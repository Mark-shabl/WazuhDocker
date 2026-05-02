#!/usr/bin/env python3
"""
Генерирует конфиги с секретами из center/.env (без хранения паролей в YAML в git).
Нужен Docker для расчёта bcrypt (hash.sh в образе wazuh-indexer) либо задайте хеши в .env вручную.
Запуск из каталога center/:  python scripts/render_secrets.py
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load_env(path: Path) -> dict[str, str]:
    if not path.is_file():
        print(f"Нет файла {path}. Скопируйте .env.example в .env и заполните.", file=sys.stderr)
        sys.exit(1)
    env: dict[str, str] = {}
    text = path.read_text(encoding="utf-8").replace("\r\n", "\n").replace("\r", "\n")
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip()
        if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
            val = val[1:-1]
        env[key] = val.replace("$$", "$")
    return env


def docker_bcrypt_hash(plaintext: str, image: str) -> str:
    proc = subprocess.run(
        [
            "docker",
            "run",
            "--rm",
            "-e",
            f"P={plaintext}",
            image,
            "bash",
            "-lc",
            r'/usr/share/wazuh-indexer/plugins/opensearch-security/tools/hash.sh -p "$P"',
        ],
        capture_output=True,
        text=True,
        timeout=180,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"docker hash.sh failed: {proc.stderr or proc.stdout}\n"
            "Проверьте Docker или задайте INDEXER_ADMIN_BCRYPT_HASH и "
            "DASHBOARD_KIBANASERVER_BCRYPT_HASH в .env вручную."
        )
    lines = [ln.strip() for ln in proc.stdout.splitlines() if ln.strip() and not ln.strip().startswith("#")]
    if not lines:
        raise RuntimeError("hash.sh вернул пустой вывод.")
    return lines[-1].strip().strip('"').strip("'")


def yaml_double_quoted(s: str) -> str:
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def patch_opensearch_dashboards_public_base_url(path: Path, base_url: str) -> None:
    """Добавляет или удаляет server.publicBaseUrl (нужно за reverse proxy с другим хостом, чем у контейнера)."""
    raw = path.read_text(encoding="utf-8").replace("\r\n", "\n").replace("\r", "\n")
    lines = [ln for ln in raw.splitlines() if not ln.lstrip().startswith("server.publicBaseUrl:")]
    out_lines: list[str] = []
    if base_url:
        insert = f"server.publicBaseUrl: {yaml_double_quoted(base_url)}"
        inserted = False
        for ln in lines:
            out_lines.append(ln)
            if not inserted and ln.strip() == "server.port: 5601":
                out_lines.append(insert)
                inserted = True
        if not inserted:
            out_lines.append(insert)
    else:
        out_lines = lines
    path.write_text("\n".join(out_lines) + "\n", encoding="utf-8")


def write_wazuh_yml(
    path: Path,
    api_url: str,
    api_user: str,
    api_password: str,
    api_ca: str,
    run_as: bool,
) -> None:
    run_as_literal = "true" if run_as else "false"
    ca_line = f"      ca: {yaml_double_quoted(api_ca)}\n" if api_ca else ""
    body = f"""hosts:
  - 1513629884013:
      url: {yaml_double_quoted(api_url)}
      port: 55000
      username: {yaml_double_quoted(api_user)}
      password: {yaml_double_quoted(api_password)}
{ca_line}      run_as: {run_as_literal}
"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


