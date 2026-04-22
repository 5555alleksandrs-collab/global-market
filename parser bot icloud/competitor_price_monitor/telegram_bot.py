from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import re
import socket
import ssl
import time
from contextlib import suppress
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from threading import Event
from typing import Optional

from telegram import (
    Contact,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
    Update,
)
from telegram.constants import ChatAction
from telegram.error import BadRequest, Forbidden, NetworkError, TelegramError
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from competitor_price_monitor.access_requests import (
    AccessRequest,
    create_or_refresh_access_request,
    format_access_request_for_admin,
    get_access_request,
    update_access_request_status,
)
from competitor_price_monitor.auto_refresh_schedule import (
    DEFAULT_DAILY_TIME,
    DEFAULT_TIMEZONE_NAME,
    calculate_next_daily_run,
    format_daily_schedule_text,
    seconds_until_next_daily_run,
    normalize_daily_time,
)
from competitor_price_monitor.access_control import (
    AccessConfig,
    add_allowed_chat,
    add_allowed_user,
    build_access_config,
    format_identity_message,
    is_authorized_chat,
    is_authorized_for_bot,
    load_access_store,
    merge_access_configs,
    parse_id_list,
    remove_allowed_chat,
    remove_allowed_user,
    save_access_store,
)
from competitor_price_monitor.change_alerts import (
    format_price_change_messages,
    load_price_change_events,
)
from competitor_price_monitor.comparison_export import (
    DEFAULT_EXPORT_PATH,
    ExportCancelledError,
    build_details_export_path,
    export_price_comparison_csv,
)
from competitor_price_monitor.device_catalog import export_supported_devices_csv, load_supported_devices
from competitor_price_monitor.google_sheets_sync import sync_exports_to_google_sheets
from competitor_price_monitor.google_sheets_sync import export_source_catalog_from_first_worksheet
from competitor_price_monitor.google_sheets_sync import export_source_catalog_from_catalog_worksheet
from competitor_price_monitor.logging_setup import setup_logging
from competitor_price_monitor.models import GoogleSheetsConfig, LoggingConfig
from competitor_price_monitor.query_compare import compare_query_text, render_compare_report

logger = logging.getLogger(__name__)
NETWORK_ERROR_LOG_DEDUP_SECONDS = 120.0
LAST_NETWORK_ERROR_SIGNATURE = ""
LAST_NETWORK_ERROR_TS = 0.0
ASYNCIO_PREVIOUS_EXCEPTION_HANDLER_KEY = "asyncio_previous_exception_handler"


MAIN_MENU_TEXT = (
    "Панель управления.\n"
    "Отправьте запрос по модели или выберите действие в меню.\n\n"
    "Примеры запросов:\n"
    "• 17 pro 256 silver sim\n"
    "• 17 pro max 512 deep blue esim\n"
    "• 16 256 black"
)
EXPORTS_MENU_TEXT = (
    "Выгрузки.\n"
    "Обновление Google Sheets, статус текущей задачи и справочник моделей."
)
NOTIFICATIONS_MENU_TEXT = (
    "Уведомления.\n"
    "Управление подпиской этого чата и просмотр расписания автообновления."
)

BUTTON_MENU = "🏠 Меню"
BUTTON_EXAMPLES = "🔎 Примеры"
BUTTON_SHEETS = "📊 Таблица"
BUTTON_CATALOG = "📚 Модели"
BUTTON_HELP = "ℹ️ Помощь"

CALLBACK_MENU_MAIN = "menu:main"
CALLBACK_MENU_EXPORTS = "menu:exports"
CALLBACK_MENU_NOTIFICATIONS = "menu:notifications"
CALLBACK_MENU_HELP = "menu:help"
CALLBACK_SHEETS = "sheets:export"
CALLBACK_CATALOG = "catalog:export"
CALLBACK_CANCEL_REFRESH = "refresh:cancel"
CALLBACK_REFRESH_STATUS = "refresh:status"
CALLBACK_RETRY_SHEETS = "refresh:retry_sheets"
CALLBACK_EXAMPLES = "examples:show"
CALLBACK_NOTIFY_INFO = "notify:info"
CALLBACK_WHOAMI = "identity:show"
CALLBACK_EXAMPLE_PREFIX = "example:"
CALLBACK_ADMIN_MENU = "admin:menu"
CALLBACK_ADMIN_LIST = "admin:list"
CALLBACK_ADMIN_REQUESTS = "admin:requests"
CALLBACK_ADMIN_ADD_USER = "admin:add_user"
CALLBACK_ADMIN_ADD_CHAT = "admin:add_chat"
CALLBACK_ADMIN_REMOVE_USER = "admin:remove_user"
CALLBACK_ADMIN_REMOVE_CHAT = "admin:remove_chat"
CALLBACK_ADMIN_CANCEL = "admin:cancel"
CALLBACK_REQUEST_APPROVE_PREFIX = "request:approve:"
CALLBACK_REQUEST_DENY_PREFIX = "request:deny:"

EXAMPLE_QUERIES = (
    "17 pro 256 silver sim",
    "17 pro max 512 deep blue esim",
    "17 256 mist blue esim",
    "16 256 black",
)
ACTIVE_COMPARISON_EXPORTS: set[int] = set()
ACTIVE_SHEETS_EXPORTS: set[int] = set()
REFRESH_LOCK_KEY = "refresh_lock"
REFRESH_STATE_KEY = "refresh_state"
AUTO_REFRESH_TASK_KEY = "auto_refresh_task"
LAST_REFRESH_SUMMARY_KEY = "last_refresh_summary"
DEFAULT_SUBSCRIBERS_PATH = Path(__file__).resolve().parent / "data" / "telegram_subscribers.json"
DEFAULT_ACCESS_STORE_PATH = Path(__file__).resolve().parent / "data" / "access_overrides.json"
DEFAULT_ACCESS_REQUESTS_PATH = Path(__file__).resolve().parent / "data" / "access_requests.json"
ADMIN_PENDING_ACTION_KEY = "admin_pending_action"
MENU_MESSAGE_ID_KEY = "menu_message_id"
MENU_CHAT_ID_KEY = "menu_chat_id"
ADMIN_ACTION_ADD_USER = "add_user"
ADMIN_ACTION_ADD_CHAT = "add_chat"
ADMIN_ACTION_REMOVE_USER = "remove_user"
ADMIN_ACTION_REMOVE_CHAT = "remove_chat"


@dataclass(frozen=True)
class AutoRefreshConfig:
    enabled: bool
    daily_time: str
    timezone_name: str
    update_sheets: bool
    run_on_start: bool


@dataclass(frozen=True)
class RefreshRunResult:
    export_path: Path
    spreadsheet_url: Optional[str]
    sheet_error: Optional[str]
    changes_count: int
    devices_count: int


@dataclass
class RefreshState:
    owner_chat_id: Optional[int]
    kind: str
    cancel_event: Event
    status_chat_id: Optional[int] = None
    status_message_id: Optional[int] = None


def render_card(title: str, lines: list[str]) -> str:
    clean_lines = [line for line in lines if str(line).strip()]
    return "{0}\n{1}".format(title, "\n".join(clean_lines))


def remember_refresh_summary(
    application: Application,
    *,
    ok: bool,
    kind: str,
    devices_count: int = 0,
    changes_count: int = 0,
    spreadsheet_url: Optional[str] = None,
    error: Optional[str] = None,
) -> None:
    timestamp = datetime.now().astimezone().replace(microsecond=0).strftime("%d.%m %H:%M")
    application.bot_data[LAST_REFRESH_SUMMARY_KEY] = {
        "ok": ok,
        "kind": kind,
        "devices_count": devices_count,
        "changes_count": changes_count,
        "spreadsheet_url": spreadsheet_url,
        "error": error,
        "timestamp": timestamp,
    }


def format_last_refresh_summary(application: Application) -> str:
    value = application.bot_data.get(LAST_REFRESH_SUMMARY_KEY)
    if not isinstance(value, dict):
        return "Последний запуск: данных пока нет."

    status_text = "успешно" if value.get("ok") else "с ошибкой"
    lines = [
        "Последний запуск: {0} ({1})".format(status_text, value.get("timestamp", "-")),
        "Тип: {0}".format("Google Sheets" if value.get("kind") == "sheets" else "обновление цен"),
        "Позиции: {0}".format(value.get("devices_count", 0)),
        "Изменения цен: {0}".format(value.get("changes_count", 0)),
    ]
    if value.get("spreadsheet_url"):
        lines.append("Таблица: {0}".format(value["spreadsheet_url"]))
    if value.get("error"):
        lines.append("Ошибка: {0}".format(value["error"]))
    return "\n".join(lines)


def build_help_text(is_admin: bool) -> str:
    base_text = (
        "Что делает бот:\n"
        "• Ищет цены по запросу модели\n"
        "• Обновляет Google Sheets\n"
        "• Присылает автоуведомления об изменениях\n\n"
        "Поддерживаемые магазины:\n"
        "• iLab\n"
        "• I LITE\n"
        "• KingStore Saratov\n"
        "• Хатико\n"
        "• RE:premium (если ссылка задана в таблице)\n\n"
        "Быстрые команды:\n"
        "• /sheets — обновить таблицу\n"
        "• /catalog — справочник моделей\n"
        "• /notify_on — включить уведомления\n"
        "• /notify_off — выключить уведомления\n"
        "• /whoami — показать ваш user_id/chat_id\n"
        "• /menu — открыть меню\n\n"
        "Пример запроса:\n"
        "• 17 pro 256 silver sim"
    )
    if not is_admin:
        return base_text
    return "{0}\n/admin".format(base_text)


async def show_main_menu(
    context: ContextTypes.DEFAULT_TYPE,
    *,
    message: Optional[Message] = None,
    query=None,
    is_admin: bool = False,
) -> None:
    chat_id = message.chat_id if message is not None else query.message.chat_id
    await show_panel(
        context,
        chat_id=chat_id,
        text=MAIN_MENU_TEXT,
        reply_markup=build_main_menu_keyboard(is_admin=is_admin),
        message=message,
        query=query,
    )


