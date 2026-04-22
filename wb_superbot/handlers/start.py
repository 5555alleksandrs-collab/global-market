"""
Обработчики: /start, главное меню, настройка токена.
"""

import logging
from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from database import db
from keyboards.kb import main_menu, cancel_kb
from services.wb_api import WBApiClient
from config import config

logger = logging.getLogger(__name__)
router = Router()


class SetTokenFSM(StatesGroup):
    waiting_token = State()


WELCOME_TEXT = (
    "👋 <b>Добро пожаловать в WB SuperBot!</b>\n\n"
    "Я умею:\n"
    "⚡ <b>Авто-бронь</b> — автоматически бронировать слоты на склады WB\n"
    "🔍 <b>Поиск таймслотов</b> — уведомлять при появлении нужных дат\n"
    "🔄 <b>Перераспределение</b> — перемещать товары между складами\n\n"
    "Для начала работы нужен <b>токен WB продавца</b>.\n"
    "Если не задан — используется токен из конфигурации бота.\n\n"
    "Введите /settoken чтобы задать свой токен, или сразу выбирайте действие:"
)


def _is_admin(tg_id: int) -> bool:
    return tg_id in config.ADMIN_IDS


def _access_request_actions(user_id: int):
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Одобрить", callback_data=f"access:approve:{user_id}")
    kb.button(text="❌ Отклонить", callback_data=f"access:deny:{user_id}")
    kb.adjust(2)
    return kb.as_markup()


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    tg_id = message.from_user.id
    await db.upsert_user(
        tg_id=tg_id,
        username=message.from_user.username or "",
        full_name=message.from_user.full_name or "",
    )
    if _is_admin(tg_id):
        await db.approve_user_access(tg_id)
        await message.answer(WELCOME_TEXT, reply_markup=main_menu(), parse_mode="HTML")
        return

    approved = await db.is_user_approved(tg_id)
    if approved:
        await message.answer(WELCOME_TEXT, reply_markup=main_menu(), parse_mode="HTML")
        return

    user = await db.get_user(tg_id)
    already_requested = bool(user and user.get("access_requested", 0))
    if not already_requested:
        await db.mark_access_requested(tg_id)
        username = f"@{message.from_user.username}" if message.from_user.username else "—"
        full_name = message.from_user.full_name or "—"
        for admin_id in config.ADMIN_IDS:
            try:
                await message.bot.send_message(
                    admin_id,
                    "📥 <b>Новая заявка на доступ</b>\n\n"
                    f"ID: <code>{tg_id}</code>\n"
                    f"Username: {username}\n"
                    f"Имя: {full_name}",
                    parse_mode="HTML",
                    reply_markup=_access_request_actions(tg_id),
                )
            except Exception:
                logger.exception("Не удалось отправить заявку админу %s", admin_id)

    await message.answer(
        "🔐 Доступ к боту выдается администратором.\n"
        "Заявка отправлена, дождитесь подтверждения.",
    )


@router.message(Command("settoken"))
async def cmd_settoken(message: Message, state: FSMContext):
    await state.set_state(SetTokenFSM.waiting_token)
    await message.answer(
        "🔑 Введите <b>API токен</b> из кабинета WB Партнёры:\n\n"
        "<i>Личный кабинет → Настройки → Доступ к API → Токен</i>",
        reply_markup=cancel_kb(),
        parse_mode="HTML",
    )


@router.message(SetTokenFSM.waiting_token)
async def process_token(message: Message, state: FSMContext):
    token = message.text.strip()
    if token == "❌ Отмена":
        await state.clear()
        await message.answer("Отменено.", reply_markup=main_menu())
        return

    if len(token) < 30:
        await message.answer("❌ Токен слишком короткий. Проверьте и введите снова.")
        return

    # Проверяем токен
    await message.answer("⏳ Проверяю токен...")
    client = WBApiClient(token)
    valid = await client.check_token()

    if not valid:
        await message.answer(
            "❌ Токен недействителен. Проверьте правильность и попробуйте снова.\n"
            "Или /cancel чтобы отменить."
        )
        return

    await db.set_wb_token(message.from_user.id, token)
    await state.clear()
    await message.answer(
        "✅ Токен принят и сохранён!",
        reply_markup=main_menu(),
    )


@router.message(Command("cancel"))
@router.message(F.text == "❌ Отмена")
async def cmd_cancel(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Действие отменено.", reply_markup=main_menu())


@router.message(F.text == "❓ Помощь")
async def cmd_help(message: Message):
    text = (
        "📖 <b>Справка по боту</b>\n\n"
        "<b>⚡ Авто-бронь</b>\n"
        "Бот сам ищет свободные слоты по вашим параметрам (склад, тип, период, коэф) "
        "и автоматически бронирует поставку.\n\n"
        "<b>🔍 Поиск таймслотов</b>\n"
        "Бот уведомит вас когда появится подходящий слот — без авто-броней.\n\n"
        "<b>🔄 Перераспределение</b>\n"
        "Перемещение товара между складами WB через API.\n\n"
        "<b>Команды:</b>\n"
        "/start — главное меню\n"
        "/settoken — задать токен WB\n"
        "/cancel — отменить текущее действие\n"
    )
    await message.answer(text, parse_mode="HTML", reply_markup=main_menu())


@router.callback_query(F.data.startswith("access:"))
async def access_request_action(callback: CallbackQuery):
    if not _is_admin(callback.from_user.id):
        await callback.answer("Недостаточно прав", show_alert=True)
        return

    _, action, user_id_raw = callback.data.split(":")
    target_id = int(user_id_raw)

    if action == "approve":
        await db.approve_user_access(target_id)
        await callback.message.edit_text(
            callback.message.text + "\n\n✅ Доступ одобрен.",
            parse_mode="HTML",
        )
        try:
            await callback.bot.send_message(
                target_id,
                "✅ Ваша заявка одобрена. Теперь можно пользоваться ботом.\n"
                "Нажмите /start",
            )
        except Exception:
            logger.exception("Не удалось уведомить пользователя %s", target_id)
        await callback.answer("Пользователь одобрен")
    elif action == "deny":
        await callback.message.edit_text(
            callback.message.text + "\n\n❌ Заявка отклонена.",
            parse_mode="HTML",
        )
        await callback.answer("Заявка отклонена")


@router.message(F.text.startswith("/approve"))
async def approve_by_command(message: Message):
    if not _is_admin(message.from_user.id):
        return
    parts = message.text.split()
    if len(parts) != 2 or not parts[1].isdigit():
        await message.answer("Формат: /approve <user_id>")
        return
    target_id = int(parts[1])
    await db.approve_user_access(target_id)
    await message.answer(f"✅ Доступ для {target_id} одобрен.")


@router.message(F.text == "/requests")
async def list_requests(message: Message):
    if not _is_admin(message.from_user.id):
        return
    rows = await db.get_pending_access_requests()
    if not rows:
        await message.answer("📭 Нет заявок на доступ.")
        return
    lines = ["📥 <b>Заявки на доступ:</b>"]
    for row in rows[:20]:
        lines.append(
            f"• <code>{row['tg_id']}</code> | @{row['username'] or '-'} | {row['full_name'] or '-'}"
        )
    lines.append("\nОдобрить: /approve <user_id>")
    await message.answer("\n".join(lines), parse_mode="HTML")
