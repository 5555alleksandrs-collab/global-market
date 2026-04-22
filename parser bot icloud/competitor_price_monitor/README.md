# Competitor Price Monitor

Python-бот для мониторинга цен конкурентов на `iPhone`, `iPad`, `MacBook`, `Apple Watch` и аксессуары по прямым ссылкам на карточки товаров.

В примере конфига уже добавлены пресеты селекторов для:

- `https://i-lite.ru/`
- `https://ilabstore.ru/`

## Что умеет

- открывает карточки товаров по URL
- вытаскивает название, цену, цену без скидки и наличие
- пишет дату проверки
- сохраняет текущий отчёт и историю в CSV
- умеет выгружать тот же отчёт в Google Sheets
- сравнивает цену конкурента с вашей ценой
- считает разницу в рублях и показывает, кто дешевле
- помечает товары, где конкурент дешевле
- помечает товары, где цена изменилась с прошлого запуска
- поддерживает разные сайты через отдельные CSS-селекторы
- использует `requests` и автоматически падает обратно на `Playwright`, если сайт рендерится через JavaScript
- логирует процесс и ошибки

## Структура

```text
competitor_price_monitor/
├── .env.example
├── __main__.py
├── cli.py
├── config/
│   └── settings.example.yaml
├── data/
├── extractor.py
├── fetchers.py
├── logging_setup.py
├── models.py
├── query_compare.py
├── README.md
├── requirements.txt
├── run.sh
├── run_telegram_bot.sh
├── runner.py
├── sinks.py
├── snapshots.py
├── telegram_bot.py
└── tests/
```

## Быстрый старт

1. Создайте рабочий конфиг на основе примера:

   ```bash
   cp competitor_price_monitor/config/settings.example.yaml competitor_price_monitor/config/settings.yaml
   ```

2. В `competitor_price_monitor/config/settings.yaml`:

- укажите реальные ссылки конкурентов
- добавьте ваши цены в `my_price`
- настройте селекторы для каждого сайта в блоке `sites`
- при необходимости включите Google Sheets

Для этих двух сайтов блок `sites` уже подготовлен, поэтому обычно достаточно только подставить прямые URL карточек товаров в `products`.

Если товаров много, можно не держать их в YAML, а подключить отдельный CSV:

```yaml
products_file: ./products.ilab_template.csv
```

Формат CSV:

```text
key,label,url,my_price,site,enabled
iphone-17-256gb-black,iPhone 17 256GB Black,https://ilabstore.ru/...,,ilabstore,true
```

В проект уже добавлен шаблон под ваш большой список моделей: [products.ilab_template.csv](/Users/pavelisaenko/Documents/New%20project/parser%20bot%20icloud/competitor_price_monitor/config/products.ilab_template.csv)

3. Запуск одной командой:

   ```bash
   cd "/Users/pavelisaenko/Documents/New project/parser bot icloud"
   ./run.sh
   ```

При первом запуске скрипт сам создаст `.venv`, установит зависимости и скачает Chromium для `Playwright`.

## Telegram-бот

Если хотите просто писать в Telegram текстовые запросы и получать готовое сравнение:

1. Создайте локальный `.env`:

   ```bash
   cp "/Users/pavelisaenko/Documents/New project/parser bot icloud/competitor_price_monitor/.env.example" \
      "/Users/pavelisaenko/Documents/New project/parser bot icloud/competitor_price_monitor/.env"
   ```

2. Укажите токен:

   ```env
   COMPETITOR_PRICE_BOT_TOKEN=your_telegram_bot_token_here
   ```

3. Запустите:

   ```bash
   cd "/Users/pavelisaenko/Documents/New project/parser bot icloud"
   ./run_telegram_bot.sh
   ```

После запуска в боте появятся кнопки:

- `Примеры запросов`
- `CSV сравнения`
- `Google Sheets`
- `Список моделей`
- `Помощь`

Если хотите ограничить доступ к боту, добавьте в `.env`:

```env
COMPETITOR_PRICE_ALLOWED_USER_IDS=123456789
COMPETITOR_PRICE_ALLOWED_CHAT_IDS=
COMPETITOR_PRICE_ADMIN_USER_IDS=123456789
COMPETITOR_PRICE_ADMIN_CHAT_IDS=
```

