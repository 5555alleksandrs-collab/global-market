"""
Авто-бронирование: полный FSM-поток создания заявки.
Шаги: склад → тип поставки → период → коэффициент → защита → подтверждение
"""

import logging
import asyncio
from datetime import date, timedelta, datetime

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from config import config
from database import db
from keyboards.kb import (
    main_menu, cancel_kb, supply_type_kb,
    period_kb, coef_kb, protection_kb,
)
from services.wb_api import WBApiClient, WBApiError

logger = logging.getLogger(__name__)
router = Router()


class AutobronFSM(StatesGroup):
    choose_warehouse = State()
    choose_supply_type = State()
    choose_period = State()
    enter_custom_dates = State()
    enter_custom_range = State()
    choose_coef = State()
    choose_protection = State()
    enter_draft_id = State()
    confirm = State()


def _progress(step: int, total: int = 6) -> str:
    done = "🟩" * step
    left = "⬜" * (total - step)
    return f"Прогресс: {done}{left} ({step}/{total})"


# ─── ВХОД ─────────────────────────────────────────────────────────────────────

@router.message(F.text == "⚡ Авто-бронь")
async def autobron_enter(message: Message, state: FSMContext):
    await state.clear()
    user = await db.get_user(message.from_user.id)
    if not user:
        await message.answer("Сначала запустите /start")
        return

    token = user.get("wb_token") or config.WB_API_TOKEN
    client = WBApiClient(token)

    await message.answer("⏳ Загружаю список складов WB...")
    try:
        warehouses = await client.get_warehouses()
    except WBApiError as e:
        await message.answer(f"❌ Ошибка получения складов: {e.message}\nПроверьте токен (/settoken)")
        return

    if not warehouses:
        await message.answer("❌ Список складов пуст.")
        return

    # Сохраняем склады в state для выбора
    wh_list = [
        {"id": w.get("ID") or w.get("id"), "name": w.get("name") or w.get("Name", "?")}
        for w in warehouses
        if w.get("ID") or w.get("id")
    ]
    await state.update_data(warehouses=wh_list, token=token)

    # Формируем кнопки складов (инлайн)
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    for wh in wh_list[:30]:  # максимум 30
        builder.button(text=wh["name"], callback_data=f"wh:{wh['id']}")
    builder.button(text="❌ Отмена", callback_data="cancel")
    builder.adjust(2)

    await state.set_state(AutobronFSM.choose_warehouse)
    await message.answer(
        f"📝 <b>Новая заявка на авто-бронь</b>\n{_progress(1)}\n\n"
        f"🏭 <b>Шаг 1/6: выберите склад для поставки</b>",
        reply_markup=builder.as_markup(),
        parse_mode="HTML",
    )


@router.callback_query(AutobronFSM.choose_warehouse, F.data.startswith("wh:"))
async def choose_warehouse(callback: CallbackQuery, state: FSMContext):
    wh_id = callback.data.split(":")[1]
    data = await state.get_data()
    wh_name = next(
        (w["name"] for w in data.get("warehouses", []) if str(w["id"]) == wh_id),
        wh_id,
    )
    await state.update_data(warehouse_id=wh_id, warehouse_name=wh_name)
    await state.set_state(AutobronFSM.choose_supply_type)
    await callback.message.edit_text(
        f"✅ Склад: <b>{wh_name}</b>\n{_progress(2)}\n\n"
        f"📦 <b>Шаг 2/6: выберите тип поставки</b>",
        reply_markup=supply_type_kb(),
        parse_mode="HTML",
    )


@router.callback_query(AutobronFSM.choose_supply_type, F.data.startswith("stype:"))
async def choose_supply_type(callback: CallbackQuery, state: FSMContext):
    stype = callback.data.split(":")[1]
    labels = {"box": "📦 Короб", "pallet": "🪵 Монопаллета", "supersafe": "🔒 Суперсейф"}
    await state.update_data(supply_type=stype, supply_type_label=labels.get(stype, stype))
    await state.set_state(AutobronFSM.choose_period)
    await callback.message.edit_text(
        f"✅ Тип: <b>{labels.get(stype)}</b>\n{_progress(3)}\n\n"
        f"📅 <b>Шаг 3/6: выберите период поиска</b>",
        reply_markup=period_kb(),
        parse_mode="HTML",
    )


@router.callback_query(AutobronFSM.choose_period, F.data.startswith("period:"))
async def choose_period(callback: CallbackQuery, state: FSMContext):
    ptype = callback.data.split(":")[1]
    today = date.today()

    if ptype == "week":
        date_from = today.isoformat()
        date_to = (today + timedelta(days=7)).isoformat()
        await state.update_data(date_from=date_from, date_to=date_to)
        await _ask_coef(callback, state)

    elif ptype == "month":
        date_from = today.isoformat()
        date_to = (today + timedelta(days=30)).isoformat()
        await state.update_data(date_from=date_from, date_to=date_to)
        await _ask_coef(callback, state)

    elif ptype == "custom_dates":
        await state.set_state(AutobronFSM.enter_custom_dates)
        await callback.message.edit_text(
            f"{_progress(3)}\n\n"
            "✏️ Введите конкретные даты через запятую:\n"
            "<code>20.08.2024, 09.09.2024, 15.09.2024</code>\n\n"
            "⚠️ 1 дата = 1 авто-бронь",
            parse_mode="HTML",
        )

    elif ptype == "custom_range":
        await state.set_state(AutobronFSM.enter_custom_range)
        await callback.message.edit_text(
            f"{_progress(3)}\n\n"
            "📌 Введите период в формате:\n"
            "<code>05.09.2024-13.09.2024</code>\n\n"
            "Без пробелов! Бот забронирует <b>одну</b> дату из этого периода.",
            parse_mode="HTML",
        )


