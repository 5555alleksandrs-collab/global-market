"""
WB SuperBot — Telegram бот для авто-бронирования поставок на Wildberries
Запуск: python main.py
"""

import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from config import config
from handlers import start, autobron, timeslots, redistribution
from handlers import statistics
from services.scheduler import start_scheduler
from database.db import init_db
from middlewares import AccessMiddleware

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("bot.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)


async def main():
    logger.info("Запуск WB SuperBot...")

    await init_db()

    bot = Bot(token=config.BOT_TOKEN)
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)
    access_middleware = AccessMiddleware()
    dp.message.middleware(access_middleware)
    dp.callback_query.middleware(access_middleware)

    # Регистрация роутеров
    dp.include_router(start.router)
    dp.include_router(autobron.router)
    dp.include_router(timeslots.router)
    dp.include_router(redistribution.router)
    dp.include_router(statistics.router)

    # Запуск планировщика задач
    scheduler = await start_scheduler(bot)

    logger.info("Бот запущен. Polling...")
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        scheduler.shutdown()
        await bot.session.close()
        logger.info("Бот остановлен.")


if __name__ == "__main__":
    asyncio.run(main())