Поддерживаются списки через запятую. Удобнее всего сначала написать боту `/whoami`, чтобы увидеть свой `user_id` и `chat_id`.

Примеры запросов в чат:

- `17 pro 256 silver sim`
- `сравни 17 pro max 512 deep blue esim`
- `/compare 17 256 mist blue esim`
- `/devices`
- `/sheets`
- `/catalog`
- `/menu`
- `/notify_on`
- `/notify_off`
- `/whoami`
- `/admin`

`/devices` и кнопка `CSV сравнения` формируют удобную ценовую матрицу: слева модели, сверху магазины, а в ячейках только цены. Если по магазину не удалось найти карточку, ячейка остаётся пустой. Справа дополнительно идут `Лучшая цена`, `Где дешевле` и `Разница max-min`. Во время сборки бот присылает короткий прогресс, потому что полный CSV может собираться несколько минут.

`/menu` открывает единое рабочее меню. Бот старается переиспользовать один и тот же экран меню и не спамить новыми сообщениями при переходах между разделами, админкой и действиями.

`/sheets` и кнопка `Google Sheets` обновляют одну и ту же Google-таблицу:

- вкладка `Сравнение цен`: матрица по магазинам, `Моя цена`, лучшая цена и признак, дешевле ли конкурент вас
- вкладка `Список моделей`: справочник моделей, query-подсказки, ваши цены и ссылки

`/catalog` и кнопка `Список моделей` отправляют справочный CSV со списком поддерживаемых моделей и готовыми query-подсказками.

`/notify_on` добавляет текущий чат в автоуведомления, `/notify_off` убирает его. По умолчанию бот также запоминает чат после `/start` и обычного использования.

`/whoami` показывает `user_id`, `chat_id`, тип чата и текущий статус доступа. Это удобно для настройки приватного доступа через allowlist.

`/admin` открывает админку доступа прямо в Telegram. Через неё можно:

- посмотреть текущий allowlist
- добавить `user_id`
- добавить `chat_id`
- убрать `user_id`
- убрать `chat_id`

Сами права администратора лучше зафиксировать в `.env` через `COMPETITOR_PRICE_ADMIN_USER_IDS`, чтобы их нельзя было случайно потерять из админки.

Если у пользователя ещё нет доступа, бот в личке предложит кнопку для отправки номера телефона. После этого администратору придёт заявка с кнопками `Одобрить` и `Отклонить`, а доступ можно будет выдать прямо из Telegram.

Сейчас Telegram-бот умеет принимать такой текст, искать нужные карточки на `iLab`, `I LITE`, `KingStore Saratov`, `SOTOViK` и `Хатико`, присылать готовое сравнение цен и выгружать CSV со сравнением по всем магазинам.

## Ручной запуск без shell-скрипта

```bash
python3 -m venv competitor_price_monitor/.venv
competitor_price_monitor/.venv/bin/pip install -r competitor_price_monitor/requirements.txt
competitor_price_monitor/.venv/bin/playwright install chromium
competitor_price_monitor/.venv/bin/python -m competitor_price_monitor --config competitor_price_monitor/config/settings.yaml
```

## Пример селекторов

```yaml
sites:
  my_store:
    domains:
      - shop.example.ru
    engine: auto
    wait_for: "h1"
    selectors:
      title:
        selector: "h1"
        required: true
      price:
        selectors:
          - ".price"
          - "[data-price]"
        required: true
      original_price:
        selectors:
          - ".price-old"
      availability:
        selector: ".availability"
    availability:
      in_stock_patterns:
        - "в наличии"
      out_of_stock_patterns:
        - "нет в наличии"
```

## Что пишет бот

`data/current_report.csv`

- текущий срез по всем товарам

`data/history.csv`

- история проверок по каждому запуску

`data/latest_snapshot.json`

- технический snapshot для сравнения с прошлым запуском

`logs/price_monitor.log`

- лог запуска и ошибок

## Развёртывание на сервере

Для этого проекта самый практичный вариант: `Ubuntu` + `systemd`.

Готовые файлы:

