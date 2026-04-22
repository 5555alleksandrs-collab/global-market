"""
Планировщик фоновых задач:
- Поиск и бронирование слотов (авто-бронь)
- Поиск таймслотов (уведомления)
- Поиск лимитов перераспределения
"""

import logging
from datetime import datetime, date, timedelta, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from aiogram import Bot

from config import config
from database import db
from services.wb_api import WBApiClient, WBApiError

logger = logging.getLogger(__name__)

PROTECTION_HOURS = 72  # защита — не бронировать раньше чем через 72ч


async def _process_autobron_tasks(bot: Bot):
    """Главный цикл авто-бронирования."""
    tasks = await db.get_active_autobron_tasks()
    if not tasks:
        return

    logger.info("Авто-бронь: обрабатываю %d активных заявок", len(tasks))
    now = datetime.now(tz=timezone.utc)

    for task in tasks:
        tg_id = task["tg_id"]
        token = task.get("wb_token") or config.WB_API_TOKEN
        client = WBApiClient(token)

        date_from = date.fromisoformat(task["date_from"])
        date_to = date.fromisoformat(task["date_to"])
        today = now.date()

        # Период ушёл в прошлое → архивируем, возвращаем бронь
        if date_to < today:
            await db.archive_autobron_task(task["id"])
            await db.add_autobrons(tg_id, 1)
            await _notify(
                bot, tg_id,
                f"⏰ Заявка #{task['id']} истекла — период {task['date_from']}–{task['date_to']} "
                f"прошёл. Авто-бронь возвращена на баланс."
            )
            continue

        # Защита: не бронировать ближайшие 72ч
        effective_from = date_from
        if task["protection"]:
            earliest = (now + timedelta(hours=PROTECTION_HOURS)).date()
            if earliest > date_to:
                logger.debug("Заявка %d: все даты в зоне защиты, пропускаем", task["id"])
                continue
            effective_from = max(date_from, earliest)

        try:
            slots = await client.find_available_slots(
                warehouse_id=int(task["warehouse_id"]),
                supply_type=task["supply_type"],
                date_from=effective_from,
                date_to=date_to,
                max_coef=task["max_coef"],
            )
        except WBApiError as e:
            logger.warning("Заявка %d: ошибка API %s", task["id"], e)
            if e.status in (401, 403):
                await _notify(bot, tg_id, f"❌ Заявка #{task['id']}: ошибка авторизации WB ({e.status}). Проверьте токен.")
            continue
        except Exception as e:
            logger.exception("Заявка %d: неожиданная ошибка %s", task["id"], e)
            continue

        if not slots:
            logger.debug("Заявка %d: подходящих слотов нет", task["id"])
            continue

        best = slots[0]
        slot_date_str = best["date"] + "T00:00:00Z"

        try:
            await client.book_supply_timeslot(
                supply_id=task["draft_id"],
                warehouse_id=int(task["warehouse_id"]),
                supply_date=slot_date_str,
            )
        except WBApiError as e:
            logger.warning("Заявка %d: не удалось забронировать %s — %s", task["id"], best["date"], e)
            await _notify(
                bot, tg_id,
                f"⚠️ Заявка #{task['id']}: найден слот {best['date']} (х{best['coefficient']}), "
                f"но бронирование не прошло: {e.message}"
            )
            continue

        # Успешно забронировали
        await db.complete_autobron_task(task["id"], best["date"])
        await _notify(
            bot, tg_id,
            f"✅ <b>Поставка забронирована!</b>\n"
            f"📦 Черновик: <code>{task['draft_id']}</code>\n"
            f"🏭 Склад ID: {task['warehouse_id']}\n"
            f"📅 Дата: <b>{best['date']}</b>\n"
            f"📊 Коэффициент: х{best['coefficient']}\n"
            f"🔖 Тип: {task['supply_type']}\n\n"
            f"Перейдите в ЛК WB → Поставки → заполните упаковку и пропуск."
        )
        logger.info("Заявка %d успешно забронирована на %s", task["id"], best["date"])


