# Telegram-ассистент закупщика iPhone

Рабочий Python-проект на macOS: рассылка запросов поставщикам в закрытых чатах через **MTProto (Telethon)** и сбор ответов с нормализацией/разбором без LLM.

## 1. Получение `api_id` и `api_hash`

1. Откройте [https://my.telegram.org](https://my.telegram.org).
2. Войдите по номеру телефона.
3. Перейдите в **API development tools** → **Create application**.
4. Скопируйте **api_id** (число) и **api_hash** (строка) в `config.py` в переменные `API_ID` и `API_HASH`.

## 2. Первый запуск и авторизация

```bash
cd procurement_assistant
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python main.py
```

При первом запуске Telethon запросит номер телефона и код из Telegram. Сессия сохранится в файл `{SESSION_NAME}.session` (по умолчанию `procurement.session`) в текущей папке; при следующих запусках повторный ввод кода не нужен.

## 3. Как указать чаты в `TARGET_CHATS` и `ALLOWED_REPLY_SOURCES`

Поддерживаются три вида идентификаторов:

1. **Username** (без `@`): `"supplier_username"`.
2. **Числовой ID пользователя** (личный диалог): `123456789`.
3. **Числовой ID группы/супергруппы**: обычно отрицательный, например `-1001234567890`.

`ALLOWED_REPLY_SOURCES` должен совпадать с вашими реальными поставщиками или быть его подмножеством: ответы учитываются **только** от этих источников.

**Как узнать ID чата**

- Через боты вроде `@userinfobot`, `@getidsbot` (отправьте пересланное сообщение или ссылку).
- Через клиент Telethon: временный скрипт с `print((await client.get_entity('username')).id)`.

В `config.py` укажите `MY_CHAT_ID`: свой **user_id** или **username**, в чат с которым вы будете писать запросы (часто это «Избранное» / диалог с собой).

## 4. Запуск

```bash
# Обычный запуск
python main.py

# Без реальной отправки (только логика и логи)
DRY_RUN=True python main.py

# Без запроса подтверждения «Да»/«Нет»
FAST_MODE=True python main.py
```

Переменные `DRY_RUN` и `FAST_MODE` можно также задать в `config.py`.

## 5. Логи

- **`logs/sessions.json`** — сохранённые сессии рассылки (цели, ответы, лучшая цена).
- **`logs/activity.jsonl`** — поток событий в формате JSON (одна JSON-строка на событие), UTC.

Просмотр сессий:

```bash
cat logs/sessions.json | python3 -m json.tool
```

Просмотр последних строк журнала:

```bash
tail -n 20 logs/activity.jsonl | python3 -m json.tool
```

Консольный вывод дублирует основные события в человекочитаемом виде.

## 6. Шаблон сообщения поставщикам

В `config.py` измените `MESSAGE_TEMPLATE`. Плейсхолдер `{query}` подставляет нормализованную строку запроса.

Примеры:

```python
MESSAGE_TEMPLATE = "{query}?"
MESSAGE_TEMPLATE = "Нужен {query}"
MESSAGE_TEMPLATE = "Есть {query}?"
```

## 7. Новые синонимы

Откройте `normalizer.py` и добавьте строки в соответствующие списки паттернов (`_MODEL_PATTERNS`, `_MEMORY_PATTERNS`, `_COLOR_PATTERNS`, `_SIM_PATTERNS`, `_REGION_PATTERNS`).

## Структура проекта

```
procurement_assistant/
├── main.py
├── config.py
├── telegram_client.py
├── normalizer.py
├── parser.py
├── matcher.py
├── session_store.py
├── logger.py
├── requirements.txt
├── README.md
└── logs/
    ├── sessions.json   # создаётся при сохранении сессии
    └── activity.jsonl  # журнал событий
```

Таймзона меток времени в логах — **UTC**.
