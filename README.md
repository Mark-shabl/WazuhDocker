# Wazuh в Docker: центр и агенты

Минимальный репозиторий под **стабильный Wazuh 4.14.5** (образы `wazuh/wazuh-*`).

| Каталог | Назначение |
|---------|------------|
| **`WazuhCentral/`** | Центральный узел: indexer, manager, dashboard. Стандартный single-node запуск, генерация TLS через `generate-indexer-certs.yml`. |
| **`WazuhRemote/`** | Агент на Linux (или другой хост с Docker): подключение к manager по DNS `wazuh-manager.mark-sandbox.ru`. |

Быстрый старт — в **`WazuhCentral/README.md`** и **`WazuhRemote/README.md`**.

Официальная документация Wazuh: [развёртывание в Docker](https://documentation.wazuh.com/current/deployment-options/docker/wazuh-container.html).
