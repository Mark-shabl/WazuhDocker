# Удалённый агент Wazuh (`remote/`)

Стабильный образ **4.14.x** (по умолчанию **4.14.4**) — **ту же версию** укажите в `.env`, что и `WAZUH_IMAGE_VERSION` в `center/` на главном сервере.

---

## Linux: агент в Docker на каждом хосте

На каждой машине, которую нужно мониторить:

1. Скопируйте папку **`remote/`** (или весь репозиторий) на сервер.
2. На **центральном** сервере с `center/` в firewall должны быть разрешены входящие **TCP 1514** и **TCP 1515** с сетей, откуда ходят агенты.
3. С агента проверка: `nc -zv <IP_manager> 1514` и `1515`.

```bash
cd remote
cp .env.example .env
```

В **`.env`**:

| Переменная | Значение |
|------------|----------|
| `WAZUH_STACK_VERSION` | Тот же тег, что образы на центре (например `4.14.4`). |
| `WAZUH_MANAGER_SERVER` | **Публичный или VLAN IP/DNS** сервера с `center/`, **не** `127.0.0.1`. |

В `docker-compose.yml` уже есть `extra_hosts: host.docker.internal:host-gateway` — на Linux это даёт **host.docker.internal** как шлюз на хост; для связи с **удалённым** менеджером оно не обязательно, но и не мешает.

```bash
docker compose up -d
docker compose logs -f   # при необходимости
```

Остановка: `docker compose down`.

---

## Windows / macOS (Docker Desktop, менеджер на этой же машине)

Для агента на той же системе, где крутится `center/`, в `.env` удобно задать:

`WAZUH_MANAGER_SERVER=host.docker.internal`

---

## Конфиг агента

Файл **`config/wazuh-agent-conf`** — шаблон от Wazuh. Образ подставляет **`WAZUH_MANAGER_SERVER`** в `ossec.conf` при старте. Для групп, имени агента, профиля и т.д. отредактируйте шаблон (см. [документацию Wazuh](https://documentation.wazuh.com/current/user-manual/reference/ossec-conf/index.html)).

---

## Ограничения Docker-агента

Агент видит **ФС и процессы внутри контейнера**, а не полный хост. Если нужен полный охват хоста Linux, типичные варианты:

- монировать нужные каталоги хоста в контейнер (`volumes` в `docker-compose.yml`);
- или ставить агент **нативно** на хост (apt/rpm) без Docker.

Для централизованного паттерна «много одинаковых Docker-агентов» часто достаточно текущей схемы с прицелом на единообразие окружения.
