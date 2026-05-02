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

### Вход в веб-интерфейс (страница логина Dashboard)

В OpenSearch Security заведены пользователи из `internal_users.yml` (хеши собираются из `.env` скриптом `render_secrets.py`).

Попробуйте по очереди:

| Логин | Пароль из `.env` |
|--------|-------------------|
| **`INDEXER_USERNAME`** (часто `admin`) | **`INDEXER_PASSWORD`** |
| **`DASHBOARD_USERNAME`** (в шаблоне `kibanaserver`) | **`DASHBOARD_PASSWORD`** |

Учётка **`API_USERNAME` / `API_PASSWORD`** — это **Wazuh API** (и плагин в `wazuh.yml`), **не** то же самое, что поле логина на странице Dashboard, если вводите не те значения.

Если пароль «не подходит» после правок `.env`:

1. Сохраните `.env` в формате **Unix (LF)**: `sed -i 's/\r$//' .env` или `dos2unix .env` — иначе в контейнер иногда попадает лишний `\r`.
2. В каталоге `center/`: `python3 scripts/render_secrets.py` (обновит `internal_users.yml` и `wazuh.yml`).
3. Перезапуск, чтобы indexer подхватил `internal_users.yml`:  
   `docker compose up -d --force-recreate wazuh.indexer wazuh.dashboard`  
   (или `docker compose down && docker compose up -d`).
4. В пароле для Docker Compose каждый символ **`$`** в `.env` нужно писать как **`$$`**, иначе Compose съест часть строки.

Проверка, что indexer принимает `admin`:  
`curl -sk -u "admin:ВАШ_INDEXER_PASSWORD" https://127.0.0.1:9200/_cluster/health?pretty` (на сервере, если 9200 проброшен).

## Ошибка `rlimit type 8` / `memlock` / `operation not permitted`

Если при `docker compose up` контейнеры **indexer** или **manager** не стартуют с сообщением про **setting rlimit**:

- **type 8** — **RLIMIT_MEMLOCK**;
- **type 7** — **RLIMIT_NOFILE** (слишком большой `nofile` в compose недоступен хосту).

Типично для **rootless Docker**, **LXC/Proxmox**, VPS с урезанными capabilities. В этом репозитории:

- в `docker-compose` **нет** кастомных `ulimits` (используются лимиты по умолчанию для контейнера);
- в `config/wazuh_indexer/wazuh.indexer.yml` задано **`bootstrap.memory_lock: false`**.

После `git pull` перезапуск: `docker compose down` и снова `up -d`.

На полноценном Docker с правами root при большой нагрузке при необходимости можно снова поднять лимиты вручную в `docker-compose.yml` под свой хост.

## Ошибка 3002, `/api/request` 401, затем `/api/login` или `/api/check-stored-api` 429

Сообщение в консоли про **CSP** (`script-src`, `unsafe-inline`) у bootstrap — ожидаемое, на работу приложения обычно не влияет.

### Что происходит по цепочке

1. Плагин Wazuh не может нормально ходить в API (неверный пароль в `wazuh.yml`, сеть до `wazuh.manager`, либо **401 от прокси** на фронтовые `POST /api/...`).
2. Интерфейс и плагин начинают **многократно** повторять запросы.
3. В ответ приходит **429**: это может быть **лимит на стороне прокси/хостинга** (Nginx `limit_req`, Cloudflare и т.п.) или временная **блокировка попыток входа** со стороны OpenSearch Security при серии неудачных обращений.

Смысл лечения: **сначала убрать первопричину 401**, затем **закрыть вкладку на 5–15 минут** (снять 429) и открыть снова.

### Конфиг Docker в этом репозитории

Том **`wazuh-dashboard-config` больше не используется**: в контейнер пробрасывается только файл `./config/wazuh_dashboard/wazuh.yml` с хоста, чтобы не застревали старые пароли API.

После `git pull` на сервере:

```bash
cd center/
python3 scripts/render_secrets.py
docker compose up -d --force-recreate wazuh.dashboard
```

Проверьте, что внутри контейнера именно ваш пароль API (без лишнего `\r` в конце строк в `.env`):

```bash
docker exec center-wazuh.dashboard cat /usr/share/wazuh-dashboard/data/wazuh/config/wazuh.yml
```

**Связь Dashboard → Manager API** (подставьте учётные данные из `.env`):

```bash
docker exec center-wazuh.dashboard curl -sk -u "ВАШ_API_USER:ВАШ_API_PASSWORD" "https://wazuh.manager:55000/?pretty"
```

Нужен JSON с `"error": 0`. Если здесь ошибка — чините manager/API и сертификаты, а не браузер.

### Обратный прокси (ваш случай `test2.mark-sandbox.ru`)

- **Не включайте второй слой HTTP Basic Auth** поверх Dashboard: браузер часто шлёт **401** на `POST /api/request` без того же `Authorization`, что вы видите как «всё сломалось» и цепочку до 429.
- Если стоит **Nginx**, не душите `location /` агрессивным **`limit_req`** без большого `burst` для длинных сессий Dashboard.
- Если перед сайтом **Cloudflare / WAF**, посмотрите в Network у ответа **429**: часто в теле или заголовках видно, кто режет (CF Ray, `server: cloudflare` и т.д.).

## Работает по IP:порту, по домену — 401 / 3002 / 429

Если **прямой заход на `https://<сервер>:443` (или ваш порт)** в порядке, а **через домен** (`https://test2.mark-sandbox.ru`) ломается, проблема почти всегда **между браузером и контейнером**: обратный прокси, TLS, заголовки, отдельная Basic Auth только на домене, Cloudflare.

### 1. Публичный URL в конфиге Dashboard

В **`center/.env`** задайте тот же адрес, что вводите в браузере (схема `https`, без слэша в конце), затем:

```bash
python3 scripts/render_secrets.py
docker compose up -d --force-recreate wazuh.dashboard
```

В `opensearch_dashboards.yml` появится строка `server.publicBaseUrl: "https://ваш.домен"` — так OpenSearch Security корректно строит куки и редиректы за прокси.

### 2. Nginx (типовой минимум)

Убедитесь, что прокси не режет запросы и передаёт схему (иначе куки и сессии ведут себя странно):

```nginx
location / {
    proxy_pass https://127.0.0.1:5601;   # или порт из DASHBOARD_HTTPS_PORT на хосте
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_read_timeout 300s;
}
```

Не навешивайте **дополнительную HTTP Basic Auth** на этот же `server`, если не уверены, что она пробрасывается на все `POST /api/...` (частый источник 401 только с домена).

### 3. Cloudflare и аналоги

Проверьте режим SSL (**Full (strict)** к вашему origin), отключите по возможности жёсткий rate limit / Bot Fight для поддомена, посмотрите ответ **429** — часто видно, что лимит выставлен на стороне CDN, а не Dashboard.

### Старый том на сервере (устарело, но можно подчистить)

Если раньше поднимали стек с томом `wazuh-dashboard-config`, он мог остаться в Docker как неиспользуемый:

```bash
docker volume ls | grep wazuh-dashboard-config
# при желании: docker volume rm <имя>
```

## Связка с `remote/`

В `remote/.env` укажите тот же `WAZUH_STACK_VERSION`, что и `WAZUH_IMAGE_VERSION` в центре, и `WAZUH_MANAGER_SERVER`.
