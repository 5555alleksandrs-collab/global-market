"""
Конфигурация бота. Все чувствительные данные берутся из .env файла.
"""

import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


@dataclass
class Config:
    BOT_TOKEN: str
    WB_API_TOKEN: str          # Токен продавца из кабинета WB Партнёры
    ADMIN_IDS: list[int]       # Telegram ID администраторов
    DB_PATH: str
    # Интервал опроса WB в секундах (не ставить < 30 — риск бана)
    POLL_INTERVAL: int
    # Включить платёжную систему (YooKassa)
    PAYMENTS_ENABLED: bool
    YOOKASSA_SHOP_ID: str
    YOOKASSA_SECRET_KEY: str


def _parse_admin_ids(raw: str) -> list[int]:
    if not raw:
        return []
    return [int(x.strip()) for x in raw.split(",") if x.strip().isdigit()]


config = Config(
    BOT_TOKEN=os.getenv("BOT_TOKEN", ""),
    WB_API_TOKEN=os.getenv("WB_API_TOKEN", ""),
    ADMIN_IDS=_parse_admin_ids(os.getenv("ADMIN_IDS", "")),
    DB_PATH=os.getenv("DB_PATH", "wb_bot.db"),
    POLL_INTERVAL=int(os.getenv("POLL_INTERVAL", "60")),
    PAYMENTS_ENABLED=os.getenv("PAYMENTS_ENABLED", "false").lower() == "true",
    YOOKASSA_SHOP_ID=os.getenv("YOOKASSA_SHOP_ID", ""),
    YOOKASSA_SECRET_KEY=os.getenv("YOOKASSA_SECRET_KEY", ""),
)

# Валидация обязательных полей
assert config.BOT_TOKEN, "BOT_TOKEN не задан в .env"
assert config.WB_API_TOKEN, "WB_API_TOKEN не задан в .env"