async def show_panel(
    context: ContextTypes.DEFAULT_TYPE,
    *,
    chat_id: int,
    text: str,
    reply_markup: InlineKeyboardMarkup,
    message: Optional[Message] = None,
    query=None,
) -> None:
    if query is not None and query.message is not None:
        await safe_edit_panel_message(query.message, text, reply_markup)
        remember_menu_message(context, chat_id, query.message.message_id)
        return

    remembered_message_id = context.user_data.get(MENU_MESSAGE_ID_KEY)
    remembered_chat_id = context.user_data.get(MENU_CHAT_ID_KEY)
    if remembered_message_id and remembered_chat_id == chat_id:
        try:
            await context.application.bot.edit_message_text(
                chat_id=chat_id,
                message_id=remembered_message_id,
                text=text,
                reply_markup=reply_markup,
            )
            return
        except TelegramError:
            context.user_data.pop(MENU_MESSAGE_ID_KEY, None)
            context.user_data.pop(MENU_CHAT_ID_KEY, None)

    if message is None:
        sent_message = await context.application.bot.send_message(
            chat_id=chat_id,
            text=text,
            reply_markup=reply_markup,
        )
    else:
        sent_message = await message.reply_text(text, reply_markup=reply_markup)
    remember_menu_message(context, chat_id, sent_message.message_id)


async def safe_edit_panel_message(message: Message, text: str, reply_markup: InlineKeyboardMarkup) -> None:
    try:
        await message.edit_text(text=text, reply_markup=reply_markup)
    except TelegramError:
        pass


async def update_status_message(
    message: Optional[Message],
    text: str,
    reply_markup: Optional[InlineKeyboardMarkup] = None,
) -> None:
    if message is None:
        return
    try:
        await message.edit_text(text=text, reply_markup=reply_markup)
    except TelegramError as error:
        if "message is not modified" in str(error).lower():
            return
        logger.debug("Failed to edit status message: %s", error)


async def update_active_refresh_message(
    application: Application,
    text: str,
    reply_markup: Optional[InlineKeyboardMarkup] = None,
    *,
    skip_message: Optional[Message] = None,
) -> None:
    state = get_refresh_state(application)
    if state is None or state.status_chat_id is None or state.status_message_id is None:
        return
    if (
        skip_message is not None
        and skip_message.chat_id == state.status_chat_id
        and skip_message.message_id == state.status_message_id
    ):
        return
    try:
        await application.bot.edit_message_text(
            chat_id=state.status_chat_id,
            message_id=state.status_message_id,
            text=text,
            reply_markup=reply_markup,
        )
    except TelegramError as error:
        if "message is not modified" in str(error).lower():
            return
        logger.debug("Failed to edit active refresh message: %s", error)


def remember_menu_message(context: ContextTypes.DEFAULT_TYPE, chat_id: int, message_id: int) -> None:
    context.user_data[MENU_CHAT_ID_KEY] = chat_id
    context.user_data[MENU_MESSAGE_ID_KEY] = message_id


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Telegram bot for model-based Apple price comparison.")
    parser.add_argument(
        "--token-env",
        default="COMPETITOR_PRICE_BOT_TOKEN",
        help="Environment variable containing Telegram bot token.",
    )
    parser.add_argument(
        "--log-file",
        default=str(Path(__file__).resolve().parent / "logs" / "telegram_bot.log"),
        help="Path to log file.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable debug logging.",
    )
    return parser


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    if message is None:
        return
    if not await ensure_authorized(update):
        return
    added = register_notification_chat(message.chat_id)
    await message.reply_text("Бот запущен и готов к работе.", reply_markup=build_main_keyboard())
    if added:
        await message.reply_text("Этот чат добавлен в автоуведомления о смене цен.")
    await show_main_menu(context, message=message, is_admin=is_admin_user(update))


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    if message is None:
        return
    if not await ensure_authorized(update):
        return
    register_notification_chat(message.chat_id)
    admin_mode = is_admin_user(update)
    await message.reply_text(build_help_text(admin_mode), reply_markup=build_main_keyboard())
    await show_main_menu(context, message=message, is_admin=admin_mode)


async def menu_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    if message is None:
        return
    if not await ensure_authorized(update):
        return
    register_notification_chat(message.chat_id)
    await show_main_menu(context, message=message, is_admin=is_admin_user(update))


async def compare_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    if message is None:
        return
    if not await ensure_authorized(update):
        return
    register_notification_chat(message.chat_id)

    query = " ".join(context.args).strip()
    if not query:
        await message.reply_text(
            "После `/compare` нужен запрос. Пример: `/compare 17 pro 256 silver sim`",
            reply_markup=build_action_keyboard(),
        )
        return

    await answer_query(message, query)


async def examples_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    if message is None:
        return
    if not await ensure_authorized(update):
        return
    register_notification_chat(message.chat_id)
    await show_panel(
        context,
        chat_id=message.chat_id,
        text="Примеры запросов.\nВыберите готовый вариант или отправьте свой текст вручную.",
        reply_markup=build_examples_keyboard(),
        message=message,
    )


async def devices_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    if message is None:
        return
    if not await ensure_authorized(update):
        return
    register_notification_chat(message.chat_id)
    await message.reply_text(
        "CSV-режим отключен.\nИспользуйте Google Sheets: кнопка `📊 Таблица` или команда `/sheets`.",
        reply_markup=build_action_keyboard(),
    )


async def sheets_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    if message is None:
        return
    if not await ensure_authorized(update):
        return
    register_notification_chat(message.chat_id)
    await send_comparison_sheet(message, context.application)


async def catalog_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    if message is None:
        return
    if not await ensure_authorized(update):
        return
    register_notification_chat(message.chat_id)
    await send_catalog_csv(message)


async def notify_on_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    if message is None:
        return
    if not await ensure_authorized(update):
        return
    register_notification_chat(message.chat_id)
    settings = read_auto_refresh_config()
    if settings.enabled:
        text = (
            "Автоуведомления включены для этого чата.\n"
            "Автообновление: {0}."
        ).format(format_daily_schedule_text(settings.daily_time, settings.timezone_name))
    else:
        text = (
            "Этот чат добавлен в список уведомлений.\n"
            "Автообновление сейчас выключено, включим его через COMPETITOR_PRICE_AUTO_REFRESH_ENABLED=true."
        )
    await message.reply_text(text, reply_markup=build_action_keyboard())


async def notify_off_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    if message is None:
        return
    if not await ensure_authorized(update):
        return
    removed = unregister_notification_chat(message.chat_id)
    text = "Автоуведомления для этого чата выключены." if removed else "Этот чат и так не был в списке автоуведомлений."
    await message.reply_text(text, reply_markup=build_action_keyboard())


async def admin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    if message is None:
        return
    if not await ensure_admin(update):
        return
    clear_admin_pending_action(context)
    await show_panel(
        context,
        chat_id=message.chat_id,
        text=build_admin_panel_text(),
        reply_markup=build_admin_keyboard(),
        message=message,
    )


async def whoami_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    if message is None:
        return

    chat = update.effective_chat
    user = update.effective_user
    access_config = read_access_config()
    admin_config = read_admin_config()
    await message.reply_text(
        format_identity_message(
            user_id=user.id if user else None,
            chat_id=chat.id if chat else None,
            username=user.username if user else None,
            chat_type=chat.type if chat else None,
            authorized=is_authorized_for_bot(
                chat.id if chat else None,
                user.id if user else None,
                access_config,
                admin_config,
            ),
        ),
        reply_markup=build_action_keyboard(),
    )


