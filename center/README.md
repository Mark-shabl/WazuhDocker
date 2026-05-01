# Центральный сервер Wazuh (`center/`)

Стабильный стек **Wazuh 4.14.x** (по умолчанию **4.14.4**). Секреты и пароли задаются только в **`.env`** (шаблон — `.env.example`).

## Порядок развёртывания

### 1. Память для Indexer (Linux / WSL)

```bash
sudo sysctl -w vm.max_map_count=262144
```

### 2. Переменные окружения

```bash
cp .env.example .env
# Отредактируйте пароли, API, WAZUH_CLUSTER_KEY и при необходимости порты.
```

Имена пользователей OpenSearch в шаблоне зафиксированы: **`admin`** и **`kibanaserver`** — их пароли берутся из `INDEXER_PASSWORD` и `DASHBOARD_PASSWORD`.

### 3. Конфиги с секретами (обязательно до `docker compose up`)

Из каталога **`center/`** (нужны **Python 3** и **Docker** для расчёта bcrypt через `hash.sh` в образе indexer; либо задайте в `.env` готовые `INDEXER_ADMIN_BCRYPT_HASH` и `DASHBOARD_KIBANASERVER_BCRYPT_HASH`):

```bash
python scripts/render_secrets.py
```

Создаются (и при этом **не коммитятся** в git): `config/wazuh_indexer/internal_users.yml`, `config/wazuh_dashboard/wazuh.yml`, `config/wazuh_cluster/wazuh_manager.conf`.

После **смены любого пароля или ключа** в `.env` снова выполните этот скрипт и перезапустите стек.

### 4. TLS-сертификаты узлов

```bash
docker compose -f generate-indexer-certs.yml run --rm generator
```

### 5. Запуск

```bash
docker compose up -d
```

- Dashboard: `https://<IP_хоста>` на порту из **`DASHBOARD_HTTPS_PORT`** в `.env` (по умолчанию **443**).
- Вход в OpenSearch/Dashboard: `INDEXER_USERNAME` / `INDEXER_PASSWORD` (по умолчанию совпадает с демо Wazuh).

## Ошибка `rlimit type 8` / `memlock` / `operation not permitted`

Если при `docker compose up` контейнеры **indexer** или **manager** не стартуют с сообщением про **setting rlimit**:

- **type 8** — **RLIMIT_MEMLOCK**;
- **type 7** — **RLIMIT_NOFILE** (слишком большой `nofile` в compose недоступен хосту).

Типично для **rootless Docker**, **LXC/Proxmox**, VPS с урезанными capabilities. В этом репозитории:

- в `docker-compose` **нет** кастомных `ulimits` (используются лимиты по умолчанию для контейнера);
- в `config/wazuh_indexer/wazuh.indexer.yml` задано **`bootstrap.memory_lock: false`**.

После `git pull` перезапуск: `docker compose down` и снова `up -d`.

На полноценном Docker с правами root при большой нагрузке при необходимости можно снова поднять лимиты вручную в `docker-compose.yml` под свой хост.

## Связка с `remote/`

В `remote/.env` укажите тот же `WAZUH_STACK_VERSION`, что и `WAZUH_IMAGE_VERSION` в центре, и `WAZUH_MANAGER_SERVER`.