async def _process_timeslot_tasks(bot: Bot):
    """Поиск таймслотов (уведомления без бронирования)."""
    tasks = await db.get_active_timeslot_tasks()
    if not tasks:
        return

    now_date = datetime.now(tz=timezone.utc).date()
    for task in tasks:
        tg_id = task["tg_id"]
        token = task.get("wb_token") or config.WB_API_TOKEN
        client = WBApiClient(token)

        date_from = date.fromisoformat(task["date_from"])
        date_to = date.fromisoformat(task["date_to"])

        if date_to < now_date:
            # Период истёк
            async with __import__("aiosqlite").connect(__import__("config").config.DB_PATH) as db_conn:
                await db_conn.execute(
                    "UPDATE timeslot_tasks SET status='done' WHERE id=?", (task["id"],)
                )
                await db_conn.commit()
            continue

        try:
            slots = await client.find_available_slots(
                warehouse_id=int(task["warehouse_id"]),
                supply_type=task["supply_type"],
                date_from=max(date_from, now_date),
                date_to=date_to,
                max_coef=task["max_coef"],
            )
        except Exception as e:
            logger.warning("Таймслот-задача %d: ошибка %s", task["id"], e)
            continue

        if not slots:
            continue

        lines = "\n".join(
            f"  📅 {s['date']} — х{s['coefficient']}"
            for s in slots[:10]
        )
        await _notify(
            bot, tg_id,
            f"🔔 <b>Найден таймслот!</b>\n"
            f"🏭 Склад ID: {task['warehouse_id']}\n"
            f"📦 Тип: {task['supply_type']}\n\n"
            f"{lines}\n\n"
            f"Перейдите в ЛК WB и забронируйте вручную, или создайте авто-бронь."
        )

        # Таймслот-поиск — одноразовый, помечаем как выполненный
        async with __import__("aiosqlite").connect(__import__("config").config.DB_PATH) as db_conn:
            await db_conn.execute(
                "UPDATE timeslot_tasks SET status='done' WHERE id=?", (task["id"],)
            )
            await db_conn.commit()


async def _process_redistribution_tasks(bot: Bot):
    """Мониторинг заявок на перераспределение."""
    tasks = await db.get_active_redistribution_tasks()
    if not tasks:
        return

    for task in tasks:
        tg_id = task["tg_id"]
        token = task.get("wb_token") or config.WB_API_TOKEN
        client = WBApiClient(token)

        try:
            result = await client.create_redistribution(
                article=task["article"],
                from_warehouse_id=int(task["from_warehouse"]),
                to_warehouse_id=int(task["to_warehouse"]),
                quantity=task["quantity"],
            )
            # Успешно
            async with __import__("aiosqlite").connect(__import__("config").config.DB_PATH) as db_conn:
                await db_conn.execute(
                    "UPDATE redistribution_tasks SET status='done' WHERE id=?", (task["id"],)
                )
                await db_conn.commit()

            await _notify(
                bot, tg_id,
                f"✅ <b>Перераспределение выполнено!</b>\n"
                f"📦 Артикул: {task['article']}\n"
                f"🔄 {task['from_warehouse']} → {task['to_warehouse']}\n"
                f"📊 Количество: {task['quantity']} шт."
            )
        except WBApiError as e:
            if "квот" in e.message.lower() or e.status == 429:
                logger.debug("Перераспределение %d: нет квот, ждём", task["id"])
            else:
                logger.warning("Перераспределение %d: ошибка %s", task["id"], e)
        except Exception as e:
            logger.exception("Перераспределение %d: ошибка %s", task["id"], e)


async def _notify(bot: Bot, tg_id: int, text: str):
    try:
        await bot.send_message(tg_id, text, parse_mode="HTML")
    except Exception as e:
        logger.warning("Не удалось отправить уведомление %d: %s", tg_id, e)


async def start_scheduler(bot: Bot) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler()

    interval = config.POLL_INTERVAL

    scheduler.add_job(
        _process_autobron_tasks,
        "interval",
        seconds=interval,
        args=[bot],
        id="autobron",
        max_instances=1,
        coalesce=True,
    )
    scheduler.add_job(
        _process_timeslot_tasks,
        "interval",
        seconds=interval,
        args=[bot],
        id="timeslots",
        max_instances=1,
        coalesce=True,
    )
    scheduler.add_job(
        _process_redistribution_tasks,
        "interval",
        seconds=max(interval * 2, 120),
        args=[bot],
        id="redistribution",
        max_instances=1,
        coalesce=True,
    )

    scheduler.start()
    logger.info(
        "Планировщик запущен. Интервал опроса: %d сек.", interval
    )
    return scheduler