async def handle_contact(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    user = update.effective_user
    if message is None or user is None or message.contact is None:
        return

    if is_authorized_for_bot(
        message.chat_id,
        user.id,
        read_access_config(),
        read_admin_config(),
    ):
        await message.reply_text(
            "Доступ уже есть, отправлять номер не нужно.",
            reply_markup=build_action_keyboard(),
        )
        return

    await process_access_request_contact(message, user_id=user.id, contact=message.contact, application=context.application)


async def ensure_authorized(update: Update) -> bool:
    chat = update.effective_chat
    user = update.effective_user
    chat_id = chat.id if chat else None
    user_id = user.id if user else None
    if is_authorized_for_bot(
        chat_id,
        user_id,
        read_access_config(),
        read_admin_config(),
    ):
        return True

    if update.callback_query is not None:
        await safe_answer_callback_query(update.callback_query, "Доступ ограничен", show_alert=True)

    message = update.effective_message
    if message is not None:
        await send_access_request_prompt(message)
    return False


async def ensure_admin(update: Update) -> bool:
    config = read_admin_config()
    if not config.enabled:
        message = update.effective_message
        if message is not None:
            await message.reply_text("Эта команда недоступна.")
        return False

    chat = update.effective_chat
    user = update.effective_user
    if is_authorized_chat(chat.id if chat else None, user.id if user else None, config):
        return True

    if update.callback_query is not None:
        await safe_answer_callback_query(update.callback_query, "Команда недоступна", show_alert=True)

    message = update.effective_message
    if message is not None:
        await message.reply_text("Эта команда недоступна.")
    return False


def is_admin_user(update: Update) -> bool:
    config = read_admin_config()
    if not config.enabled:
        return False
    chat = update.effective_chat
    user = update.effective_user
    return is_authorized_chat(chat.id if chat else None, user.id if user else None, config)


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    if message is None or not message.text:
        return

    if not await ensure_authorized(update):
        return
    register_notification_chat(message.chat_id)
    text = message.text.strip()
    if await maybe_handle_admin_input(message, text, context):
        return
    if text == BUTTON_MENU:
        await show_main_menu(context, message=message, is_admin=is_admin_user(update))
        return
    if text == BUTTON_HELP:
        await help_cmd(update, context)
        return
    if text == BUTTON_EXAMPLES:
        await examples_cmd(update, context)
        return
    if text == BUTTON_SHEETS:
        await send_comparison_sheet(message, context.application)
        return
    if text == BUTTON_CATALOG:
        await send_catalog_csv(message)
        return

    await answer_query(message, text)


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    message = update.effective_message
    if query is None or message is None:
        return

    if query.data and (
        query.data.startswith(CALLBACK_REQUEST_APPROVE_PREFIX)
        or query.data.startswith(CALLBACK_REQUEST_DENY_PREFIX)
    ):
        if not await ensure_admin(update):
            return
        await handle_access_request_callback(update, context)
        return

    if not await ensure_authorized(update):
        return

    if not await safe_answer_callback_query(query):
        return

    if query.data == CALLBACK_MENU_MAIN:
        clear_admin_pending_action(context)
        await show_main_menu(context, query=query, is_admin=is_admin_user(update))
        return

    if query.data == CALLBACK_MENU_EXPORTS:
        clear_admin_pending_action(context)
        await show_panel(
            context,
            chat_id=message.chat_id,
            text=EXPORTS_MENU_TEXT,
            reply_markup=build_exports_keyboard(),
            query=query,
        )
        return

    if query.data == CALLBACK_MENU_NOTIFICATIONS:
        clear_admin_pending_action(context)
        await show_panel(
            context,
            chat_id=message.chat_id,
            text=NOTIFICATIONS_MENU_TEXT,
            reply_markup=build_notifications_keyboard(),
            query=query,
        )
        return

    if query.data == CALLBACK_MENU_HELP:
        clear_admin_pending_action(context)
        await show_panel(
            context,
            chat_id=message.chat_id,
            text=build_help_text(is_admin_user(update)),
            reply_markup=build_main_menu_keyboard(is_admin=is_admin_user(update)),
            query=query,
        )
        return

    if query.data == CALLBACK_EXAMPLES:
        clear_admin_pending_action(context)
        await show_panel(
            context,
            chat_id=message.chat_id,
            text="Примеры запросов.\nВыберите готовый вариант или отправьте свой текст вручную.",
            reply_markup=build_examples_keyboard(),
            query=query,
        )
        return

    if query.data == CALLBACK_WHOAMI:
        chat = update.effective_chat
        user = update.effective_user
        access_config = read_access_config()
        admin_config = read_admin_config()
        await show_panel(
            context,
            chat_id=message.chat_id,
            text=format_identity_message(
                user_id=user.id if user else None,
                chat_id=chat.id if chat else None,
                username=user.username if user else None,
                chat_type=chat.type if chat else None,
                authorized=is_authorized_for_bot(
                    chat.id if chat else None,
                    user.id if user else None,
                    access_config,
                    admin_config,
                ),
            ),
            reply_markup=build_main_menu_keyboard(is_admin=is_admin_user(update)),
            query=query,
        )
        return

    if query.data == "notify:on":
        register_notification_chat(message.chat_id)
        settings = read_auto_refresh_config()
        await show_panel(
            context,
            chat_id=message.chat_id,
            text=(
                "Уведомления для этого чата включены.\n"
                "Автообновление: {0}."
            ).format(format_daily_schedule_text(settings.daily_time, settings.timezone_name)),
            reply_markup=build_notifications_keyboard(),
            query=query,
        )
        return

    if query.data == "notify:off":
        unregister_notification_chat(message.chat_id)
        await show_panel(
            context,
            chat_id=message.chat_id,
            text="Уведомления для этого чата выключены.",
            reply_markup=build_notifications_keyboard(),
            query=query,
        )
        return

    if query.data == CALLBACK_NOTIFY_INFO:
        await show_panel(
            context,
            chat_id=message.chat_id,
            text=build_notifications_status_text(message.chat_id),
            reply_markup=build_notifications_keyboard(),
            query=query,
        )
        return

    if query.data == CALLBACK_SHEETS:
        register_notification_chat(message.chat_id)
        await send_comparison_sheet(message, context.application)
        return

    if query.data == CALLBACK_CATALOG:
        register_notification_chat(message.chat_id)
        await send_catalog_csv(message)
        return

    if query.data == CALLBACK_CANCEL_REFRESH:
        response = request_refresh_cancel(context.application, message.chat_id)
        state = get_refresh_state(context.application)
        reply_markup = (
            build_cancelling_action_keyboard()
            if state is not None and state.cancel_event.is_set()
            else build_running_action_keyboard() if state is not None else build_action_keyboard()
        )
        await update_status_message(
            message,
            response,
            reply_markup,
        )
        await update_active_refresh_message(
            context.application,
            response,
            reply_markup,
            skip_message=message,
        )
        return

    if query.data == CALLBACK_REFRESH_STATUS:
        await update_status_message(
            message,
            build_refresh_status_text(context.application),
            build_running_action_keyboard() if is_refresh_busy(context.application) else build_action_keyboard(),
        )
        return

    if query.data == CALLBACK_RETRY_SHEETS:
        register_notification_chat(message.chat_id)
        await send_comparison_sheet(message, context.application)
        return

    if query.data == CALLBACK_ADMIN_MENU:
        if not await ensure_admin(update):
            return
        clear_admin_pending_action(context)
        await show_panel(
            context,
            chat_id=message.chat_id,
            text=build_admin_panel_text(),
            reply_markup=build_admin_keyboard(),
            query=query,
        )
        return

    if query.data == CALLBACK_ADMIN_LIST:
        if not await ensure_admin(update):
            return
        clear_admin_pending_action(context)
        await show_panel(
            context,
            chat_id=message.chat_id,
            text=build_admin_list_text(),
            reply_markup=build_admin_keyboard(),
            query=query,
        )
        return

    if query.data == CALLBACK_ADMIN_REQUESTS:
        if not await ensure_admin(update):
            return
        clear_admin_pending_action(context)
        await show_panel(
            context,
            chat_id=message.chat_id,
            text=build_admin_requests_text(),
            reply_markup=build_admin_keyboard(),
            query=query,
        )
        return

    if query.data == CALLBACK_ADMIN_ADD_USER:
        if not await ensure_admin(update):
            return
        set_admin_pending_action(context, ADMIN_ACTION_ADD_USER)
        await show_panel(
            context,
            chat_id=message.chat_id,
            text=build_admin_input_prompt(ADMIN_ACTION_ADD_USER),
            reply_markup=build_admin_keyboard(),
            query=query,
        )
        return

    if query.data == CALLBACK_ADMIN_ADD_CHAT:
        if not await ensure_admin(update):
            return
        set_admin_pending_action(context, ADMIN_ACTION_ADD_CHAT)
        await show_panel(
            context,
            chat_id=message.chat_id,
            text=build_admin_input_prompt(ADMIN_ACTION_ADD_CHAT),
            reply_markup=build_admin_keyboard(),
            query=query,
        )
        return

    if query.data == CALLBACK_ADMIN_REMOVE_USER:
        if not await ensure_admin(update):
            return
        set_admin_pending_action(context, ADMIN_ACTION_REMOVE_USER)
        await show_panel(
            context,
            chat_id=message.chat_id,
            text=build_admin_input_prompt(ADMIN_ACTION_REMOVE_USER),
            reply_markup=build_admin_keyboard(),
            query=query,
        )
        return

    if query.data == CALLBACK_ADMIN_REMOVE_CHAT:
        if not await ensure_admin(update):
            return
        set_admin_pending_action(context, ADMIN_ACTION_REMOVE_CHAT)
        await show_panel(
            context,
            chat_id=message.chat_id,
            text=build_admin_input_prompt(ADMIN_ACTION_REMOVE_CHAT),
            reply_markup=build_admin_keyboard(),
            query=query,
        )
        return

    if query.data == CALLBACK_ADMIN_CANCEL:
        if not await ensure_admin(update):
            return
        clear_admin_pending_action(context)
        await show_panel(
            context,
            chat_id=message.chat_id,
            text=build_admin_panel_text(),
            reply_markup=build_admin_keyboard(),
            query=query,
        )
        return

    if query.data and query.data.startswith(CALLBACK_EXAMPLE_PREFIX):
        suffix = query.data[len(CALLBACK_EXAMPLE_PREFIX) :]
        if suffix.isdigit():
            index = int(suffix)
            if 0 <= index < len(EXAMPLE_QUERIES):
                await answer_query(message, EXAMPLE_QUERIES[index])
                return

    await message.reply_text("Не удалось распознать действие кнопки.", reply_markup=build_action_keyboard())


async def answer_query(message: Message, query_text: str) -> None:
    await message.chat.send_action(ChatAction.TYPING)

    try:
        query, matches = compare_query_text(query_text)
        response = render_compare_report(query, matches)
    except ValueError as error:
        response = str(error)
    except Exception as error:  # noqa: BLE001
        logger.exception("Failed to process query: %s", query_text)
        response = "Не удалось получить сравнение: {0}".format(error)

    await message.reply_text(response, reply_markup=build_action_keyboard())


async def send_comparison_csv(message: Message, application: Application) -> None:
    chat_id = message.chat_id
    if chat_id in ACTIVE_COMPARISON_EXPORTS:
        await message.reply_text(
            "Таблица уже собирается. Я пришлю файл, как только закончу.",
            reply_markup=build_action_keyboard(),
        )
        return
    if is_refresh_busy(application):
        await message.reply_text(
            "Сейчас уже идёт обновление цен. Как только оно закончится, можно будет запросить CSV ещё раз.",
            reply_markup=build_action_keyboard(),
        )
        return

    ACTIVE_COMPARISON_EXPORTS.add(chat_id)
    status_message = await message.reply_text(
        "Собираю ценовую матрицу: слева модели, сверху магазины. Это может занять несколько минут, я буду показывать прогресс.",
        reply_markup=build_running_action_keyboard(),
    )

    try:
        result = await execute_refresh_cycle(
            application,
            update_sheets=False,
            progress_message=status_message,
            owner_chat_id=chat_id,
        )
        caption = "Ценовая матрица сформирована: {0} моделей x магазины.".format(result.devices_count)
        await update_status_message(
            status_message,
            "Выгрузка готова. Отправляю CSV-файл.",
            build_action_keyboard(),
        )

        await message.chat.send_action(ChatAction.UPLOAD_DOCUMENT)
        with result.export_path.open("rb") as handle:
            await message.reply_document(
                document=handle,
                filename=result.export_path.name,
                caption=caption,
                reply_markup=build_action_keyboard(),
            )
        await update_status_message(
            status_message,
            "CSV сформирован и отправлен.\nМоделей: {0}.".format(result.devices_count),
            build_action_keyboard(),
        )
    except ExportCancelledError as error:
        await update_status_message(status_message, str(error), build_action_keyboard())
    except Exception as error:  # noqa: BLE001
        logger.exception("Failed to build price comparison export")
        await update_status_message(
            status_message,
            "Не удалось сформировать CSV со сравнением цен: {0}".format(error),
            build_action_keyboard(),
        )
    finally:
        ACTIVE_COMPARISON_EXPORTS.discard(chat_id)


async def send_catalog_csv(message: Message) -> None:
    await message.chat.send_action(ChatAction.UPLOAD_DOCUMENT)

    try:
        source_catalog_path = resolve_runtime_source_catalog_path()
        export_path = export_supported_devices_csv(source_path=source_catalog_path)
        devices = load_supported_devices(source_catalog_path)
        caption = "Список поддерживаемых моделей: {0} позиций.".format(len(devices))

        with export_path.open("rb") as handle:
            await message.reply_document(
                document=handle,
                filename=export_path.name,
                caption=caption,
                reply_markup=build_action_keyboard(),
            )
    except Exception as error:  # noqa: BLE001
        logger.exception("Failed to build supported devices catalog export")
        await message.reply_text(
            "Не удалось сформировать CSV со списком моделей: {0}".format(error),
            reply_markup=build_action_keyboard(),
        )


async def send_comparison_sheet(message: Message, application: Application) -> None:
    chat_id = message.chat_id
    if chat_id in ACTIVE_SHEETS_EXPORTS:
        await message.reply_text(
            "Google Sheets уже обновляется. Я пришлю ссылку, как только всё будет готово.",
            reply_markup=build_action_keyboard(),
        )
        return
    if is_refresh_busy(application):
        await message.reply_text(
            "Сейчас уже идёт обновление цен. Как только оно закончится, можно будет снова запросить Google Sheets.",
            reply_markup=build_action_keyboard(),
        )
        return
    try:
        sheets_config = read_google_sheets_config()
    except RuntimeError as error:
        await message.reply_text(str(error), reply_markup=build_action_keyboard())
        return

    ACTIVE_SHEETS_EXPORTS.add(chat_id)
    status_message = await message.reply_text(
        render_card(
            "📊 Запуск обновления",
            [
                "Подготавливаю позиции и начинаю сбор цен.",
                "Статус буду обновлять в этом же сообщении.",
            ],
        ),
        reply_markup=build_running_action_keyboard(),
    )

    try:
        result = await execute_refresh_cycle(
            application,
            update_sheets=True,
            progress_message=status_message,
            allow_missing_sheets=False,
            owner_chat_id=chat_id,
        )
        await update_status_message(
            status_message,
            render_card(
                "✅ Обновление завершено",
                [
                    "Google Sheets успешно обновлён.",
                    "Позиции: {0}".format(result.devices_count),
                    "Изменения цен: {0}".format(result.changes_count),
                    "Таблица: {0}".format(result.spreadsheet_url),
                    "Вкладки: {0}, {1}".format(
                        sheets_config.comparison_worksheet_name,
                        sheets_config.catalog_worksheet_name,
                    ),
                ],
            ),
            build_action_keyboard(),
        )
        remember_refresh_summary(
            application,
            ok=True,
            kind="sheets",
            devices_count=result.devices_count,
            changes_count=result.changes_count,
            spreadsheet_url=result.spreadsheet_url,
        )
    except ExportCancelledError as error:
        await update_status_message(
            status_message,
            render_card("⛔ Операция остановлена", [str(error)]),
            build_action_keyboard(),
        )
        remember_refresh_summary(application, ok=False, kind="sheets", error=str(error))
    except Exception as error:  # noqa: BLE001
        logger.exception("Failed to sync Google Sheets export")
        await update_status_message(
            status_message,
            render_card(
                "❌ Ошибка обновления",
                [
                    "Не удалось обновить Google Sheets.",
                    "Причина: {0}".format(error),
                    "Проверьте доступы сервисного аккаунта и настройки `.env`.",
                ],
            ),
            build_action_keyboard(),
        )
        remember_refresh_summary(application, ok=False, kind="sheets", error=str(error))
    finally:
        ACTIVE_SHEETS_EXPORTS.discard(chat_id)


def build_main_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton(BUTTON_MENU), KeyboardButton(BUTTON_HELP)],
        ],
        resize_keyboard=True,
        input_field_placeholder="Введите модель, например: 17 pro 256 silver sim",
    )