@router.message(AutobronFSM.enter_custom_dates)
async def enter_custom_dates(message: Message, state: FSMContext):
    raw = message.text.strip()
    dates = []
    for part in raw.split(","):
        part = part.strip()
        try:
            d = datetime.strptime(part, "%d.%m.%Y").date()
            dates.append(d.isoformat())
        except ValueError:
            pass

    if not dates:
        await message.answer("❌ Не удалось распознать даты. Формат: 20.08.2024, 09.09.2024")
        return

    # Берём диапазон
    dates.sort()
    await state.update_data(
        date_from=dates[0],
        date_to=dates[-1],
        custom_dates=dates,
    )

    # Создадим фейковый callback для перехода к коэф
    await state.set_state(AutobronFSM.choose_coef)
    await message.answer(
        f"✅ Даты: {', '.join(dates)}\n{_progress(4)}\n\n"
        f"📊 <b>Шаг 4/6: выберите максимальный коэффициент</b>",
        reply_markup=coef_kb(),
        parse_mode="HTML",
    )


@router.message(AutobronFSM.enter_custom_range)
async def enter_custom_range(message: Message, state: FSMContext):
    raw = message.text.strip()
    try:
        parts = raw.split("-")
        if len(parts) != 2:
            raise ValueError
        d_from = datetime.strptime(parts[0].strip(), "%d.%m.%Y").date()
        d_to = datetime.strptime(parts[1].strip(), "%d.%m.%Y").date()
        if d_from > d_to:
            raise ValueError("from > to")
    except Exception:
        await message.answer(
            "❌ Неверный формат. Пример: <code>05.09.2024-13.09.2024</code>",
            parse_mode="HTML",
        )
        return

    await state.update_data(date_from=d_from.isoformat(), date_to=d_to.isoformat())
    await state.set_state(AutobronFSM.choose_coef)
    await message.answer(
        f"✅ Период: {d_from} — {d_to}\n{_progress(4)}\n\n"
        f"📊 <b>Шаг 4/6: выберите максимальный коэффициент</b>",
        reply_markup=coef_kb(),
        parse_mode="HTML",
    )


async def _ask_coef(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AutobronFSM.choose_coef)
    data = await state.get_data()
    await callback.message.edit_text(
        f"✅ Период: {data['date_from']} — {data['date_to']}\n{_progress(4)}\n\n"
        f"📊 <b>Шаг 4/6: выберите максимальный коэффициент</b>",
        reply_markup=coef_kb(),
        parse_mode="HTML",
    )


@router.callback_query(AutobronFSM.choose_coef, F.data.startswith("coef:"))
async def choose_coef(callback: CallbackQuery, state: FSMContext):
    coef = int(callback.data.split(":")[1])
    await state.update_data(max_coef=coef)
    await state.set_state(AutobronFSM.choose_protection)
    await callback.message.edit_text(
        f"✅ Коэффициент: до х{coef}\n{_progress(5)}\n\n"
        f"🛡 <b>Шаг 5/6: настройка защиты</b>",
        reply_markup=protection_kb(),
        parse_mode="HTML",
    )


@router.callback_query(AutobronFSM.choose_protection, F.data.startswith("prot:"))
async def choose_protection(callback: CallbackQuery, state: FSMContext):
    prot = int(callback.data.split(":")[1])
    await state.update_data(protection=prot)
    await state.set_state(AutobronFSM.enter_draft_id)
    await callback.message.edit_text(
        f"{_progress(6)}\n\n"
        "🗒 <b>Шаг 6/6:</b> введите <b>ID черновика</b> поставки из ЛК WB:\n\n"
        "<i>Поставки → Черновики → ID поставки (число)</i>\n\n"
        "Или введите <b>название</b> — бот создаст новый черновик.",
        parse_mode="HTML",
    )


@router.message(AutobronFSM.enter_draft_id)
async def enter_draft_id(message: Message, state: FSMContext):
    draft_id = message.text.strip()
    if not draft_id:
        await message.answer("❌ Введите ID черновика.")
        return
    await state.update_data(draft_id=draft_id)

    data = await state.get_data()
    prot_label = "🛡 Включена (+72ч)" if data["protection"] else "⚡ Выключена"

    summary = (
        f"{_progress(6)}\n\n"
        f"📋 <b>Подтверждение заявки:</b>\n\n"
        f"🏭 Склад: <b>{data['warehouse_name']}</b>\n"
        f"📦 Тип: <b>{data['supply_type_label']}</b>\n"
        f"📅 Период: <b>{data['date_from']} — {data['date_to']}</b>\n"
        f"📊 Коэффициент: <b>до х{data['max_coef']}</b>\n"
        f"🛡 Защита: <b>{prot_label}</b>\n"
        f"🗒 Черновик: <code>{draft_id}</code>\n\n"
        f"Создать заявку?"
    )

    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Создать", callback_data="ab_confirm")
    builder.button(text="❌ Отмена", callback_data="cancel")
    builder.adjust(2)

    await state.set_state(AutobronFSM.confirm)
    await message.answer(summary, reply_markup=builder.as_markup(), parse_mode="HTML")


