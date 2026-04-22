"""
Настройки бота: токен Telegram, Google Sheets, фильтр цен.
Скопируйте .env.example в .env или задайте переменные окружения.
"""

from __future__ import annotations

import os
import re
from pathlib import Path


def _normalize_spreadsheet_id(raw: str) -> str:
    """Из URL или строки с кавычками извлекает только ID таблицы."""
    s = (raw or "").strip().strip('"').strip("'")
    if not s:
        return ""
    m = re.search(r"/d/([a-zA-Z0-9-_]+)", s)
    if m:
        return m.group(1)
    return s

try:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parent / ".env")
except ImportError:
    pass

# Telegram Bot API (создать у @BotFather)
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")

# Google Sheets: JSON ключ сервисного аккаунта + ID таблицы
GOOGLE_CREDENTIALS_PATH = os.environ.get(
    "GOOGLE_CREDENTIALS_PATH",
    str(Path(__file__).resolve().parent / "credentials.json"),
)
SPREADSHEET_ID = _normalize_spreadsheet_id(os.environ.get("SPREADSHEET_ID", ""))

# Имя листа, где колонка A — товары (как в таблице, без «пробив» и т.п. если такого листа нет).
WORKSHEET_NAME = (os.environ.get("WORKSHEET_NAME", "Лист1") or "Лист1").strip()

# Дополнительные имена для поиска листа, через запятую (если основное не совпало)
WORKSHEET_FALLBACK_NAMES: list[str] = []
_fb = os.environ.get("WORKSHEET_FALLBACK_NAMES", "").strip()
if _fb:
    WORKSHEET_FALLBACK_NAMES = [x.strip() for x in _fb.split(",") if x.strip()]

# Если листа с именем из WORKSHEET_NAME нет — взять первый лист таблицы (1 = да)
WORKSHEET_FALLBACK_TO_FIRST = os.environ.get(
    "WORKSHEET_FALLBACK_TO_FIRST", "1"
).strip().lower() not in ("0", "false", "no", "")

# Секции прайса по флагам: 🇯🇵 → суффикс ключа (япония / eSIM), 🇬🇧 → (UK / SIM)
REGION_SUFFIX_JP = (os.environ.get("REGION_SUFFIX_JP", "eSIM") or "eSIM").strip()
REGION_SUFFIX_GB = (os.environ.get("REGION_SUFFIX_GB", "SIM") or "SIM").strip()

# Товары в колонке A; первая строка с названиями товаров (после шапки «Наименование»)
DATA_START_ROW = int(os.environ.get("DATA_START_ROW", "2"))

# Колонки «Заход первая цена» и «Заход вторая цена» (F=6, G=7)
FIRST_PRICE_COLUMN = int(os.environ.get("FIRST_PRICE_COLUMN", "6"))
SECOND_PRICE_COLUMN = int(os.environ.get("SECOND_PRICE_COLUMN", "7"))

# Сколько строк сканировать в A при поиске товара
MAX_SCAN_ROWS = int(os.environ.get("MAX_SCAN_ROWS", "5000"))

# JSON: имя поставщика -> {red, green, blue} в диапазоне 0..1
SUPPLIER_COLORS_PATH = os.environ.get(
    "SUPPLIER_COLORS_PATH",
    str(Path(__file__).resolve().parent / "supplier_colors.json"),
)

# Каталог позиций (как в колонке A): fallback, если прямое нечёткое совпадение не сработало.
# Несколько файлов через запятую.
PRICE_SHEET_CATALOG_PATH = os.environ.get(
    "PRICE_SHEET_CATALOG_PATH",
    str(Path(__file__).resolve().parent / "data" / "price_sheet_catalog.txt"),
)

# Кнопки в боте: список имён через запятую (как в таблице). Пусто = все ключи из supplier_colors.json
SUPPLIER_BUTTONS: list[str] = []
_sb = os.environ.get("SUPPLIER_BUTTONS", "").strip()
if _sb:
    SUPPLIER_BUTTONS = [x.strip() for x in _sb.split(",") if x.strip()]

# Накопление цен по поставщикам для min / 2-й цены между сообщениями
OFFERS_STORE_PATH = os.environ.get(
    "OFFERS_STORE_PATH",
    str(Path(__file__).resolve().parent / "data" / "offers.json"),
)

# Диапазон допустимых значений цены
PRICE_MIN = float(os.environ.get("PRICE_MIN", "100"))
PRICE_MAX = float(os.environ.get("PRICE_MAX", "9999999"))

# Ссылка на справку в /help и при «привет» (README, GitHub — по желанию)
HELP_URL = (os.environ.get("HELP_URL", "") or "").strip()

# Ограничение доступа
ALLOWED_USER_IDS: list[int] = []
_raw = os.environ.get("ALLOWED_USER_IDS", "").strip()
if _raw:
    ALLOWED_USER_IDS = [int(x.strip()) for x in _raw.split(",") if x.strip().isdigit()]