def build_main_menu_keyboard(*, is_admin: bool = False) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton("🔎 Поиск", callback_data=CALLBACK_EXAMPLES),
            InlineKeyboardButton("📦 Выгрузки", callback_data=CALLBACK_MENU_EXPORTS),
        ],
        [
            InlineKeyboardButton("🔔 Уведомления", callback_data=CALLBACK_MENU_NOTIFICATIONS),
            InlineKeyboardButton("📊 Таблица", callback_data=CALLBACK_SHEETS),
        ],
        [
            InlineKeyboardButton("🧾 Мой доступ", callback_data=CALLBACK_WHOAMI),
        ],
    ]
    if is_admin:
        rows.append(
            [
                InlineKeyboardButton("🛂 Админка", callback_data=CALLBACK_ADMIN_MENU),
                InlineKeyboardButton("ℹ️ Помощь", callback_data=CALLBACK_MENU_HELP),
            ]
        )
    else:
        rows.append([InlineKeyboardButton("ℹ️ Помощь", callback_data=CALLBACK_MENU_HELP)])
    return InlineKeyboardMarkup(rows)


def build_action_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("🏠 Главное меню", callback_data=CALLBACK_MENU_MAIN),
                InlineKeyboardButton("📦 Выгрузки", callback_data=CALLBACK_MENU_EXPORTS),
            ],
            [
                InlineKeyboardButton("🔁 Обновить таблицу", callback_data=CALLBACK_RETRY_SHEETS),
            ]
        ]
    )


def build_running_action_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("⛔ Отменить выгрузку", callback_data=CALLBACK_CANCEL_REFRESH),
                InlineKeyboardButton("📍 Статус", callback_data=CALLBACK_REFRESH_STATUS),
            ],
            [
                InlineKeyboardButton("🏠 Главное меню", callback_data=CALLBACK_MENU_MAIN),
                InlineKeyboardButton("📦 Выгрузки", callback_data=CALLBACK_MENU_EXPORTS),
            ],
        ]
    )


def build_cancelling_action_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("📍 Статус", callback_data=CALLBACK_REFRESH_STATUS),
            ],
            [
                InlineKeyboardButton("🏠 Главное меню", callback_data=CALLBACK_MENU_MAIN),
                InlineKeyboardButton("📦 Выгрузки", callback_data=CALLBACK_MENU_EXPORTS),
            ],
        ]
    )


def build_exports_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("📊 Обновить Google Sheets", callback_data=CALLBACK_SHEETS),
            ],
            [
                InlineKeyboardButton("📚 Список моделей", callback_data=CALLBACK_CATALOG),
            ],
            [
                InlineKeyboardButton("⛔ Отменить выгрузку", callback_data=CALLBACK_CANCEL_REFRESH),
                InlineKeyboardButton("📍 Статус", callback_data=CALLBACK_REFRESH_STATUS),
            ],
            [
                InlineKeyboardButton("🔁 Обновить таблицу", callback_data=CALLBACK_RETRY_SHEETS),
            ],
            [
                InlineKeyboardButton("🏠 Назад в меню", callback_data=CALLBACK_MENU_MAIN),
            ],
        ]
    )


def build_notifications_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✅ Включить", callback_data="notify:on"),
                InlineKeyboardButton("⛔ Выключить", callback_data="notify:off"),
            ],
            [
                InlineKeyboardButton("🕒 Расписание и статус", callback_data=CALLBACK_NOTIFY_INFO),
            ],
            [
                InlineKeyboardButton("🏠 Назад в меню", callback_data=CALLBACK_MENU_MAIN),
            ],
        ]
    )


def build_refresh_status_text(application: Application) -> str:
    state = get_refresh_state(application)
    if state is None:
        return render_card(
            "📍 Статус",
            [
                "Активных задач сейчас нет.",
                "Можно запустить обновление Google Sheets.",
                format_last_refresh_summary(application),
            ],
        )

    status = "выполняется"
    if state.cancel_event.is_set():
        status = "останавливается по запросу"
    kind_text = "Google Sheets" if state.kind == "sheets" else "обновление цен"
    return render_card(
        "📍 Статус",
        [
            "Текущая задача: {0}".format(kind_text),
            "Состояние: {0}".format(status),
            format_last_refresh_summary(application),
        ],
    )


def build_notifications_status_text(chat_id: int) -> str:
    settings = read_auto_refresh_config()
    subscribed = int(chat_id) in load_notification_chat_ids()
    subscription_text = "включены" if subscribed else "выключены"
    auto_refresh_text = (
        format_daily_schedule_text(settings.daily_time, settings.timezone_name)
        if settings.enabled
        else "выключено"
    )
    return render_card(
        "🔔 Статус уведомлений",
        [
            "Для этого чата: {0}".format(subscription_text),
            "Автообновление: {0}".format(auto_refresh_text),
            "Google Sheets: {0}".format("включено" if settings.update_sheets else "выключено"),
        ],
    )


def build_examples_keyboard() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(example, callback_data="{0}{1}".format(CALLBACK_EXAMPLE_PREFIX, index))]
        for index, example in enumerate(EXAMPLE_QUERIES)
    ]
    rows.append([InlineKeyboardButton("🏠 Назад в меню", callback_data=CALLBACK_MENU_MAIN)])
    return InlineKeyboardMarkup(rows)


def format_access_counts(config: AccessConfig) -> str:
    return "{0} user_id, {1} chat_id".format(
        len(config.allowed_user_ids),
        len(config.allowed_chat_ids),
    )


def format_id_preview(values: frozenset[int], *, limit: int = 6) -> str:
    ordered = [str(value) for value in sorted(values)]
    if not ordered:
        return "нет"
    preview = ", ".join(ordered[:limit])
    if len(ordered) > limit:
        preview += " + ещё {0}".format(len(ordered) - limit)
    return preview


def extend_access_section(lines: list[str], title: str, config: AccessConfig) -> None:
    lines.append(title)
    lines.append("• user_id: {0}".format(format_id_preview(config.allowed_user_ids)))
    lines.append("• chat_id: {0}".format(format_id_preview(config.allowed_chat_ids)))


