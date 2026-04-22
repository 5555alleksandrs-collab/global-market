"""
Перераспределение остатков между складами WB.
"""

import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from config import config
from database import db
from keyboards.kb import main_menu
from services.wb_api import WBApiClient, WBApiError

logger = logging.getLogger(__name__)
router = Router()


class RedistFSM(StatesGroup):
    enter_article = State()
    choose_from_warehouse = State()
    choose_to_warehouse = State()
    enter_quantity = State()
    confirm = State()


@router.message(F.text == "🔄 Перераспределение")
async def redist_enter(message: Message, state: FSMContext):
    await state.clear()
    user = await db.get_user(message.from_user.id)
    token = (user.get("wb_token") if user else None) or config.WB_API_TOKEN
    client = WBApiClient(token)

    await message.answer("⏳ Загружаю данные...")
    try:
        warehouses = await client.get_warehouses()
    except WBApiError as e:
        await message.answer(f"❌ Ошибка API: {e.message}")
        return

    wh_list = [
        {"id": w.get("ID") or w.get("id"), "name": w.get("name") or w.get("Name", "?")}
        for w in warehouses
        if w.get("ID") or w.get("id")
    ]
    await state.update_data(warehouses=wh_list, token=token)
    await state.set_state(RedistFSM.enter_article)
    await message.answer(
        "🔄 <b>Перераспределение остатков</b>\n\n"
        "Введите <b>артикул продавца</b> товара для перемещения:",
        parse_mode="HTML",
    )


@router.message(RedistFSM.enter_article)
async def redist_article(message: Message, state: FSMContext):
    article = message.text.strip()
    if not article:
        await message.answer("❌ Введите артикул.")
        return
    await state.update_data(article=article)

    data = await state.get_data()
    wh_list = data.get("warehouses", [])

    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    for wh in wh_list[:30]:
        builder.button(text=wh["name"], callback_data=f"rd_from:{wh['id']}")
    builder.button(text="❌ Отмена", callback_data="cancel")
    builder.adjust(2)

    await state.set_state(RedistFSM.choose_from_warehouse)
    await message.answer(
        f"✅ Артикул: <code>{article}</code>\n\n"
        f"🏭 <b>Откуда перемещаем (склад-источник)?</b>",
        reply_markup=builder.as_markup(),
        parse_mode="HTML",
    )


@router.callback_query(RedistFSM.choose_from_warehouse, F.data.startswith("rd_from:"))
async def redist_from_warehouse(callback: CallbackQuery, state: FSMContext):
    wh_id = callback.data.split(":")[1]
    data = await state.get_data()
    wh_name = next(
        (w["name"] for w in data.get("warehouses", []) if str(w["id"]) == wh_id), wh_id
    )
    await state.update_data(from_warehouse=wh_id, from_warehouse_name=wh_name)

    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    for wh in data.get("warehouses", [])[:30]:
        if str(wh["id"]) == wh_id:
            continue  # нельзя перемещать на тот же склад
        builder.button(text=wh["name"], callback_data=f"rd_to:{wh['id']}")
    builder.button(text="❌ Отмена", callback_data="cancel")
    builder.adjust(2)

    await state.set_state(RedistFSM.choose_to_warehouse)
    await callback.message.edit_text(
        f"✅ Откуда: <b>{wh_name}</b>\n\n"
        f"🏭 <b>Куда перемещаем (склад-получатель)?</b>",
        reply_markup=builder.as_markup(),
        parse_mode="HTML",
    )


@router.callback_query(RedistFSM.choose_to_warehouse, F.data.startswith("rd_to:"))
async def redist_to_warehouse(callback: CallbackQuery, state: FSMContext):
    wh_id = callback.data.split(":")[1]
    data = await state.get_data()
    wh_name = next(
        (w["name"] for w in data.get("warehouses", []) if str(w["id"]) == wh_id), wh_id
    )
    await state.update_data(to_warehouse=wh_id, to_warehouse_name=wh_name)
    await state.set_state(RedistFSM.enter_quantity)
    await callback.message.edit_text(
        f"✅ Куда: <b>{wh_name}</b>\n\n"
        f"📦 Введите <b>количество товара</b> для перемещения (штук):",
        parse_mode="HTML",
    )


@router.message(RedistFSM.enter_quantity)
async def redist_quantity(message: Message, state: FSMContext):
    try:
        qty = int(message.text.strip())
        if qty <= 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ Введите целое положительное число.")
        return

    await state.update_data(quantity=qty)
    data = await state.get_data()

    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Создать заявку", callback_data="rd_confirm")
    builder.button(text="❌ Отмена", callback_data="cancel")
    builder.adjust(2)

    await state.set_state(RedistFSM.confirm)
    await message.answer(
        f"📋 <b>Подтверждение перераспределения:</b>\n\n"
        f"📦 Артикул: <code>{data['article']}</code>\n"
        f"📤 Откуда: <b>{data['from_warehouse_name']}</b>\n"
        f"📥 Куда: <b>{data['to_warehouse_name']}</b>\n"
        f"🔢 Количество: <b>{qty} шт.</b>\n\n"
        f"⚠️ Перераспределение доступно только при наличии квот WB.",
        reply_markup=builder.as_markup(),
        parse_mode="HTML",
    )


@router.callback_query(RedistFSM.confirm, F.data == "rd_confirm")
async def redist_confirm(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    tg_id = callback.from_user.id

    task_id = await db.create_redistribution_task(
        tg_id=tg_id,
        article=data["article"],
        from_warehouse=data["from_warehouse"],
        to_warehouse=data["to_warehouse"],
        quantity=data["quantity"],
    )
    await state.clear()
    await callback.message.edit_text(
        f"✅ <b>Заявка #{task_id} на перераспределение создана!</b>\n\n"
        f"Бот будет отслеживать доступность квот и выполнит перемещение автоматически.\n"
        f"Уведомление придёт по результату.",
        parse_mode="HTML",
    )
    await callback.message.answer("Главное меню:", reply_markup=main_menu())