- [README_SERVER.md](/Users/pavelisaenko/Documents/New%20project/parser%20bot%20icloud/competitor_price_monitor/deploy/README_SERVER.md)
- [competitor-price-monitor.service](/Users/pavelisaenko/Documents/New%20project/parser%20bot%20icloud/competitor_price_monitor/deploy/competitor-price-monitor.service)

Коротко:

```bash
sudo apt update
sudo apt install -y python3.11 python3.11-venv python3-pip git curl
cd /opt/competitor_price_monitor
python3.11 -m venv competitor_price_monitor/.venv
competitor_price_monitor/.venv/bin/pip install -r competitor_price_monitor/requirements.txt
competitor_price_monitor/.venv/bin/playwright install --with-deps chromium
sudo cp competitor_price_monitor/deploy/competitor-price-monitor.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable competitor-price-monitor
sudo systemctl start competitor-price-monitor
```

Важно: на сервере нужно заново собрать `.venv`, а в `.env` поменять `COMPETITOR_PRICE_GOOGLE_CREDENTIALS_PATH` на серверный путь без маковских директорий.

## Google Sheets

Чтобы включить выгрузку:

1. Создайте сервисный аккаунт в Google Cloud
2. Скачайте JSON-ключ
3. Положите файл, например, в `competitor_price_monitor/config/google-service-account.json`
4. Дайте этому сервисному аккаунту доступ к нужной таблице
5. Включите `output.google_sheets.enabled: true`
6. Укажите `spreadsheet_id` и `credentials_path`

Для Telegram-бота удобнее сразу положить настройки в `.env`:

```env
COMPETITOR_PRICE_GOOGLE_SHEETS_ID=ваш_spreadsheet_id
COMPETITOR_PRICE_GOOGLE_CREDENTIALS_PATH="/полный/путь/до/google-service-account.json"
COMPETITOR_PRICE_GOOGLE_COMPARISON_WORKSHEET="__FIRST__"
COMPETITOR_PRICE_GOOGLE_CATALOG_WORKSHEET="Список моделей"
COMPETITOR_PRICE_AUTO_REFRESH_ENABLED=true
COMPETITOR_PRICE_AUTO_REFRESH_DAILY_TIME=10:00
COMPETITOR_PRICE_AUTO_REFRESH_TIMEZONE=Europe/Moscow
COMPETITOR_PRICE_AUTO_REFRESH_UPDATE_SHEETS=true
COMPETITOR_PRICE_AUTO_REFRESH_RUN_ON_START=false
```

После этого в боте можно нажать `Google Sheets` или отправить `/sheets`, и он обновит обе вкладки в одной таблице и пришлёт ссылку.

Если хотите писать сравнение прямо в первый лист таблицы, используйте специальное значение `__FIRST__`. Тогда бот обновит самую первую вкладку, даже если она называется `Лист1`.

В этом режиме бот не перетирает весь лист целиком: он очищает и заполняет только блок данных, начиная с `A5`, чтобы сохранить ваш верхний оформленный шаблон и шапку таблицы.

В шаблонном первом листе `старая цена` означает цену магазина с предыдущего запуска бота, а не зачёркнутую цену со страницы товара. На самом первом запуске эти колонки будут пустыми, а со второго начнут показывать прошлое значение.

Автообновление работает прямо внутри Telegram-бота:

- бот по расписанию сам собирает свежие цены
- сравнивает их с предыдущим запуском по каждому магазину
- обновляет Google Sheets
- присылает в подписанные чаты только те позиции, где цена изменилась

По умолчанию Telegram-бот настроен на ежедневное обновление в `10:00` по `Europe/Moscow`. При желании время можно поменять через `COMPETITOR_PRICE_AUTO_REFRESH_DAILY_TIME`, а часовой пояс через `COMPETITOR_PRICE_AUTO_REFRESH_TIMEZONE`.

Если текущая цена конкурента стала ниже вашей, бот явно напишет это в уведомлении.

## Архитектура под расширение

- `runner.py` содержит основной orchestration flow
- `sinks.py` легко расширяется под Telegram, email и только-изменившиеся уведомления
- `snapshots.py` уже хранит прошлое состояние для диффов
- планировщик можно добавить через `cron`, `launchd`, `systemd` или будущий Telegram-бот

## Тесты

```bash
python3 -m unittest discover -s competitor_price_monitor/tests
```