def build_admin_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("📋 Обзор", callback_data=CALLBACK_ADMIN_MENU),
                InlineKeyboardButton("👥 Доступы", callback_data=CALLBACK_ADMIN_LIST),
            ],
            [
                InlineKeyboardButton("📝 Заявки", callback_data=CALLBACK_ADMIN_REQUESTS),
                InlineKeyboardButton("✖️ Сбросить действие", callback_data=CALLBACK_ADMIN_CANCEL),
            ],
            [
                InlineKeyboardButton("➕ Выдать user_id", callback_data=CALLBACK_ADMIN_ADD_USER),
                InlineKeyboardButton("➕ Выдать chat_id", callback_data=CALLBACK_ADMIN_ADD_CHAT),
            ],
            [
                InlineKeyboardButton("➖ Убрать user_id", callback_data=CALLBACK_ADMIN_REMOVE_USER),
                InlineKeyboardButton("➖ Убрать chat_id", callback_data=CALLBACK_ADMIN_REMOVE_CHAT),
            ],
            [
                InlineKeyboardButton("🏠 Назад в меню", callback_data=CALLBACK_MENU_MAIN),
            ],
        ]
    )


def build_admin_panel_text() -> str:
    merged = read_access_config()
    env_config = read_env_access_config()
    stored = read_stored_access_config()
    explicit_admin = read_explicit_admin_config()
    pending_count = len(load_pending_access_requests())
    admin_mode_text = (
        "Админка использует отдельный список админов."
        if explicit_admin.enabled
        else "Отдельный список админов не задан: используется основной allowlist."
    )
    return render_card(
        "🛂 Доступ и права",
        [
            "Краткая сводка по доступам и заявкам.",
            "• Всего разрешено: {0}".format(format_access_counts(merged)),
            "• База из .env: {0}".format(format_access_counts(env_config)),
            "• Выдано через панель: {0}".format(format_access_counts(stored)),
            "• Заявок ждут решения: {0}".format(pending_count),
            admin_mode_text,
            "Попросите пользователя отправить /whoami или номер телефона, чтобы быстро выдать доступ.",
        ],
    )


def build_admin_list_text() -> str:
    merged = read_access_config()
    env_config = read_env_access_config()
    stored = read_stored_access_config()
    lines = [
        "Итоговый список доступа по боту.",
        "• Всего разрешено: {0}".format(format_access_counts(merged)),
    ]
    extend_access_section(lines, "Сейчас разрешено:", merged)
    extend_access_section(lines, "База из .env:", env_config)
    extend_access_section(lines, "Выдано через панель:", stored)
    return render_card(
        "👥 Доступы",
        lines,
    )


def build_admin_requests_text() -> str:
    requests = load_pending_access_requests()
    if not requests:
        return render_card(
            "📝 Заявки",
            [
                "Сейчас новых заявок нет.",
                "Когда пользователь отправит номер, здесь и в чате появится карточка с кнопками решения.",
            ],
        )

    lines = [
        "Ожидают решения: {0}".format(len(requests)),
        "Карточки заявок с кнопками уже отправляются в чат админов.",
    ]
    for index, request in enumerate(requests[:6], start=1):
        username_text = "@{0}".format(request.username) if request.username else "без username"
        lines.append(
            "{0}. {1} · {2}".format(
                index,
                request.full_name or "без имени",
                request.phone_number or "без номера",
            )
        )
        lines.append(
            "   user_id {0} · chat_id {1} · {2}".format(
                request.user_id,
                request.chat_id,
                username_text,
            )
        )
        lines.append("   запрос: {0}".format(request.requested_at))
    if len(requests) > 6:
        lines.append("И ещё ожидают решения: {0}".format(len(requests) - 6))
    return render_card("📝 Заявки", lines)


def build_admin_input_prompt(action: str) -> str:
    if action == ADMIN_ACTION_ADD_USER:
        return render_card(
            "➕ Выдать user_id",
            [
                "Пришлите user_id, которому нужно открыть доступ.",
                "Самый удобный способ: попросить человека отправить /whoami.",
                "Для выхода нажмите «Сбросить действие» или напишите «отмена».",
            ],
        )
    if action == ADMIN_ACTION_ADD_CHAT:
        return render_card(
            "➕ Выдать chat_id",
            [
                "Пришлите chat_id, которому нужно открыть доступ.",
                "Для группы или канала удобно сначала получить его через /whoami.",
                "Для выхода нажмите «Сбросить действие» или напишите «отмена».",
            ],
        )
    if action == ADMIN_ACTION_REMOVE_USER:
        return render_card(
            "➖ Убрать user_id",
            [
                "Пришлите user_id, который нужно убрать из доступа.",
                "Для выхода нажмите «Сбросить действие» или напишите «отмена».",
            ],
        )
    if action == ADMIN_ACTION_REMOVE_CHAT:
        return render_card(
            "➖ Убрать chat_id",
            [
                "Пришлите chat_id, который нужно убрать из доступа.",
                "Для выхода нажмите «Сбросить действие» или напишите «отмена».",
            ],
        )
    return build_admin_panel_text()


def build_admin_result_text(success_text: str) -> str:
    merged = read_access_config()
    pending_count = len(load_pending_access_requests())
    return render_card(
        "✅ Готово",
        [
            success_text,
            "• Сейчас разрешено: {0}".format(format_access_counts(merged)),
            "• Заявок в ожидании: {0}".format(pending_count),
            "Для деталей откройте `Доступы` или `Заявки`.",
        ],
    )


def build_access_request_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [[KeyboardButton("Отправить номер для доступа", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True,
        input_field_placeholder="Нажмите кнопку, чтобы отправить номер",
    )


def build_access_request_admin_keyboard(request_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Одобрить", callback_data="{0}{1}".format(CALLBACK_REQUEST_APPROVE_PREFIX, request_id)),
                InlineKeyboardButton("Отклонить", callback_data="{0}{1}".format(CALLBACK_REQUEST_DENY_PREFIX, request_id)),
            ]
        ]
    )


async def send_access_request_prompt(message: Message) -> None:
    chat = message.chat
    if chat.type != "private":
        await message.reply_text(
            "Доступ к этому боту ограничен.\n"
            "Напишите боту в личные сообщения и отправьте номер через кнопку, чтобы запросить доступ.",
        )
        return

    await message.reply_text(
        "Доступ к этому боту ограничен.\n"
        "Если хотите запросить доступ, нажмите кнопку ниже и отправьте свой номер. Админу придёт заявка с кнопками одобрения.",
        reply_markup=build_access_request_keyboard(),
    )


async def process_access_request_contact(
    message: Message,
    *,
    user_id: int,
    contact: Contact,
    application: Application,
) -> None:
    if contact.user_id not in {None, user_id}:
        await message.reply_text(
            "Нужно отправить именно свой контакт через кнопку Telegram.",
            reply_markup=build_access_request_keyboard(),
        )
        return

    chat = message.chat
    user = message.from_user
    requested_at = datetime.now().astimezone().replace(microsecond=0).isoformat()
    request = create_or_refresh_access_request(
        DEFAULT_ACCESS_REQUESTS_PATH,
        user_id=user_id,
        chat_id=chat.id,
        username=user.username if user else None,
        full_name=user.full_name if user else "",
        phone_number=contact.phone_number or "",
        requested_at=requested_at,
    )
    notified_count = await notify_admins_about_access_request(application, request)
    if notified_count > 0:
        await message.reply_text(
            "Заявка отправлена администратору. Как только он примет решение, я напишу сюда.",
            reply_markup=build_main_keyboard(),
        )
    else:
        await message.reply_text(
            "Заявка сохранена, но админ-получатель ещё не настроен.\n"
            "Попросите владельца бота указать COMPETITOR_PRICE_ADMIN_USER_IDS и перезапустить бота.",
            reply_markup=build_main_keyboard(),
        )


async def notify_admins_about_access_request(application: Application, request: AccessRequest) -> int:
    admin_ids = collect_admin_recipient_ids()
    if not admin_ids:
        logger.warning("Access request created, but admin recipients are not configured")
        return 0

    text = format_access_request_for_admin(request)
    reply_markup = build_access_request_admin_keyboard(request.request_id)
    sent_count = 0
    for chat_id in admin_ids:
        try:
            await application.bot.send_message(chat_id=chat_id, text=text, reply_markup=reply_markup)
            sent_count += 1
        except TelegramError as error:
            logger.warning("Failed to notify admin chat %s about access request: %s", chat_id, error)
    return sent_count


def collect_admin_recipient_ids() -> list[int]:
    config = read_admin_config()
    ids = set(config.allowed_user_ids) | set(config.allowed_chat_ids)
    return sorted(ids)


def load_pending_access_requests() -> list[AccessRequest]:
    requests = list(load_access_requests_map().values())
    return sorted(
        [request for request in requests if request.status == "pending"],
        key=lambda item: item.requested_at,
        reverse=True,
    )


async def handle_access_request_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    message = update.effective_message
    admin = update.effective_user
    if query is None or message is None:
        return

    data = query.data or ""
    approved = data.startswith(CALLBACK_REQUEST_APPROVE_PREFIX)
    request_id = data.split(":", 2)[-1]
    request = get_access_request(DEFAULT_ACCESS_REQUESTS_PATH, request_id)
    if request is None:
        await safe_answer_callback_query(query, "Заявка не найдена", show_alert=True)
        return
    if request.status != "pending":
        await safe_answer_callback_query(query, "Эта заявка уже обработана", show_alert=True)
        return

    if approved:
        updated_access = add_allowed_user(read_stored_access_config(), request.user_id)
        updated_access = add_allowed_chat(updated_access, request.chat_id)
        write_stored_access_config(updated_access)
        decision_text = "одобрена"
        user_text = (
            "Доступ одобрен.\n"
            "Теперь вы можете пользоваться ботом."
        )
        status = "approved"
    else:
        decision_text = "отклонена"
        user_text = "Заявка на доступ отклонена администратором."
        status = "denied"

    updated_request = update_access_request_status(
        DEFAULT_ACCESS_REQUESTS_PATH,
        request_id,
        status=status,
        reviewed_at=datetime.now().astimezone().replace(microsecond=0).isoformat(),
        reviewed_by=admin.id if admin else None,
    )
    await safe_answer_callback_query(query, "Заявка {0}".format(decision_text))

    status_line = "Статус: {0}".format("одобрена" if approved else "отклонена")
    await message.edit_text(
        "{0}\n\n{1}".format(format_access_request_for_admin(request), status_line)
    )

    try:
        await context.application.bot.send_message(
            chat_id=request.chat_id,
            text=user_text,
            reply_markup=build_main_keyboard() if approved else build_access_request_keyboard(),
        )
    except TelegramError as error:
        logger.warning("Failed to notify requester %s about access decision: %s", request.chat_id, error)

    if approved:
        register_notification_chat(request.chat_id)


