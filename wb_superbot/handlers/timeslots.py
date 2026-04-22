"""
Поиск таймслотов — уведомления без автоматического бронирования.
"""

import logging
from datetime import date, timedelta, datetime

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from config import config
from database import db
from keyboards.kb import main_menu, supply_type_kb, period_kb, coef_kb
from services.wb_api import WBApiClient, WBApiError

logger = logging.getLogger(__name__)
router = Router()


class TimeslotFSM(StatesGroup):
    choose_warehouse = State()
    choose_supply_type = State()
    choose_period = State()
    enter_custom_range = State()
    choose_coef = State()


@router.message(F.text == "🔍 Поиск таймслотов")
async def timeslot_enter(message: Message, state: FSMContext):
    await state.clear()
    user = await db.get_user(message.from_user.id)
    token = (user.get("wb_token") if user else None) or config.WB_API_TOKEN
    client = WBApiClient(token)

    await message.answer("⏳ Загружаю склады...")
    try:
        warehouses = await client.get_warehouses()
    except WBApiError as e:
        await message.answer(f"❌ Ошибка: {e.message}")
        return

    wh_list = [
        {"id": w.get("ID") or w.get("id"), "name": w.get("name") or w.get("Name", "?")}
        for w in warehouses
        if w.get("ID") or w.get("id")
    ]
    await state.update_data(warehouses=wh_list, token=token)

    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    for wh in wh_list[:30]:
        builder.button(text=wh["name"], callback_data=f"ts_wh:{wh['id']}")
    builder.button(text="❌ Отмена", callback_data="cancel")
    builder.adjust(2)

    await state.set_state(TimeslotFSM.choose_warehouse)
    await message.answer(
        "🏭 <b>Выберите склад:</b>",
        reply_markup=builder.as_markup(),
        parse_mode="HTML",
    )


@router.callback_query(TimeslotFSM.choose_warehouse, F.data.startswith("ts_wh:"))
async def ts_choose_warehouse(callback: CallbackQuery, state: FSMContext):
    wh_id = callback.data.split(":")[1]
    data = await state.get_data()
    wh_name = next(
        (w["name"] for w in data.get("warehouses", []) if str(w["id"]) == wh_id), wh_id
    )
    await state.update_data(warehouse_id=wh_id, warehouse_name=wh_name)
    await state.set_state(TimeslotFSM.choose_supply_type)
    await callback.message.edit_text(
        f"✅ Склад: <b>{wh_name}</b>\n\n📦 <b>Тип поставки:</b>",
        reply_markup=supply_type_kb(),
        parse_mode="HTML",
    )


@router.callback_query(TimeslotFSM.choose_supply_type, F.data.startswith("stype:"))
async def ts_choose_supply_type(callback: CallbackQuery, state: FSMContext):
    stype = callback.data.split(":")[1]
    await state.update_data(supply_type=stype)
    await state.set_state(TimeslotFSM.choose_period)
    await callback.message.edit_text(
        "📅 <b>Период поиска:</b>",
        reply_markup=period_kb(),
        parse_mode="HTML",
    )


@router.callback_query(TimeslotFSM.choose_period, F.data.startswith("period:"))
async def ts_choose_period(callback: CallbackQuery, state: FSMContext):
    ptype = callback.data.split(":")[1]
    today = date.today()

    if ptype == "week":
        await state.update_data(
            date_from=today.isoformat(),
            date_to=(today + timedelta(days=7)).isoformat(),
        )
        await _ts_ask_coef(callback, state)
    elif ptype == "month":
        await state.update_data(
            date_from=today.isoformat(),
            date_to=(today + timedelta(days=30)).isoformat(),
        )
        await _ts_ask_coef(callback, state)
    else:
        await state.set_state(TimeslotFSM.enter_custom_range)
        await callback.message.edit_text(
            "📌 Введите период: <code>05.09.2024-13.09.2024</code>",
            parse_mode="HTML",
        )


@router.message(TimeslotFSM.enter_custom_range)
async def ts_enter_range(message: Message, state: FSMContext):
    raw = message.text.strip()
    try:
        parts = raw.split("-")
        d_from = datetime.strptime(parts[0].strip(), "%d.%m.%Y").date()
        d_to = datetime.strptime(parts[1].strip(), "%d.%m.%Y").date()
    except Exception:
        await message.answer("❌ Формат: <code>05.09.2024-13.09.2024</code>", parse_mode="HTML")
        return
    await state.update_data(date_from=d_from.isoformat(), date_to=d_to.isoformat())
    await state.set_state(TimeslotFSM.choose_coef)
    await message.answer(
        f"✅ Период: {d_from} — {d_to}\n\n📊 <b>Максимальный коэффициент:</b>",
        reply_markup=coef_kb(),
        parse_mode="HTML",
    )


async def _ts_ask_coef(callback: CallbackQuery, state: FSMContext):
    await state.set_state(TimeslotFSM.choose_coef)
    await callback.message.edit_text(
        "📊 <b>Максимальный коэффициент:</b>",
        reply_markup=coef_kb(),
        parse_mode="HTML",
    )


@router.callback_query(TimeslotFSM.choose_coef, F.data.startswith("coef:"))
async def ts_choose_coef(callback: CallbackQuery, state: FSMContext):
    coef = int(callback.data.split(":")[1])
    data = await state.get_data()
    tg_id = callback.from_user.id

    task_id = await db.create_timeslot_task(
        tg_id=tg_id,
        warehouse_id=data["warehouse_id"],
        supply_type=data["supply_type"],
        date_from=data["date_from"],
        date_to=data["date_to"],
        max_coef=coef,
    )
    await state.clear()
    await callback.message.edit_text(
        f"✅ <b>Задача поиска #{task_id} создана!</b>\n\n"
        f"🏭 Склад: {data['warehouse_name']}\n"
        f"📦 Тип: {data['supply_type']}\n"
        f"📅 Период: {data['date_from']} — {data['date_to']}\n"
        f"📊 Коэф: до х{coef}\n\n"
        f"Уведомление придёт как только появится подходящий слот.",
        parse_mode="HTML",
    )
    await callback.message.answer("Главное меню:", reply_markup=main_menu())
