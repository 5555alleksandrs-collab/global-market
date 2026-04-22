# Telegram MTProto credentials
API_ID = 0  # получить на my.telegram.org
API_HASH = ""  # получить на my.telegram.org
SESSION_NAME = "procurement"

# Мой аккаунт — куда присылать финальный результат
MY_CHAT_ID = 0  # мой Telegram user_id или username

# Список чатов для рассылки запросов поставщикам
# Формат: список username, числовых chat_id или числовых user_id
TARGET_CHATS = [
    "supplier_username_1",
    "supplier_username_2",
    123456789,  # числовой chat_id группы
    987654321,  # числовой user_id личной переписки
]

# Белый список источников — только отсюда принимать ответы
# Должен совпадать или быть подмножеством TARGET_CHATS
ALLOWED_REPLY_SOURCES = [
    "supplier_username_1",
    "supplier_username_2",
    123456789,
    987654321,
]

# Время ожидания ответов в секундах
REPLY_WAIT_SECONDS = 600  # 10 минут по умолчанию

# Шаблон сообщения поставщикам
# {query} — подставляется нормализованный запрос
MESSAGE_TEMPLATE = "{query}?"

# Режимы запуска
DRY_RUN = False  # True = не отправлять, только показывать
FAST_MODE = False  # True = не спрашивать подтверждение
HUMAN_IN_THE_LOOP = True  # True = показать и спросить подтверждение перед отправкой

# Защита от дублей
# Если одно и то же сообщение уже отправлялось в этот чат за последние N секунд — не слать повторно
DEDUP_WINDOW_SECONDS = 300  # 5 минут