DEFAULT_SOURCE_CATALOG_PATH = Path(__file__).resolve().parent / "config" / "products.ilab_template.csv"
DEFAULT_RUNTIME_SOURCE_CATALOG_PATH = Path(__file__).resolve().parent / "data" / "runtime_source_catalog.csv"
RUNTIME_SOURCE_REFRESH_TIMEOUT_SECONDS = 20
GOOGLE_SHEETS_SYNC_TIMEOUT_SECONDS = 60


def build_comparison_export_path() -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return DEFAULT_EXPORT_PATH.with_name("price_comparison_matrix_{0}.csv".format(timestamp))


def get_refresh_lock(application: Application) -> asyncio.Lock:
    lock = application.bot_data.get(REFRESH_LOCK_KEY)
    if lock is None:
        lock = asyncio.Lock()
        application.bot_data[REFRESH_LOCK_KEY] = lock
    return lock


def get_refresh_state(application: Application) -> Optional[RefreshState]:
    state = application.bot_data.get(REFRESH_STATE_KEY)
    if isinstance(state, RefreshState):
        return state
    return None


def set_refresh_state(application: Application, state: Optional[RefreshState]) -> None:
    if state is None:
        application.bot_data.pop(REFRESH_STATE_KEY, None)
        return
    application.bot_data[REFRESH_STATE_KEY] = state


def request_refresh_cancel(application: Application, chat_id: int) -> str:
    state = get_refresh_state(application)
    if state is None:
        return "Сейчас нет активной выгрузки."
    if state.owner_chat_id is not None and state.owner_chat_id != chat_id:
        return "Сейчас выполняется выгрузка из другого чата. Её можно остановить только там."
    if state.cancel_event.is_set():
        return "Остановка уже запрошена. Жду завершения активных запросов."
    state.cancel_event.set()
    return "Останавливаю выгрузку. Текущие активные запросы завершу и остановлю процесс."


def is_refresh_busy(application: Application) -> bool:
    return get_refresh_lock(application).locked()


async def execute_refresh_cycle(
    application: Application,
    update_sheets: bool,
    progress_message: Optional[Message] = None,
    allow_missing_sheets: bool = False,
    owner_chat_id: Optional[int] = None,
) -> RefreshRunResult:
    lock = get_refresh_lock(application)
    if lock.locked():
        raise RuntimeError("Обновление уже запущено.")

    async with lock:
        refresh_state = RefreshState(
            owner_chat_id=owner_chat_id,
            kind="sheets" if update_sheets else "csv",
            cancel_event=Event(),
            status_chat_id=progress_message.chat_id if progress_message is not None else None,
            status_message_id=progress_message.message_id if progress_message is not None else None,
        )
        set_refresh_state(application, refresh_state)
        progress_task: Optional[asyncio.Task] = None
        try:
            if progress_message is not None:
                await update_status_message(
                    progress_message,
                    render_card("⏳ Этап 1/3", ["Готовлю список моделей для проверки."]),
                    build_running_action_keyboard(),
                )
            source_catalog_path = await refresh_runtime_source_catalog_path(progress_message)
            if refresh_state.cancel_event.is_set():
                raise ExportCancelledError("Выгрузка отменена пользователем.")
            devices = load_supported_devices(source_catalog_path)
            if progress_message is not None:
                await update_status_message(
                    progress_message,
                    render_card(
                        "🔎 Этап 2/3",
                        ["Список моделей готов.", "Начинаю сбор цен по магазинам."],
                    ),
                    build_running_action_keyboard(),
                )
            export_path = build_comparison_export_path()
            export_task = asyncio.create_task(
                asyncio.to_thread(
                    export_price_comparison_csv,
                    export_path,
                    source_catalog_path,
                    compare_query_text,
                    refresh_state.cancel_event,
                )
            )
            if progress_message is not None:
                progress_task = asyncio.create_task(
                    report_export_progress(
                        progress_message,
                        export_path,
                        len(devices),
                        export_task,
                        refresh_state.cancel_event,
                    )
                )

            await export_task
            spreadsheet_url = None
            sheet_error = None

            if update_sheets:
                if refresh_state.cancel_event.is_set():
                    raise ExportCancelledError("Выгрузка отменена пользователем.")
                if progress_message is not None:
                    await update_status_message(
                        progress_message,
                        render_card("📤 Этап 3/3", ["Цены собраны.", "Обновляю Google Sheets."]),
                        build_running_action_keyboard(),
                    )
                try:
                    sheets_config = read_google_sheets_config()
                    spreadsheet_url = await asyncio.wait_for(
                        asyncio.to_thread(
                            sync_exports_to_google_sheets,
                            sheets_config,
                            export_path,
                            source_catalog_path,
                        ),
                        timeout=GOOGLE_SHEETS_SYNC_TIMEOUT_SECONDS,
                    )
                except RuntimeError as error:
                    if not allow_missing_sheets:
                        raise
                    sheet_error = str(error)
                    logger.warning("Skipping Google Sheets auto-sync: %s", error)
                except asyncio.TimeoutError:
                    sheet_error = "Google Sheets отвечает слишком долго, обновление листа пропущено."
                    logger.warning("Google Sheets sync timed out")
                    if not allow_missing_sheets:
                        raise RuntimeError(sheet_error)
                except Exception as error:  # noqa: BLE001
                    if not allow_missing_sheets:
                        raise
                    sheet_error = str(error)
                    logger.exception("Automatic Google Sheets sync failed")

            changes = await asyncio.to_thread(
                load_price_change_events,
                build_details_export_path(export_path),
                source_catalog_path,
            )
            return RefreshRunResult(
                export_path=export_path,
                spreadsheet_url=spreadsheet_url,
                sheet_error=sheet_error,
                changes_count=len(changes),
                devices_count=len(devices),
            )
        finally:
            if progress_task is not None:
                progress_task.cancel()
                with suppress(asyncio.CancelledError):
                    await progress_task
            set_refresh_state(application, None)


async def auto_refresh_loop(application: Application) -> None:
    settings = read_auto_refresh_config()
    if not settings.enabled:
        logger.info("Auto refresh is disabled")
        return

    logger.info(
        "Auto refresh started: schedule=%s, update_sheets=%s, run_on_start=%s",
        format_daily_schedule_text(settings.daily_time, settings.timezone_name),
        settings.update_sheets,
        settings.run_on_start,
    )

    try:
        if settings.run_on_start:
            await asyncio.sleep(10)
            await run_auto_refresh_cycle(application, settings)

        while True:
            delay_seconds = seconds_until_next_daily_run(
                daily_time=settings.daily_time,
                timezone_name=settings.timezone_name,
            )
            next_run = calculate_next_daily_run(
                daily_time=settings.daily_time,
                timezone_name=settings.timezone_name,
            )
            logger.info("Next auto refresh scheduled for %s", next_run.isoformat())
            await asyncio.sleep(delay_seconds)
            await run_auto_refresh_cycle(application, settings)
    except asyncio.CancelledError:
        logger.info("Auto refresh loop stopped")
        raise


async def run_auto_refresh_cycle(application: Application, settings: AutoRefreshConfig) -> None:
    if is_refresh_busy(application):
        logger.info("Skipping auto refresh because another refresh is already running")
        return

    chat_ids = sorted(load_notification_chat_ids())
    if not chat_ids and not settings.update_sheets:
        logger.info("Skipping auto refresh because there are no subscribers and sheets update is disabled")
        return

    try:
        result = await execute_refresh_cycle(
            application,
            update_sheets=settings.update_sheets,
            progress_message=None,
            allow_missing_sheets=True,
        )
        changes = await asyncio.to_thread(
            load_price_change_events,
            build_details_export_path(result.export_path),
            resolve_runtime_source_catalog_path(),
        )
    except Exception as error:  # noqa: BLE001
        logger.exception("Auto refresh failed")
        if chat_ids:
            await broadcast_messages(
                application,
                chat_ids,
                ["Автообновление цен завершилось с ошибкой: {0}".format(error)],
            )
        return

    messages = format_price_change_messages(changes, result.spreadsheet_url)
    if result.sheet_error:
        messages.append("Google Sheets не обновлён: {0}".format(result.sheet_error))

    if messages and chat_ids:
        await broadcast_messages(application, chat_ids, messages)
    else:
        logger.info("Auto refresh finished without price changes")


async def broadcast_messages(application: Application, chat_ids: list[int], messages: list[str]) -> None:
    if not chat_ids or not messages:
        return

    for chat_id in list(chat_ids):
        for text in messages:
            try:
                await application.bot.send_message(chat_id=chat_id, text=text, reply_markup=build_action_keyboard())
            except Forbidden:
                logger.warning("Chat %s blocked the bot, removing from notifications", chat_id)
                unregister_notification_chat(chat_id)
                break
            except TelegramError as error:
                logger.warning("Failed to send auto-refresh message to chat %s: %s", chat_id, error)
                break


def is_expired_callback_error(error: BaseException) -> bool:
    if not isinstance(error, BadRequest):
        return False
    message = str(error).lower()
    return "query is too old" in message or "query id is invalid" in message


async def safe_answer_callback_query(
    query,
    text: Optional[str] = None,
    show_alert: bool = False,
) -> bool:
    try:
        await query.answer(text=text, show_alert=show_alert)
        return True
    except BadRequest as error:
        if is_expired_callback_error(error):
            logger.info("Ignoring expired callback query for data=%s", getattr(query, "data", None))
            return False
        raise