def main() -> None:
    env_path = ROOT / ".env"
    env = load_env(env_path)

    ver = env.get("WAZUH_IMAGE_VERSION", "4.14.4").strip()
    image = f"wazuh/wazuh-indexer:{ver}"

    admin_hash = env.get("INDEXER_ADMIN_BCRYPT_HASH", "").strip()
    kibana_hash = env.get("DASHBOARD_KIBANASERVER_BCRYPT_HASH", "").strip()

    if not admin_hash or not kibana_hash:
        idx_pw = env.get("INDEXER_PASSWORD", "").strip()
        dash_pw = env.get("DASHBOARD_PASSWORD", "").strip()
        if not idx_pw or not dash_pw:
            print(
                "Задайте INDEXER_PASSWORD и DASHBOARD_PASSWORD в .env "
                "или укажите готовые INDEXER_ADMIN_BCRYPT_HASH и DASHBOARD_KIBANASERVER_BCRYPT_HASH.",
                file=sys.stderr,
            )
            sys.exit(1)
        try:
            if not admin_hash:
                admin_hash = docker_bcrypt_hash(idx_pw, image)
            if not kibana_hash:
                kibana_hash = docker_bcrypt_hash(dash_pw, image)
        except FileNotFoundError:
            print(
                "Команда docker не найдена. Установите Docker или пропишите в .env:\n"
                "  INDEXER_ADMIN_BCRYPT_HASH=...\n"
                "  DASHBOARD_KIBANASERVER_BCRYPT_HASH=...\n"
                "(получить: docker run --rm -e P='пароль' IMAGE bash -lc "
                "'/usr/share/wazuh-indexer/plugins/opensearch-security/tools/hash.sh -p \"$P\"')",
                file=sys.stderr,
            )
            sys.exit(1)
        except RuntimeError as e:
            print(str(e), file=sys.stderr)
            sys.exit(1)

    cluster_key = env.get("WAZUH_CLUSTER_KEY", "").strip()
    if not cluster_key:
        print("Задайте WAZUH_CLUSTER_KEY в .env (например 32 hex-символа).", file=sys.stderr)
        sys.exit(1)

    indexer_internal_url = env.get("INDEXER_URL_INTERNAL", "https://wazuh.indexer:9200").strip()
    if not indexer_internal_url:
        indexer_internal_url = "https://wazuh.indexer:9200"

    tmpl_iu = ROOT / "config/wazuh_indexer/internal_users.yml.template"
    out_iu = ROOT / "config/wazuh_indexer/internal_users.yml"
    text = tmpl_iu.read_text(encoding="utf-8")
    text = text.replace("__ADMIN_BCRYPT_HASH__", yaml_double_quoted(admin_hash))
    text = text.replace("__KIBANASERVER_BCRYPT_HASH__", yaml_double_quoted(kibana_hash))
    out_iu.write_text(text, encoding="utf-8")

    tmpl_mgr = ROOT / "config/wazuh_cluster/wazuh_manager.conf.template"
    out_mgr = ROOT / "config/wazuh_cluster/wazuh_manager.conf"
    mgr_body = tmpl_mgr.read_text(encoding="utf-8")
    mgr_body = mgr_body.replace("__WAZUH_CLUSTER_KEY__", cluster_key)
    mgr_body = mgr_body.replace("__INDEXER_URL_INTERNAL__", indexer_internal_url)
    out_mgr.write_text(mgr_body, encoding="utf-8")

    api_url = env.get("WAZUH_API_URL", "https://wazuh.manager").strip()
    api_user = env.get("API_USERNAME", "").strip()
    api_pass = env.get("API_PASSWORD", "").strip()
    if not api_user or not api_pass:
        print("Задайте API_USERNAME и API_PASSWORD в .env.", file=sys.stderr)
        sys.exit(1)
    # Путь CA внутри контейнера dashboard (опционально). Пустое значение = как в upstream, без поля ca в wazuh.yml.
    if "WAZUH_API_CA_PATH" in env:
        api_ca = env["WAZUH_API_CA_PATH"].strip()
    else:
        api_ca = ""
    run_as = env.get("WAZUH_API_RUN_AS", "true").strip().lower() in ("1", "true", "yes")

    write_wazuh_yml(
        ROOT / "config/wazuh_dashboard/wazuh.yml",
        api_url,
        api_user,
        api_pass,
        api_ca,
        run_as,
    )

    osd_path = ROOT / "config/wazuh_dashboard/opensearch_dashboards.yml"
    public_base = env.get("DASHBOARD_PUBLIC_BASE_URL", "").strip().rstrip("/")
    patch_opensearch_dashboards_public_base_url(osd_path, public_base)

    print(
        "OK: internal_users.yml, wazuh_manager.conf, wazuh.yml, opensearch_dashboards.yml обновлены из .env"
    )


if __name__ == "__main__":
    main()
