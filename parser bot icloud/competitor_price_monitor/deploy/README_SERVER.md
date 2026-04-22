# Развёртывание на сервере

Ниже самый надёжный путь для этого проекта: отдельный Linux-пользователь + `systemd`.

## Рекомендуемая среда

- `Ubuntu 22.04` или `24.04`
- `Python 3.11+`
- отдельная папка без пробелов, например `/opt/competitor_price_monitor`

## 1. Установить системные пакеты

```bash
sudo apt update
sudo apt install -y python3.11 python3.11-venv python3-pip git curl
```

## 2. Создать пользователя под бота

```bash
sudo useradd -m -s /bin/bash pricebot || true
sudo mkdir -p /opt/competitor_price_monitor
sudo chown -R pricebot:pricebot /opt/competitor_price_monitor
```

## 3. Перенести проект на сервер

Самый простой способ с локального Mac:

```bash
rsync -av --delete "/Users/pavelisaenko/Documents/New project/parser bot icloud/" user@SERVER_IP:/opt/competitor_price_monitor/
```

Если удобнее, можно и через `scp`, но `rsync` лучше для повторных обновлений.

## 4. Подготовить окружение на сервере

```bash
cd /opt/competitor_price_monitor
python3.11 -m venv competitor_price_monitor/.venv
competitor_price_monitor/.venv/bin/pip install --upgrade pip
competitor_price_monitor/.venv/bin/pip install -r competitor_price_monitor/requirements.txt
competitor_price_monitor/.venv/bin/playwright install --with-deps chromium
```

## 5. Перенести `.env` и Google JSON-ключ

На сервере должны существовать:

- `/opt/competitor_price_monitor/competitor_price_monitor/.env`
- `/opt/competitor_price_monitor/competitor_price_monitor/config/google-service-account.json`

В `.env` обязательно проверьте серверный путь:

```env
COMPETITOR_PRICE_GOOGLE_CREDENTIALS_PATH=/opt/competitor_price_monitor/competitor_price_monitor/config/google-service-account.json
```

Если в локальном `.env` путь был маковский, его нужно заменить.

## 6. Установить `systemd`-сервис

Скопируйте файл:

- [competitor-price-monitor.service](/Users/pavelisaenko/Documents/New%20project/parser%20bot%20icloud/competitor_price_monitor/deploy/competitor-price-monitor.service)

На сервер:

```bash
sudo cp /opt/competitor_price_monitor/competitor_price_monitor/deploy/competitor-price-monitor.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable competitor-price-monitor
sudo systemctl start competitor-price-monitor
```

## 7. Проверить статус

```bash
sudo systemctl status competitor-price-monitor
journalctl -u competitor-price-monitor -f
```

## Как обновлять бота дальше

После новых правок:

```bash
rsync -av --delete "/Users/pavelisaenko/Documents/New project/parser bot icloud/" user@SERVER_IP:/opt/competitor_price_monitor/
ssh user@SERVER_IP
cd /opt/competitor_price_monitor
competitor_price_monitor/.venv/bin/pip install -r competitor_price_monitor/requirements.txt
sudo systemctl restart competitor-price-monitor
```

## Важные замечания

- Не переносите локальную macOS `.venv` на сервер как готовую среду. На Linux её нужно собирать заново.
- Лучше держать серверный путь без пробелов.
- Папки `competitor_price_monitor/data` и `competitor_price_monitor/logs` должны быть доступны на запись пользователю `pricebot`.
- Если `Google Sheets` вдруг перестанет работать после переноса, в первую очередь проверьте путь к JSON-ключу и что таблица открыта для `client_email` сервисного аккаунта.