async def report_export_progress(
    message: Message,
    export_path: Path,
    total_devices: int,
    export_task: asyncio.Task,
    cancel_event: Event,
) -> None:
    last_reported_count = 0
    stalled_intervals = 0
    cancellation_notice_sent = False

    while not export_task.done():
        await asyncio.sleep(20)
        if cancel_event.is_set():
            if not cancellation_notice_sent:
                await update_status_message(
                    message,
                    render_card(
                        "⛔ Остановка запрошена",
                        [
                            "Новые товары больше не запускаю.",
                            "Жду завершения уже начатых запросов.",
                        ],
                    ),
                    build_cancelling_action_keyboard(),
                )
                cancellation_notice_sent = True
            return
        exported_count = count_exported_rows(export_path)
        if exported_count >= last_reported_count + 10:
            await update_status_message(
                message,
                render_card(
                    "🔄 Идёт сбор цен",
                    ["Готово {0}/{1} моделей.".format(exported_count, total_devices)],
                ),
                build_running_action_keyboard(),
            )
            last_reported_count = exported_count
            stalled_intervals = 0
            continue

        if exported_count == last_reported_count:
            stalled_intervals += 1
            if stalled_intervals == 3:
                await update_status_message(
                    message,
                    render_card(
                        "⌛ Медленный ответ сайтов",
                        [
                            "Некоторые источники отвечают дольше обычного.",
                            "Продолжаю сборку и пропускаю проблемные ответы по таймауту.",
                        ],
                    ),
                    build_running_action_keyboard(),
                )


def count_exported_rows(export_path: Path) -> int:
    if not export_path.exists():
        return 0

    with export_path.open("r", encoding="utf-8", newline="") as handle:
        line_count = sum(1 for _ in handle)

    return max(0, line_count - 1)


async def maybe_handle_admin_input(
    message: Message,
    text: str,
    context: ContextTypes.DEFAULT_TYPE,
) -> bool:
    action = get_admin_pending_action(context)
    if action is None:
        return False

    normalized = text.strip().lower()
    if normalized in {"отмена", "cancel", "/cancel"}:
        clear_admin_pending_action(context)
        await show_panel(
            context,
            chat_id=message.chat_id,
            text=build_admin_panel_text(),
            reply_markup=build_admin_keyboard(),
            message=message,
        )
        return True

    try:
        target_id = int(text.strip())
    except ValueError:
        await show_panel(
            context,
            chat_id=message.chat_id,
            text=render_card(
                "⚠️ Нужен числовой ID",
                [
                    "Ожидаю целый user_id или chat_id числом.",
                    "Пример: 123456789 или -1001234567890.",
                    "Для выхода нажмите «Сбросить действие» или напишите «отмена».",
                ],
            ),
            reply_markup=build_admin_keyboard(),
            message=message,
        )
        return True

    store_config = read_stored_access_config()
    env_config = read_env_access_config()
    if action == ADMIN_ACTION_ADD_USER:
        updated = add_allowed_user(store_config, target_id)
        success_text = "Доступ выдан пользователю `{0}`.".format(target_id)
    elif action == ADMIN_ACTION_ADD_CHAT:
        updated = add_allowed_chat(store_config, target_id)
        success_text = "Доступ выдан чату `{0}`.".format(target_id)
    elif action == ADMIN_ACTION_REMOVE_USER:
        updated = remove_allowed_user(store_config, target_id)
        success_text = "Пользователь `{0}` убран из доступа.".format(target_id)
        if target_id in env_config.allowed_user_ids:
            success_text += "\nНо этот user_id всё ещё разрешён через `.env`."
    elif action == ADMIN_ACTION_REMOVE_CHAT:
        updated = remove_allowed_chat(store_config, target_id)
        success_text = "Чат `{0}` убран из доступа.".format(target_id)
        if target_id in env_config.allowed_chat_ids:
            success_text += "\nНо этот chat_id всё ещё разрешён через `.env`."
    else:
        clear_admin_pending_action(context)
        return False

    write_stored_access_config(updated)
    clear_admin_pending_action(context)
    await show_panel(
        context,
        chat_id=message.chat_id,
        text=build_admin_result_text(success_text),
        reply_markup=build_admin_keyboard(),
        message=message,
    )
    return True


def load_notification_chat_ids(path: Path = DEFAULT_SUBSCRIBERS_PATH) -> set[int]:
    if not path.exists():
        return set()

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        logger.warning("Failed to decode subscriber list from %s", path)
        return set()

    result = set()
    for item in raw:
        try:
            result.add(int(item))
        except (TypeError, ValueError):
            continue
    return result


