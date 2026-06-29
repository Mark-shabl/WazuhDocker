# Центральный сервер Wazuh (`WazuhCentral/`)

Стандартный single-node стек **Wazuh 4.14.5**: `wazuh.manager`, `wazuh.indexer`, `wazuh.dashboard`.

Основной принцип: сначала поднимаем и проверяем Dashboard по локальному IP сервера Wazuh, например `https://192.168.88.246`. Домен через Nginx Proxy Manager добавляется только после этого как внешний reverse proxy.

## Быстрый Старт

Из каталога `WazuhCentral/`:

```bash
cp .env.example .env
sudo sysctl -w vm.max_map_count=262144
sudo docker compose -f generate-indexer-certs.yml run --rm generator
sudo docker compose up -d
```

Откройте:

```text
https://<LAN_IP_сервера_Wazuh>
```

Например:

```text
https://192.168.88.246
```

Браузер предупредит о self-signed сертификате, это нормально для стандартной установки.

Дефолтный вход:

| Логин | Пароль |
| --- | --- |
| `admin` | `SecretPassword` |

## Проверка После Запуска

На сервере Wazuh:

```bash
sudo docker ps
curl -vk https://127.0.0.1:443/
curl -vk https://<LAN_IP_сервера_Wazuh>:443/
sudo docker logs --tail=100 center-wazuh.dashboard
```

На старте Dashboard может писать, что Wazuh indexer ещё не готов. По официальной документации это нормально: indexer обычно поднимается около минуты, затем Dashboard продолжает запуск.

Если `curl` возвращает `Connection refused`, смотрите логи `center-wazuh.dashboard`: контейнер не слушает порт, пока Dashboard падает или ещё стартует.

## Домен Через Nginx Proxy Manager

Настраивайте домен только после того, как `https://<LAN_IP_сервера_Wazuh>` работает напрямую.

В NPM создайте Proxy Host:

- **Domain Names**: ваш домен, например `test2.mark-sandbox.ru`.
- **Scheme**: `https`.
- **Forward Hostname / IP**: LAN IP сервера Wazuh, например `192.168.88.246`.
- **Forward Port**: `443` (или значение `DASHBOARD_HTTPS_PORT` из `.env`, если меняли порт).
- **WebSockets Support**: включить.
- **SSL**: включить Let's Encrypt для домена; `Force SSL` можно включить после проверки.
- **Advanced**: вставить содержимое `config/nginx-proxy-manager/advanced-snippet.conf`.

Проверка с машины NPM до Wazuh:

```bash
curl -vk https://<LAN_IP_сервера_Wazuh>:443/
```

Важно: не добавляйте в `config/wazuh_dashboard/opensearch_dashboards.yml` настройки публичного URL под домен. Для Wazuh Dashboard 4.14.x домен должен жить на стороне NPM: внешний сертификат, `Host`, `X-Forwarded-Proto` и проксирование к Wazuh по HTTPS.

## Порты

| Порт | Назначение |
| --- | --- |
| `443/tcp` | Wazuh Dashboard HTTPS |
| `1514/tcp` | подключение агентов |
| `1515/tcp` | регистрация агентов |
| `514/udp` | syslog |
| `55000/tcp` | Wazuh API |
| `9200/tcp` | Wazuh indexer API |

Если NPM стоит на другой машине в той же подсети, конфликта за порт `443` нет: NPM слушает свой сервер, Wazuh слушает свой сервер.

Если NPM стоит на той же машине, что и Wazuh, два процесса не смогут одновременно занять `443`. Тогда задайте в `.env`, например:

```env
DASHBOARD_HTTPS_PORT=5601
```

и в NPM используйте upstream `https://127.0.0.1:5601`.

## Ограничение Docker-Логов

В `docker-compose.yml` включён Docker `local` logging driver с ротацией stdout/stderr логов контейнеров. По умолчанию хранится до `7` файлов по `50 MB` на контейнер:

```env
DOCKER_LOG_MAX_SIZE=50m
DOCKER_LOG_MAX_FILE=7
```

Это защищает диск от бесконечного роста логов при циклических ошибках. Если нужно применить изменённые лимиты к уже созданным контейнерам:

```bash
docker compose up -d --force-recreate
```

## Смена Паролей

Для первой проверки лучше оставить дефолтные пароли и добиться рабочего Dashboard по IP. После этого меняйте пароли.

В этом репозитории есть опциональный скрипт:

```bash
python3 scripts/render_secrets.py
docker compose up -d --force-recreate wazuh.indexer wazuh.dashboard
```

Он пересобирает:

- `config/wazuh_indexer/internal_users.yml`;
- `config/wazuh_dashboard/wazuh.yml`;
- `config/wazuh_cluster/wazuh_manager.conf`.

Если пароль содержит символ `$`, в `.env` для Docker Compose пишите его как `$$`.

## Типичные Ошибки

### `vm.max_map_count`

Если indexer не стартует, проверьте:

```bash
sudo sysctl -w vm.max_map_count=262144
```

Чтобы сохранить значение после перезагрузки, добавьте его в системную конфигурацию хоста.

### `rlimit type 7/8`, `memlock`, `operation not permitted`

На некоторых VPS, LXC/Proxmox и rootless Docker нельзя поднять лимиты как в официальном compose. Поэтому в этом репозитории нет кастомных `ulimits`, а в `config/wazuh_indexer/wazuh.indexer.yml` задано:

```yaml
bootstrap.memory_lock: false
```

### `502 Bad Gateway` через NPM

Это почти всегда не Wazuh, а путь NPM до upstream:

- неверный IP сервера Wazuh;
- неверный порт;
- в NPM выбран `http` вместо `https`;
- NPM проверяет самоподписанный сертификат upstream.

Проверьте с машины NPM:

```bash
curl -vk https://<LAN_IP_сервера_Wazuh>:443/
```

### `401`, `429`, `AxiosError: Network Error`

Сначала проверьте, что прямой вход по IP работает. Если по IP работает, а через домен нет, причина обычно в NPM, Cloudflare/WAF, лишней Basic Auth или rate limit.

Не включайте дополнительную HTTP Basic Auth поверх Wazuh Dashboard, пока не убедитесь, что все `POST /api/...` проходят без 401.

## Связка С `WazuhRemote/`

Для агентов используется DNS `wazuh-manager.mark-sandbox.ru`. Он должен указывать на сервер `WazuhCentral`, а TCP `1514` и `1515` должны быть доступны с машин агентов.

В `WazuhRemote/.env` укажите тот же `WAZUH_STACK_VERSION`, что и `WAZUH_IMAGE_VERSION` в `WazuhCentral/.env`, и задайте:

```env
WAZUH_MANAGER_SERVER=wazuh-manager.mark-sandbox.ru
WAZUH_REGISTRATION_SERVER=wazuh-manager.mark-sandbox.ru
```
