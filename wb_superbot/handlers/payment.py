"""
Оплата: подписка и авто-брони.
Поддерживается YooKassa (если включена в конфиге) и ручное пополнение админом.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from config import config
from database import db
from keyboards.kb import main_menu, payment_kb, confirm_payment_kb, TARIFF_SUBSCRIPTION, TARIFF_AUTOBRON

logger = logging.getLogger(__name__)
router = Router()


@router.message(F.text == "💳 Подписка и оплата")
async def payment_enter(message: Message):
    tg_id = message.from_user.id
    user = await db.get_user(tg_id)

    balance = user.get("autobrons", 0) if user else 0
    sub_until = user.get("sub_until", "") if user else ""
    subscribed = user.get("subscribed", 0) if user else 0

    sub_status = (
        f"✅ Активна до {sub_until[:10]}" if subscribed and sub_until
        else "❌ Не активна"
    )

    await message.answer(
        f"💳 <b>Подписка и оплата</b>\n\n"
        f"📌 Подписка: {sub_status}\n"
        f"⚡ Авто-брони: <b>{balance} шт.</b>\n\n"
        f"<b>Тарифы:</b>\n"
        f"• Подписка 30 дней — {TARIFF_SUBSCRIPTION}₽\n"
        f"• 1 авто-бронь — 310₽\n"
        f"• 5 авто-броней — 1050₽\n"
        f"• 10 авто-броней — 1890₽\n"
        f"• 30 авто-броней — 5250₽\n\n"
        f"⚠️ Авто-бронирование без подписки не работает.\n"
        f"Оплата через ЮКассу (карты РФ, SberPay, ЮMoney).",
        reply_markup=payment_kb(),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "pay:sub")
async def pay_subscription(callback: CallbackQuery):
    tg_id = callback.from_user.id
    amount = TARIFF_SUBSCRIPTION

    if config.PAYMENTS_ENABLED:
        payment_url = await _create_yookassa_payment(
            tg_id=tg_id,
            amount=amount,
            description="Подписка WB SuperBot на 30 дней",
            metadata={"service": "subscription"},
        )
        if payment_url:
            pay_db_id = await db.record_payment(tg_id, amount, "subscription")
            from aiogram.types import InlineKeyboardMarkup
            from aiogram.utils.keyboard import InlineKeyboardBuilder
            builder = InlineKeyboardBuilder()
            builder.button(text=f"💳 Оплатить {amount}₽", url=payment_url)
            builder.button(text="✅ Оплатил, проверить", callback_data=f"check_pay:{pay_db_id}")
            builder.button(text="❌ Отмена", callback_data="cancel")
            builder.adjust(1)
            await callback.message.edit_text(
                f"💳 <b>Оплата подписки — {amount}₽</b>\n\n"
                f"1. Нажмите кнопку «Оплатить»\n"
                f"2. Оплатите картой РФ / SberPay / ЮMoney\n"
                f"3. Вернитесь и нажмите «Оплатил, проверить»",
                reply_markup=builder.as_markup(),
                parse_mode="HTML",
            )
            return

    # Если ЮКасса не настроена — показываем заглушку
    await callback.message.edit_text(
        f"⚠️ <b>Оплата временно недоступна</b>\n\n"
        f"Обратитесь к администратору для активации подписки.\n"
        f"Стоимость: {amount}₽",
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("pay:ab:"))
async def pay_autobron(callback: CallbackQuery):
    _, _, count_str, price_str = callback.data.split(":")
    count = int(count_str)
    amount = int(price_str)
    tg_id = callback.from_user.id

    if config.PAYMENTS_ENABLED:
        payment_url = await _create_yookassa_payment(
            tg_id=tg_id,
            amount=amount,
            description=f"{count} авто-брон{'ь' if count == 1 else 'и'} WB SuperBot",
            metadata={"service": f"autobron_{count}"},
        )
        if payment_url:
            pay_db_id = await db.record_payment(tg_id, amount, f"autobron_{count}")
            from aiogram.utils.keyboard import InlineKeyboardBuilder
            builder = InlineKeyboardBuilder()
            builder.button(text=f"💳 Оплатить {amount}₽", url=payment_url)
            builder.button(text="✅ Оплатил, проверить", callback_data=f"check_pay:{pay_db_id}")
            builder.button(text="❌ Отмена", callback_data="cancel")
            builder.adjust(1)
            await callback.message.edit_text(
                f"💳 <b>Оплата {count} авто-бронь — {amount}₽</b>\n\n"
                f"1. Нажмите «Оплатить»\n"
                f"2. Оплатите любым удобным способом\n"
                f"3. Нажмите «Оплатил, проверить»",
                reply_markup=builder.as_markup(),
                parse_mode="HTML",
            )
            return

    await callback.message.edit_text(
        f"⚠️ <b>Оплата временно недоступна</b>\n\n"
        f"Обратитесь к администратору.\n"
        f"Стоимость: {amount}₽ за {count} авто-бронь.",
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("check_pay:"))
async def check_payment(callback: CallbackQuery):
    """
    Проверка оплаты. При включённой ЮКассе — делаем запрос к API.
    При выключённой — только для администраторов через /addabron.
    """
    pay_db_id = int(callback.data.split(":")[1])
    tg_id = callback.from_user.id

    if config.PAYMENTS_ENABLED:
        # TODO: реализовать проверку через YooKassa API
        # Сейчас — заглушка
        await callback.answer(
            "⏳ Проверяем оплату... Если оплата прошла, средства зачислятся автоматически.",
            show_alert=True,
        )
    else:
        await callback.answer(
            "⚠️ Платёжная система не настроена. Обратитесь к администратору.",
            show_alert=True,
        )


@router.callback_query(F.data == "pay:history")
async def pay_history(callback: CallbackQuery):
    tg_id = callback.from_user.id
    payments = await db.get_payment_history(tg_id)

    if not payments:
        await callback.message.edit_text("📋 История оплат пуста.")
        return

    lines = ["📋 <b>История оплат:</b>\n"]
    for p in payments:
        icon = "✅" if p["status"] == "paid" else ("⏳" if p["status"] == "pending" else "❌")
        lines.append(f"{icon} {p['created_at'][:10]} — {p['amount']}₽ — {p['service']}")

    await callback.message.edit_text("\n".join(lines), parse_mode="HTML")


# ─── АДМИН-КОМАНДЫ ────────────────────────────────────────────────────────────

@router.message(F.text.startswith("/addabron"))
async def admin_add_abron(message: Message):
    """
    /addabron <user_id> <count>
    Добавляет авто-брони пользователю (только для администраторов).
    """
    if message.from_user.id not in config.ADMIN_IDS:
        return

    parts = message.text.split()
    if len(parts) != 3:
        await message.answer("Формат: /addabron <user_id> <count>")
        return

    try:
        target_id = int(parts[1])
        count = int(parts[2])
    except ValueError:
        await message.answer("❌ Неверные параметры.")
        return

    await db.add_autobrons(target_id, count)
    await db.record_payment(target_id, 0, f"admin_gift_{count}", "admin")
    await message.answer(f"✅ Пользователю {target_id} добавлено {count} авто-броней.")

    # Уведомляем пользователя
    try:
        await message.bot.send_message(
            target_id,
            f"⚡ Вам начислено <b>{count} авто-броней</b>!",
            parse_mode="HTML",
        )
    except Exception:
        pass


@router.message(F.text.startswith("/addsub"))
async def admin_add_sub(message: Message):
    """
    /addsub <user_id> <days>
    Активирует подписку пользователю.
    """
    if message.from_user.id not in config.ADMIN_IDS:
        return

    parts = message.text.split()
    if len(parts) != 3:
        await message.answer("Формат: /addsub <user_id> <days>")
        return

    try:
        target_id = int(parts[1])
        days = int(parts[2])
    except ValueError:
        await message.answer("❌ Неверные параметры.")
        return

    until = (datetime.now() + timedelta(days=days)).isoformat()
    import aiosqlite
    async with aiosqlite.connect(config.DB_PATH) as db_conn:
        await db_conn.execute(
            "UPDATE users SET subscribed=1, sub_until=? WHERE tg_id=?",
            (until, target_id),
        )
        await db_conn.commit()

    await message.answer(f"✅ Пользователю {target_id} активирована подписка на {days} дней.")
    try:
        await message.bot.send_message(
            target_id,
            f"⭐ Ваша подписка активирована на <b>{days} дней</b>!",
            parse_mode="HTML",
        )
    except Exception:
        pass


# ─── YOOKASSA ─────────────────────────────────────────────────────────────────

async def _create_yookassa_payment(
    tg_id: int,
    amount: int,
    description: str,
    metadata: dict,
) -> str | None:
    """
    Создаёт платёж в ЮКассе и возвращает URL для оплаты.
    Требует YOOKASSA_SHOP_ID и YOOKASSA_SECRET_KEY в .env
    """
    if not config.YOOKASSA_SHOP_ID or not config.YOOKASSA_SECRET_KEY:
        return None

    import httpx, uuid
    payload = {
        "amount": {"value": f"{amount}.00", "currency": "RUB"},
        "confirmation": {"type": "redirect", "return_url": "https://t.me/"},
        "capture": True,
        "description": description,
        "metadata": {**metadata, "tg_id": str(tg_id)},
    }
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                "https://api.yookassa.ru/v3/payments",
                json=payload,
                auth=(config.YOOKASSA_SHOP_ID, config.YOOKASSA_SECRET_KEY),
                headers={"Idempotence-Key": str(uuid.uuid4())},
            )
        if resp.status_code == 200:
            data = resp.json()
            return data["confirmation"]["confirmation_url"]
    except Exception as e:
        logger.exception("ЮКасса: ошибка создания платежа: %s", e)
    return None
