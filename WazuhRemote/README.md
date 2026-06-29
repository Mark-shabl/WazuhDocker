# Агент Wazuh (`WazuhRemote/`)

Docker-агент **Wazuh 4.14.5** для локальных и удалённых серверов. Все агенты подключаются к manager через DNS-имя:

```text
wazuh-manager.mark-sandbox.ru
```

Это обычный TCP-доступ к Wazuh manager, не HTTP reverse proxy. Для агентов нужны порты:

| Порт | Назначение |
| --- | --- |
| `1514/tcp` | постоянное подключение агента к manager |
| `1515/tcp` | первичная регистрация / enrollment |

## DNS И Firewall

DNS-запись должна указывать на адрес сервера `WazuhCentral`:

```text
wazuh-manager.mark-sandbox.ru -> IP_сервера_WazuhCentral
```

На сервере `WazuhCentral` разрешите входящие TCP `1514` и `1515` от сетей/серверов, где будут запущены агенты. Для публичного интернета лучше ограничить firewall конкретными IP агентов или использовать VPN.

Проверка с машины агента:

```bash
nc -zv wazuh-manager.mark-sandbox.ru 1514
nc -zv wazuh-manager.mark-sandbox.ru 1515
```

## Запуск

На машине агента:

```bash
cd WazuhRemote
cp .env.example .env
```

В `.env` задайте уникальное имя агента:

```env
WAZUH_STACK_VERSION=4.14.5
WAZUH_MANAGER_SERVER=wazuh-manager.mark-sandbox.ru
WAZUH_REGISTRATION_SERVER=wazuh-manager.mark-sandbox.ru
WAZUH_AGENT_GROUP=default
WAZUH_AGENT_NAME=server-name-here
```

Запуск:

```bash
docker compose up -d
```

Проверка:

```bash
docker exec wazuh-remote-agent grep -A20 '<client>' /var/ossec/etc/ossec.conf
docker logs --tail=100 wazuh-remote-agent
```

В `ossec.conf` должны быть:

```xml
<address>wazuh-manager.mark-sandbox.ru</address>
<manager_address>wazuh-manager.mark-sandbox.ru</manager_address>
<groups>default</groups>
```

На сервере `WazuhCentral`:

```bash
docker exec center-wazuh.manager /var/ossec/bin/agent_control -l
```

## Ограничение Docker-Логов

В `docker-compose.yml` включён Docker `local` logging driver с ротацией stdout/stderr логов контейнера. По умолчанию хранится до `7` файлов по `50 MB`:

```env
DOCKER_LOG_MAX_SIZE=50m
DOCKER_LOG_MAX_FILE=7
```

Если нужно применить изменённые лимиты к уже созданному контейнеру:

```bash
docker compose up -d --force-recreate
```

## Повторный Запуск И Ключи

Ключ агента хранится в named volume `wazuh-agent-etc`, чтобы после `docker compose down/up` агент не терял регистрацию и не получал `Duplicate agent name`.

Если нужно полностью пере-регистрировать агент с тем же именем:

```bash
docker compose down
docker volume rm wazuh-remote_wazuh-agent-etc 2>/dev/null || true
```

Затем удалите старого агента на manager через Dashboard или `manage_agents`, после чего снова запустите:

```bash
docker compose up -d
```

## Ограничения Docker-Агента

Агент видит файловую систему и процессы внутри контейнера, а не полный хост. Если нужен полный охват Linux-хоста, типичные варианты:

- монтировать нужные каталоги хоста в контейнер через `volumes`;
- установить Wazuh agent нативно на хост без Docker.