def save_notification_chat_ids(chat_ids: set[int], path: Path = DEFAULT_SUBSCRIBERS_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(sorted(chat_ids), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def register_notification_chat(chat_id: int, path: Path = DEFAULT_SUBSCRIBERS_PATH) -> bool:
    chat_ids = load_notification_chat_ids(path)
    before = len(chat_ids)
    chat_ids.add(int(chat_id))
    if len(chat_ids) != before:
        save_notification_chat_ids(chat_ids, path)
        return True
    return False


def unregister_notification_chat(chat_id: int, path: Path = DEFAULT_SUBSCRIBERS_PATH) -> bool:
    chat_ids = load_notification_chat_ids(path)
    if int(chat_id) not in chat_ids:
        return False
    chat_ids.remove(int(chat_id))
    save_notification_chat_ids(chat_ids, path)
    return True


def read_stored_access_config(path: Path = DEFAULT_ACCESS_STORE_PATH) -> AccessConfig:
    return load_access_store(path)


def write_stored_access_config(config: AccessConfig, path: Path = DEFAULT_ACCESS_STORE_PATH) -> None:
    save_access_store(config, path)


def load_access_requests_map(path: Path = DEFAULT_ACCESS_REQUESTS_PATH) -> dict[str, AccessRequest]:
    from competitor_price_monitor.access_requests import load_access_requests

    return load_access_requests(path)


def set_admin_pending_action(context: ContextTypes.DEFAULT_TYPE, action: str) -> None:
    context.user_data[ADMIN_PENDING_ACTION_KEY] = action


def get_admin_pending_action(context: ContextTypes.DEFAULT_TYPE) -> Optional[str]:
    value = context.user_data.get(ADMIN_PENDING_ACTION_KEY)
    if not value:
        return None
    return str(value)


def clear_admin_pending_action(context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data.pop(ADMIN_PENDING_ACTION_KEY, None)


def read_env_value(key: str) -> Optional[str]:
    value = os.getenv(key, "").strip()
    if value:
        return value

    env_path = Path(__file__).resolve().parent / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            raw = line.strip()
            if not raw or raw.startswith("#") or "=" not in raw:
                continue
            env_key, env_value = raw.split("=", 1)
            if env_key.strip() == key:
                clean_value = env_value.strip().strip('"').strip("'")
                if clean_value:
                    return clean_value

    return None


def read_bool_env(key: str, default: bool) -> bool:
    raw = read_env_value(key)
    if raw is None:
        return default

    normalized = raw.strip().lower()
    if normalized in {"1", "true", "yes", "y", "on"}:
        return True
    if normalized in {"0", "false", "no", "n", "off"}:
        return False
    return default


def read_env_access_config() -> AccessConfig:
    return build_access_config(
        allowed_user_ids=parse_id_list(read_env_value("COMPETITOR_PRICE_ALLOWED_USER_IDS")),
        allowed_chat_ids=parse_id_list(read_env_value("COMPETITOR_PRICE_ALLOWED_CHAT_IDS")),
    )


def read_explicit_admin_config() -> AccessConfig:
    return build_access_config(
        allowed_user_ids=parse_id_list(read_env_value("COMPETITOR_PRICE_ADMIN_USER_IDS")),
        allowed_chat_ids=parse_id_list(read_env_value("COMPETITOR_PRICE_ADMIN_CHAT_IDS")),
    )


def read_access_config() -> AccessConfig:
    return merge_access_configs(
        read_env_access_config(),
        read_stored_access_config(),
    )


def read_admin_config() -> AccessConfig:
    explicit_admin_config = read_explicit_admin_config()
    if explicit_admin_config.enabled:
        return explicit_admin_config
    return read_env_access_config()


def read_auto_refresh_config() -> AutoRefreshConfig:
    enabled = read_bool_env("COMPETITOR_PRICE_AUTO_REFRESH_ENABLED", True)
    update_sheets = read_bool_env("COMPETITOR_PRICE_AUTO_REFRESH_UPDATE_SHEETS", True)
    run_on_start = read_bool_env("COMPETITOR_PRICE_AUTO_REFRESH_RUN_ON_START", False)
    daily_time = normalize_daily_time(
        read_env_value("COMPETITOR_PRICE_AUTO_REFRESH_DAILY_TIME") or DEFAULT_DAILY_TIME
    )
    timezone_name = read_env_value("COMPETITOR_PRICE_AUTO_REFRESH_TIMEZONE") or DEFAULT_TIMEZONE_NAME
    return AutoRefreshConfig(
        enabled=enabled,
        daily_time=daily_time,
        timezone_name=timezone_name,
        update_sheets=update_sheets,
        run_on_start=run_on_start,
    )


def resolve_runtime_source_catalog_path() -> Path:
    try:
        read_google_sheets_config()
    except RuntimeError:
        return DEFAULT_SOURCE_CATALOG_PATH

    if DEFAULT_RUNTIME_SOURCE_CATALOG_PATH.exists():
        return DEFAULT_RUNTIME_SOURCE_CATALOG_PATH
    return DEFAULT_SOURCE_CATALOG_PATH


async def refresh_runtime_source_catalog_path(progress_message: Optional[Message] = None) -> Path:
    try:
        sheets_config = read_google_sheets_config()
    except RuntimeError:
        return DEFAULT_SOURCE_CATALOG_PATH

    try:
        comparison_name = (sheets_config.comparison_worksheet_name or "").strip().upper()
        if comparison_name == "__FIRST__":
            return await asyncio.wait_for(
                asyncio.to_thread(
                    export_source_catalog_from_first_worksheet,
                    sheets_config,
                    DEFAULT_RUNTIME_SOURCE_CATALOG_PATH,
                    DEFAULT_SOURCE_CATALOG_PATH,
                ),
                timeout=RUNTIME_SOURCE_REFRESH_TIMEOUT_SECONDS,
            )
        return await asyncio.wait_for(
            asyncio.to_thread(
                export_source_catalog_from_catalog_worksheet,
                sheets_config,
                DEFAULT_RUNTIME_SOURCE_CATALOG_PATH,
            ),
            timeout=RUNTIME_SOURCE_REFRESH_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        fallback_path = resolve_runtime_source_catalog_path()
        logger.warning("Timed out building runtime source catalog from Google Sheets, fallback to %s", fallback_path)
        if progress_message is not None and fallback_path.exists():
            await update_status_message(
                progress_message,
                "Google Sheets слишком долго отдаёт список моделей. Беру последний сохранённый список и продолжаю.",
                build_running_action_keyboard(),
            )
        return fallback_path
    except Exception as error:  # noqa: BLE001
        fallback_path = resolve_runtime_source_catalog_path()
        logger.warning(
            "Failed to build runtime source catalog from Google Sheets, fallback to %s: %s",
            fallback_path,
            error,
        )
        return fallback_path


def read_token(token_env: str) -> str:
    token = read_env_value(token_env)
    if token:
        return token

    raise RuntimeError(
        "Telegram token not found. Set {0} in environment or competitor_price_monitor/.env".format(
            token_env
        )
    )


def ensure_telegram_api_host_resolves(hostname: str = "api.telegram.org") -> None:
    try:
        socket.getaddrinfo(hostname, 443, type=socket.SOCK_STREAM)
    except OSError as error:
        raise RuntimeError(
            "Не удаётся подключиться к Telegram API.\n"
            "Проверьте интернет, DNS/VPN/прокси и доступ к {0}.".format(hostname)
        ) from error


def read_google_sheets_config() -> GoogleSheetsConfig:
    project_root = Path(__file__).resolve().parent
    spreadsheet_id = _normalize_spreadsheet_id(
        read_env_value("COMPETITOR_PRICE_GOOGLE_SHEETS_ID") or ""
    )
    credentials_raw = read_env_value("COMPETITOR_PRICE_GOOGLE_CREDENTIALS_PATH") or ""
    comparison_worksheet_name = (
        read_env_value("COMPETITOR_PRICE_GOOGLE_COMPARISON_WORKSHEET") or "Сравнение цен"
    )
    catalog_worksheet_name = (
        read_env_value("COMPETITOR_PRICE_GOOGLE_CATALOG_WORKSHEET") or "Список моделей"
    )

    if not spreadsheet_id or not credentials_raw:
        raise RuntimeError(
            "Google Sheets не настроен.\n"
            "Добавьте в competitor_price_monitor/.env:\n"
            "COMPETITOR_PRICE_GOOGLE_SHEETS_ID=ваш_spreadsheet_id\n"
            "COMPETITOR_PRICE_GOOGLE_CREDENTIALS_PATH=\"/полный/путь/до/google-service-account.json\""
        )
    if spreadsheet_id in {"ваш_spreadsheet_id", "put_your_google_spreadsheet_id_here"}:
        raise RuntimeError(
            "В COMPETITOR_PRICE_GOOGLE_SHEETS_ID всё ещё стоит шаблонное значение.\n"
            "Нужно вставить настоящий spreadsheet_id из ссылки Google Sheets:\n"
            "https://docs.google.com/spreadsheets/d/ВОТ_ЭТО_ID/edit"
        )

    credentials_path = Path(credentials_raw).expanduser()
    if not credentials_path.is_absolute():
        credentials_path = (project_root / credentials_path).resolve()
    if not credentials_path.exists():
        raise RuntimeError(
            "Файл сервисного аккаунта Google не найден: {0}".format(credentials_path)
        )

    return GoogleSheetsConfig(
        enabled=True,
        spreadsheet_id=spreadsheet_id,
        comparison_worksheet_name=comparison_worksheet_name,
        catalog_worksheet_name=catalog_worksheet_name,
        credentials_path=str(credentials_path),
    )


def _normalize_spreadsheet_id(value: str) -> str:
    raw = value.strip().strip('"').strip("'")
    match = re.search(r"/spreadsheets/d/([a-zA-Z0-9-_]+)", raw)
    if match:
        return match.group(1)
    return raw


def classify_transient_telegram_network_error(error: BaseException) -> Optional[str]:
    if isinstance(error, ssl.SSLError):
        return "Временный SSL-сбой при связи с Telegram. Продолжаю переподключение."

    if not isinstance(error, NetworkError):
        return None

    message = str(error).lower()
    if "record layer failure" in message or "ssl" in message:
        return "Временный SSL-сбой при связи с Telegram. Продолжаю переподключение."
    if "remoteprotocolerror" in message or "server disconnected without sending a response" in message:
        return "Telegram оборвал соединение без ответа. Продолжаю переподключение."
    if "timed out" in message:
        return "Telegram отвечает слишком долго. Продолжаю переподключение."
    if (
        "connecterror" in message
        or "nodename nor servname provided" in message
        or "temporary failure in name resolution" in message
        or "name resolution" in message
    ):
        return "Проблема сети или DNS при связи с Telegram. Продолжаю переподключение."
    return "Временная сетевая ошибка Telegram. Продолжаю переподключение."


def log_transient_network_warning(summary: str, error: BaseException) -> None:
    global LAST_NETWORK_ERROR_SIGNATURE, LAST_NETWORK_ERROR_TS

    detail = str(error).strip()
    signature = "{0}|{1}".format(summary, detail)
    now = time.monotonic()
    if (
        signature == LAST_NETWORK_ERROR_SIGNATURE
        and (now - LAST_NETWORK_ERROR_TS) < NETWORK_ERROR_LOG_DEDUP_SECONDS
    ):
        return

    LAST_NETWORK_ERROR_SIGNATURE = signature
    LAST_NETWORK_ERROR_TS = now
    logger.warning("%s Детали: %s", summary, detail)


def should_suppress_asyncio_exception(context: dict) -> bool:
    error = context.get("exception")
    message = str(error or context.get("message") or "")
    lowered = message.lower()
    if "connection.init: connection closed while reading from the driver" in lowered:
        return True
    if "task exception was never retrieved" in lowered and "playwright" in lowered:
        return True
    return False


def build_asyncio_exception_handler(previous_handler):
    def _handler(loop: asyncio.AbstractEventLoop, context: dict) -> None:
        if should_suppress_asyncio_exception(context):
            logger.debug(
                "Ignoring noisy asyncio/playwright shutdown error: %s",
                context.get("exception") or context.get("message"),
            )
            return

        if previous_handler is not None:
            previous_handler(loop, context)
            return

        loop.default_exception_handler(context)

    return _handler


async def handle_application_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    error = context.error
    if error is None:
        return

    if is_expired_callback_error(error):
        logger.info("Ignoring expired callback query error from application handler")
        return

    transient_network_summary = classify_transient_telegram_network_error(error)
    if transient_network_summary:
        log_transient_network_warning(transient_network_summary, error)
        return

    logger.error(
        "Unhandled Telegram application error",
        exc_info=(type(error), error, error.__traceback__),
    )


async def post_init(application: Application) -> None:
    get_refresh_lock(application)
    loop = asyncio.get_running_loop()
    previous_handler = loop.get_exception_handler()
    loop.set_exception_handler(build_asyncio_exception_handler(previous_handler))
    application.bot_data[ASYNCIO_PREVIOUS_EXCEPTION_HANDLER_KEY] = previous_handler
    settings = read_auto_refresh_config()
    if settings.enabled:
        application.bot_data[AUTO_REFRESH_TASK_KEY] = asyncio.create_task(auto_refresh_loop(application))


async def post_shutdown(application: Application) -> None:
    loop = asyncio.get_running_loop()
    previous_handler = application.bot_data.get(ASYNCIO_PREVIOUS_EXCEPTION_HANDLER_KEY)
    loop.set_exception_handler(previous_handler)

    task = application.bot_data.get(AUTO_REFRESH_TASK_KEY)
    if task is None:
        return
    task.cancel()
    with suppress(asyncio.CancelledError):
        await task


def build_application(token: str) -> Application:
    application = (
        Application.builder()
        .token(token)
        .http_version("1.1")
        .get_updates_http_version("1.1")
        .connect_timeout(15.0)
        .read_timeout(20.0)
        .write_timeout(20.0)
        .pool_timeout(10.0)
        .get_updates_connect_timeout(15.0)
        .get_updates_read_timeout(70.0)
        .get_updates_write_timeout(20.0)
        .get_updates_pool_timeout(10.0)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_cmd))
    application.add_handler(CommandHandler("compare", compare_cmd))
    application.add_handler(CommandHandler("examples", examples_cmd))
    application.add_handler(CommandHandler("devices", devices_cmd))
    application.add_handler(CommandHandler("sheets", sheets_cmd))
    application.add_handler(CommandHandler("catalog", catalog_cmd))
    application.add_handler(CommandHandler("notify_on", notify_on_cmd))
    application.add_handler(CommandHandler("notify_off", notify_off_cmd))
    application.add_handler(CommandHandler("whoami", whoami_cmd))
    application.add_handler(CommandHandler("admin", admin_cmd))
    application.add_handler(CallbackQueryHandler(handle_callback))
    application.add_handler(MessageHandler(filters.CONTACT, handle_contact))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    application.add_error_handler(handle_application_error)
    return application


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    setup_logging(
        LoggingConfig(level="DEBUG" if args.verbose else "INFO", file_path=args.log_file),
        verbose=args.verbose,
    )

    try:
        token = read_token(args.token_env)
        ensure_telegram_api_host_resolves()
    except RuntimeError as error:
        logger.error("%s", error)
        return 1

    application = build_application(token)
    logger.info("Telegram compare bot started")
    try:
        application.run_polling()
    except NetworkError as error:
        logger.error("Не удалось подключиться к Telegram API: %s", error)
        logger.error("Проверьте интернет, DNS/VPN/прокси и запустите бота снова.")
        return 1
    except OSError as error:
        logger.error("Бот остановлен из-за сетевой ошибки ОС: %s", error)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
