# Wazuh в Docker: центр и агенты

Минимальный репозиторий под **стабильный Wazuh 4.14.x** (образы `wazuh/wazuh-*`).

| Каталог | Назначение |
|---------|------------|
| **`center/`** | Центральный узел: indexer, manager, dashboard. Секреты в `.env`, скрипт `scripts/render_secrets.py`, генерация TLS `generate-indexer-certs.yml`. |
| **`remote/`** | Агент на Linux (или другой хост с Docker): подключение к manager по `WAZUH_MANAGER_SERVER`. |

Быстрый старт — в **`center/README.md`** и **`remote/README.md`**.

Официальная документация Wazuh: [развёртывание в Docker](https://documentation.wazuh.com/current/deployment-options/docker/wazuh-container.html).
