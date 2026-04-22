"""
Статистика бронирований.
"""

import logging
from aiogram import Router, F
from aiogram.types import Message

from database import db
from keyboards.kb import main_menu

logger = logging.getLogger(__name__)
router = Router()


@router.message(F.text == "📊 Статистика")
async def show_stats(message: Message):
    tg_id = message.from_user.id
    tasks = await db.get_user_autobron_tasks(tg_id)

    total = len(tasks)
    done = sum(1 for t in tasks if t["status"] == "done")
    active = sum(1 for t in tasks if t["status"] == "active")
    archived = sum(1 for t in tasks if t["status"] == "archived")

    # Успешные бронирования
    booked = [t for t in tasks if t.get("booked_date")]
    booked_by_wh: dict[str, int] = {}
    for t in booked:
        wh = t["warehouse_id"]
        booked_by_wh[wh] = booked_by_wh.get(wh, 0) + 1

    lines = [
        "📊 <b>Ваша статистика</b>\n",
        f"📦 Всего заявок: {total}",
        f"✅ Успешно забронировано: {done}",
        f"🟢 Активных заявок: {active}",
        f"📁 В архиве: {archived}",
    ]

    if booked_by_wh:
        lines.append("\n<b>По складам:</b>")
        for wh_id, cnt in sorted(booked_by_wh.items(), key=lambda x: -x[1]):
            lines.append(f"  🏭 Склад {wh_id}: {cnt} брон.")

    if booked:
        lines.append("\n<b>Последние 5 бронирований:</b>")
        for t in booked[-5:]:
            lines.append(f"  ✅ {t['booked_date']} | склад {t['warehouse_id']} | х{t['max_coef']}")

    await message.answer("\n".join(lines), parse_mode="HTML", reply_markup=main_menu())