@router.callback_query(AutobronFSM.confirm, F.data == "ab_confirm")
async def confirm_autobron(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    tg_id = callback.from_user.id
    await callback.message.edit_text(
        "⏳ Создаю заявку...\n"
        "▱▱▱"
    )
    await asyncio.sleep(0.5)
    await callback.message.edit_text(
        "⏳ Создаю заявку...\n"
        "▰▰▱"
    )
    await asyncio.sleep(0.5)

    task_id = await db.create_autobron_task(
        tg_id=tg_id,
        draft_id=data["draft_id"],
        warehouse_id=data["warehouse_id"],
        supply_type=data["supply_type"],
        date_from=data["date_from"],
        date_to=data["date_to"],
        max_coef=data["max_coef"],
        protection=data["protection"],
    )

    await state.clear()
    await callback.message.edit_text(
        f"✅ <b>Заявка #{task_id} создана!</b>\n"
        f"Прогресс: 🟩🟩🟩🟩🟩🟩 (6/6)\n\n"
        f"Бот начнёт поиск слотов в ближайшие минуты.\n"
        f"Уведомление придёт сюда как только поставка будет забронирована.",
        parse_mode="HTML",
    )
    await callback.message.answer("Главное меню:", reply_markup=main_menu())


# ─── СПИСОК ЗАПРОСОВ ─────────────────────────────────────────────────────────

@router.message(F.text == "📋 Список запросов")
async def show_tasks(message: Message):
    tg_id = message.from_user.id
    tasks = await db.get_user_autobron_tasks(tg_id)

    if not tasks:
        await message.answer("📭 У вас нет активных заявок.", reply_markup=main_menu())
        return

    active = [t for t in tasks if t["status"] == "active"]
    done = [t for t in tasks if t["status"] == "done"]
    archived = [t for t in tasks if t["status"] == "archived"]

    lines = [f"📋 <b>Ваши заявки:</b> активных {len(active)}, архив {len(archived)+len(done)}\n"]
    for t in tasks[:15]:
        icon = {"active": "📦", "done": "✅", "archived": "📁"}.get(t["status"], "?")
        lines.append(
            f"{icon} <b>#{t['id']}</b> | склад {t['warehouse_id']} | "
            f"{t['date_from'][:10]}–{t['date_to'][:10]} | х{t['max_coef']}"
        )

    from keyboards.kb import tasks_list_kb
    await message.answer(
        "\n".join(lines),
        reply_markup=tasks_list_kb(tasks[:15]),
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("task:"))
async def task_detail(callback: CallbackQuery):
    task_id = int(callback.data.split(":")[1])
    tasks = await db.get_user_autobron_tasks(callback.from_user.id)
    t = next((x for x in tasks if x["id"] == task_id), None)
    if not t:
        await callback.answer("Задача не найдена", show_alert=True)
        return

    prot = "🛡 Включена" if t["protection"] else "⚡ Выключена"
    status_map = {"active": "🟢 Активна", "done": "✅ Выполнена", "archived": "📁 Архив"}
    text = (
        f"📋 <b>Заявка #{t['id']}</b>\n\n"
        f"Статус: {status_map.get(t['status'], t['status'])}\n"
        f"🏭 Склад: {t['warehouse_id']}\n"
        f"📦 Тип: {t['supply_type']}\n"
        f"📅 Период: {t['date_from']} — {t['date_to']}\n"
        f"📊 Коэффициент: до х{t['max_coef']}\n"
        f"🛡 Защита: {prot}\n"
        f"🗒 Черновик: {t['draft_id']}\n"
        f"🕐 Создана: {t['created_at'][:16]}\n"
    )
    if t.get("booked_date"):
        text += f"✅ Забронирована: {t['booked_date']}\n"

    from keyboards.kb import task_actions_kb
    await callback.message.edit_text(text, reply_markup=task_actions_kb(task_id), parse_mode="HTML")


@router.callback_query(F.data.startswith("del_task:"))
async def delete_task(callback: CallbackQuery):
    task_id = int(callback.data.split(":")[1])
    tg_id = callback.from_user.id
    ok = await db.delete_autobron_task(task_id, tg_id)
    if ok:
        await callback.message.edit_text(
            f"🗑 Заявка #{task_id} удалена. Авто-бронь возвращена на баланс (если была активной)."
        )
    else:
        await callback.answer("❌ Не удалось удалить.", show_alert=True)


@router.callback_query(F.data == "cancel")
async def cancel_handler(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.delete()
