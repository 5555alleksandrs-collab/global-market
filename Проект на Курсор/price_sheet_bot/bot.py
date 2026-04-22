"""
Telegram-бот: пересланные прайсы поставщиков → парсинг → min/2-я цена в F/G с цветом;
или ручной формат «товар + строки Поставщик цена».
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
from html import escape
from pathlib import Path

from googleapiclient.errors import HttpError
from telegram import BotCommand, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler, filters

import config
from chat_intent import is_smalltalk_message
from message_split import model_line_required_error_hint, split_model_and_price_text
from parse_supplier_prices import parse_supplier_price_lines, two_lowest_with_suppliers
from parse_telegram_pricelist import looks_like_telegram_pricelist, parse_telegram_pricelist
from price_store import load_store, merge_supplier_prices, min_and_second, save_store
from sheets_writer import batch_write_fg_for_products, write_row_prices_with_supplier_colors
from supplier_label import looks_like_supplier_label
from telegram_supplier import supplier_name_from_message

PENDING_SUPPLIER_KEY = "pending_supplier_name"
# callback_data: sup:0 … sup:N (лимит Telegram 64 байта)
CALLBACK_SUPPLIER_PREFIX = "sup:"


def _supplier_names() -> list[str]:
    """Имена для кнопок: SUPPLIER_BUTTONS из .env или все ключи supplier_colors.json."""
    path = Path(config.SUPPLIER_COLORS_PATH)
    keys_from_file: list[str] = []
    if path.is_file():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                keys_from_file = [str(k) for k in data.keys()]
        except (OSError, json.JSONDecodeError):
            pass

    if config.SUPPLIER_BUTTONS:
        out: list[str] = []
        key_set = set(keys_from_file)
        for name in config.SUPPLIER_BUTTONS:
            if name in key_set:
                out.append(name)
            else:
                logger.warning("SUPPLIER_BUTTONS: «%s» нет в supplier_colors.json — кнопка пропущена.", name)
        return out

    return keys_from_file


def supplier_keyboard() -> InlineKeyboardMarkup | None:
    """Кнопки поставщиков (по 3 в ряд)."""
    names = _supplier_names()
    if not names:
        return None
    rows: list[list[InlineKeyboardButton]] = []
    row: list[InlineKeyboardButton] = []
    for i, name in enumerate(names):
        label = name if len(name) <= 40 else name[:37] + "…"
        row.append(
            InlineKeyboardButton(
                label,
                callback_data=f"{CALLBACK_SUPPLIER_PREFIX}{i}",
            )
        )
        if len(row) >= 3:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    return InlineKeyboardMarkup(rows)


logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


def _smalltalk_reply_html() -> str:
    """Короткий ответ на «привет» и т.п. — не путать с прайсом."""
    lines = [
        "<b>Привет.</b> Я бот для прайсов поставщиков: пересланный текст прайса → разбор → запись минимума и второй цены в Google Таблицу (колонки F/G).",
        "",
        "<b>Как пользоваться</b>",
        "1) Нажмите кнопку поставщика или напишите <b>одной строкой</b> код (<code>AL</code>, <code>BB</code>…), затем",
        "2) <b>следующим сообщением</b> вставьте текст прайса (или перешлите сообщение из чата поставщика).",
        "",
        "Команды: <code>/start</code> — полная инструкция · <code>/help</code> — справка · <code>/suppliers</code> — кнопки · <code>/cancel</code> — сброс выбранного поставщика",
    ]
    if config.HELP_URL:
        u = escape(config.HELP_URL, quote=True)
        lines.append(f'<a href="{u}">Документация / GitHub</a>')
    return "\n".join(lines)


def _build_full_help_html(uid: int | None = None) -> str:
    """Текст как в /start: вся инструкция + опционально user_id и ссылка."""
    lines = [
        "<b>Поставщик:</b> нажмите кнопку ниже или введите код текстом (<code>AL</code>), "
        "затем <b>следующим</b> сообщением пришлите прайс.",
        "",
        "<b>Пересланный прайс:</b> имя берётся из отправителя пересланного сообщения.",
        "",
        "Таблица: колонка A — товар; F/G — минимум и вторая цена; цвета — в "
        "<code>supplier_colors.json</code>.",
        "",
        "<b>Ручной режим:</b> первая строка как в A, далее <code>Имя цена</code> по строкам.",
        "<b>eSIM / SIM:</b> в каждой строке прайса учитываются флаги и коды (Kr, HK, Uk, US, Aus, …); "
        "шапка из 🇯🇵/🇬🇧 — если в строке нет страны. iPhone 17 Air — всегда eSIM. "
        "Суффиксы в таблице: <code>REGION_SUFFIX_JP</code> / <code>REGION_SUFFIX_GB</code>.",
        "<b>В группе:</b> упомяните бота в начале сообщения или в @BotFather отключите приватность для бота (/setprivacy).",
        "<b>Фото:</b> прайс должен быть в подписи к картинке или отдельным текстом.",
    ]
    if config.HELP_URL:
        u = escape(config.HELP_URL, quote=True)
        lines.append(f'<a href="{u}">Документация / репозиторий</a>')
    lines.append("")
    lines.append("Сброс метки: /cancel · список кнопок: /suppliers")
    if uid is not None:
        lines.append("")
        lines.append(f"user_id: <code>{uid}</code>")
    return "\n".join(lines)


def _format_exception_for_user(exc: BaseException) -> str:
    """Текст для пользователя: тип, для Google API — HTTP-код и message из JSON."""
    if isinstance(exc, HttpError):
        extra = ""
        try:
            if exc.content:
                body = json.loads(exc.content.decode("utf-8", errors="replace"))
                msg = (body.get("error") or {}).get("message")
                if msg:
                    extra = f" {msg}"
        except (json.JSONDecodeError, UnicodeError, TypeError, AttributeError):
            pass
        return f"Google Sheets HTTP {exc.resp.status}{extra}"
    return f"{type(exc).__name__}: {exc}"


def _allowed(user_id: int | None) -> bool:
    if user_id is None:
        return False
    if not config.ALLOWED_USER_IDS:
        return True
    return user_id in config.ALLOWED_USER_IDS


async def on_supplier_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Нажатие на кнопку поставщика — ставим метку, как при тексте AL."""
    q = update.callback_query
    if not q or not q.data:
        return
    if not q.data.startswith(CALLBACK_SUPPLIER_PREFIX):
        return
    uid = q.from_user.id if q.from_user else None
    if not _allowed(uid):
        await q.answer("Доступ запрещён", show_alert=True)
        return
    try:
        idx = int(q.data[len(CALLBACK_SUPPLIER_PREFIX) :])
    except ValueError:
        await q.answer()
        return
    names = _supplier_names()
    if idx < 0 or idx >= len(names):
        await q.answer("Неверный выбор", show_alert=True)
        return
    name = names[idx]
    context.user_data[PENDING_SUPPLIER_KEY] = name
    await q.answer()
    if not q.message:
        return
    kb = supplier_keyboard()
    await q.message.reply_text(
        f"Поставщик: <b>{escape(name)}</b>\nПришлите прайс <b>следующим</b> сообщением.",
        parse_mode="HTML",
        reply_markup=kb,
    )


def _message_plain_text(message) -> str | None:
    """Текст сообщения или подпись к фото/видео (caption). Без этого бот «не видит» прайс на картинке."""
    if not message:
        return None
    raw = message.text or message.caption
    if not raw:
        return None
    s = raw.strip()
    return s if s else None


async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    uid = update.effective_user.id if update.effective_user else None
    if not _allowed(uid):
        await update.message.reply_text("Доступ запрещён.")
        return

    text = _message_plain_text(update.message)
    if not text:
        if update.message.photo:
            await update.message.reply_text(
                "Прайс не в тексте сообщения. Добавьте подпись под фото (caption) "
                "или отправьте прайс отдельным текстовым сообщением."
            )
        elif update.message.document:
            await update.message.reply_text(
                "Файлы бот не разбирает. Откройте прайс и вставьте текст в чат, "
                "или отправьте скриншот с подписью."
            )
        return
    if text.startswith("/"):
        return

    if is_smalltalk_message(text):
        await update.message.reply_text(
            _smalltalk_reply_html(),
            parse_mode="HTML",
            reply_markup=supplier_keyboard(),
        )
        return

    telegram_pairs = await asyncio.to_thread(parse_telegram_pricelist, text)

    # Короткое сообщение «AL» — код поставщика для следующего прайса
    if not telegram_pairs and looks_like_supplier_label(text):
        context.user_data[PENDING_SUPPLIER_KEY] = text.strip()
        await update.message.reply_text(
            f"Поставщик для <b>следующего</b> сообщения с прайсом: <code>{escape(text.strip())}</code>\n"
            "Пришлите прайс <b>следующим</b> сообщением.",
            parse_mode="HTML",
        )
        return

    supplier = supplier_name_from_message(update.message)
    pending = context.user_data.get(PENDING_SUPPLIER_KEY)
    if pending and telegram_pairs:
        supplier = pending.strip()
        context.user_data.pop(PENDING_SUPPLIER_KEY, None)

    if len(telegram_pairs) > 0:
        await _handle_telegram_pricelist(update, supplier, telegram_pairs)
        return

    if looks_like_telegram_pricelist(text):
        await update.message.reply_text(
            "Похоже на прайс из Telegram, но не удалось извлечь цены. "
            "Проверьте формат (секции с GB/TB, строки с ценами и \$).\n\n"
            "Если пишете в группе — начните сообщение с @имя_бота или отключите "
            "режим приватности у бота в @BotFather (команда /setprivacy)."
        )
        return

    await _handle_manual_lines(update)


async def _handle_telegram_pricelist(
    update: Update,
    supplier: str,
    telegram_pairs: list[tuple[str, float]],
) -> None:
    reply_lines = [
        f"Поставщик: {supplier}",
        f"Разобрано позиций: {len(telegram_pairs)}",
    ]

    if not config.SPREADSHEET_ID or not os.path.isfile(config.GOOGLE_CREDENTIALS_PATH):
        reply_lines.append("")
        reply_lines.append("Google Sheets не настроен (SPREADSHEET_ID, credentials.json).")
        await update.message.reply_text("\n".join(reply_lines))
        return

    store = load_store(config.OFFERS_STORE_PATH)
    raw_touched = merge_supplier_prices(store, supplier, telegram_pairs)
    touched = list(dict.fromkeys(raw_touched))
    save_store(config.OFFERS_STORE_PATH, store)

    items: list[tuple[str, str, float, str | None, float | None]] = []
    for pk in touched:
        first, second = min_and_second(store.get(pk, {}))
        if first is None:
            continue
        s1, p1 = first
        if second is not None:
            s2, p2 = second
            items.append((pk, s1, float(p1), s2, float(p2)))
        else:
            items.append((pk, s1, float(p1), None, None))

    if not items:
        reply_lines.append("Не удалось посчитать цены для записи.")
        await update.message.reply_text("\n".join(reply_lines))
        return

    try:
        ok, err, sheet_title = await asyncio.to_thread(
            batch_write_fg_for_products,
            config.GOOGLE_CREDENTIALS_PATH,
            config.SPREADSHEET_ID,
            config.WORKSHEET_NAME,
            data_start_row=config.DATA_START_ROW,
            first_price_column_index=config.FIRST_PRICE_COLUMN,
            second_price_column_index=config.SECOND_PRICE_COLUMN,
            max_scan_rows=config.MAX_SCAN_ROWS,
            supplier_colors_path=config.SUPPLIER_COLORS_PATH,
            items=items,
        )
        reply_lines.append("")
        if sheet_title.strip() != config.WORKSHEET_NAME.strip():
            reply_lines.append(
                f"Лист таблицы: «{sheet_title}» (в .env было «{config.WORKSHEET_NAME}» — такого имени не было; проверьте WORKSHEET_NAME)."
            )
        reply_lines.append("Запись в таблицу:")
        reply_lines.extend(ok[:30])
        if len(ok) > 30:
            reply_lines.append(f"… и ещё {len(ok) - 30} строк.")
        if err:
            reply_lines.append("")
            reply_lines.append("Не найдены в колонке A:")
            reply_lines.extend(err[:15])
    except Exception as e:
        logger.exception("batch sheets")
        reply_lines.append("")
        reply_lines.append(f"Ошибка: {_format_exception_for_user(e)}")

    body = "\n".join(reply_lines)
    if len(body) > 4000:
        body = body[:3900] + "\n… (ответ обрезан лимитом Telegram 4096 символов.)"
    await update.message.reply_text(body)


async def _handle_manual_lines(update: Update) -> None:
    text = (_message_plain_text(update.message) or "").strip()
    model, price_block = split_model_and_price_text(text)
    if not model or not model.strip():
        await update.message.reply_text(
            "Не удалось разобрать прайс.\n\n"
            "<b>Вариант 1.</b> Перешлите сообщение поставщика с прайсом (как в чате «Пробив NEW»).\n\n"
            "<b>Вариант 2.</b> Вручную:\n"
            + model_line_required_error_hint(),
            parse_mode="HTML",
        )
        return

    pairs = parse_supplier_price_lines(price_block, config.PRICE_MIN, config.PRICE_MAX)
    if not pairs:
        await update.message.reply_text(
            "Не удалось разобрать строки «поставщик + цена».\n\n"
            "Со второй строки, например:\n"
            "<code>Cell tech 638</code>\n<code>Otm 640</code>\n\n"
            "Или перешлите готовый прайс от поставщика.",
            parse_mode="HTML",
        )
        return

    first, second = two_lowest_with_suppliers(pairs)
    if first is None:
        await update.message.reply_text("Нет цен для сравнения.")
        return

    s1_name, p1 = first
    if second is not None:
        s2_name, p2_val = second
    else:
        s2_name, p2_val = None, None

    reply_lines = [
        f"Товар: «{model.strip()}»",
        f"• Минимум: {p1:g} — {s1_name}",
    ]
    if p2_val is not None and s2_name:
        reply_lines.append(f"• Вторая цена: {p2_val:g} — {s2_name}")
    else:
        reply_lines.append("• Вторая цена: только одно предложение.")

    if not config.SPREADSHEET_ID or not os.path.isfile(config.GOOGLE_CREDENTIALS_PATH):
        reply_lines.append("")
        reply_lines.append("Google Sheets не настроен.")
        await update.message.reply_text("\n".join(reply_lines))
        return

    try:
        _row, matched, cells_note, sheet_title = await asyncio.to_thread(
            write_row_prices_with_supplier_colors,
            config.GOOGLE_CREDENTIALS_PATH,
            config.SPREADSHEET_ID,
            config.WORKSHEET_NAME,
            data_start_row=config.DATA_START_ROW,
            first_price_column_index=config.FIRST_PRICE_COLUMN,
            second_price_column_index=config.SECOND_PRICE_COLUMN,
            max_scan_rows=config.MAX_SCAN_ROWS,
            supplier_colors_path=config.SUPPLIER_COLORS_PATH,
            product_name=model.strip(),
            first_supplier=s1_name,
            first_price=p1,
            second_supplier=s2_name,
            second_price=p2_val,
        )
        reply_lines.append("")
        if sheet_title.strip() != config.WORKSHEET_NAME.strip():
            reply_lines.append(
                f"Лист таблицы: «{sheet_title}» (имя из .env «{config.WORKSHEET_NAME}» не найдено — см. WORKSHEET_NAME)."
            )
        reply_lines.append(f"Строка: «{matched}» (№{_row}).")
        reply_lines.append(cells_note)
    except ValueError as e:
        reply_lines.append("")
        reply_lines.append(str(e))
    except Exception as e:
        logger.exception("sheets")
        reply_lines.append("")
        reply_lines.append(f"Ошибка таблицы: {_format_exception_for_user(e)}")

    await update.message.reply_text("\n".join(reply_lines))


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    uid = update.effective_user.id if update.effective_user else None
    if not _allowed(uid):
        await update.message.reply_text("Доступ запрещён.")
        return
    kb = supplier_keyboard()
    await update.message.reply_text(
        _build_full_help_html(uid),
        parse_mode="HTML",
        reply_markup=kb,
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    uid = update.effective_user.id if update.effective_user else None
    if not _allowed(uid):
        await update.message.reply_text("Доступ запрещён.")
        return
    kb = supplier_keyboard()
    await update.message.reply_text(
        "<b>Справка</b>\n\n" + _build_full_help_html(None),
        parse_mode="HTML",
        reply_markup=kb,
    )


async def cmd_suppliers(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    uid = update.effective_user.id if update.effective_user else None
    if not _allowed(uid):
        await update.message.reply_text("Доступ запрещён.")
        return
    kb = supplier_keyboard()
    await update.message.reply_text(
        "Выберите поставщика, затем отправьте прайс следующим сообщением.",
        reply_markup=kb,
    )


async def cmd_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message:
        context.user_data.pop(PENDING_SUPPLIER_KEY, None)
        await update.message.reply_text("Метка поставщика сброшена.")


async def _post_init(application: Application) -> None:
    """Показывает в терминале, что бот реально подключился к Telegram."""
    me = await application.bot.get_me()
    logger.info(
        "Подключено к Telegram: @%s — пишите боту в ЛИЧКУ или в группе с @%s в начале сообщения.",
        me.username,
        me.username,
    )
    try:
        await application.bot.set_my_commands(
            [
                BotCommand("start", "Инструкция и кнопки"),
                BotCommand("help", "Полная справка"),
                BotCommand("suppliers", "Выбор поставщика"),
                BotCommand("cancel", "Сброс метки поставщика"),
            ]
        )
    except Exception as e:
        logger.warning("Не удалось установить меню команд: %s", e)


def main() -> None:
    if not config.TELEGRAM_BOT_TOKEN:
        logger.error("Задайте TELEGRAM_BOT_TOKEN в .env или переменной окружения.")
        sys.exit(1)

    app = (
        Application.builder()
        .token(config.TELEGRAM_BOT_TOKEN)
        .post_init(_post_init)
        .build()
    )
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("suppliers", cmd_suppliers))
    app.add_handler(CommandHandler("cancel", cmd_cancel))
    app.add_handler(CallbackQueryHandler(on_supplier_callback, pattern=r"^sup:\d+$"))
    # TEXT + caption под фото/видео; иначе прайс «на картинке» без подписи бот не получает
    app.add_handler(
        MessageHandler(
            (filters.TEXT | filters.PHOTO | filters.VIDEO | filters.Document.ALL)
            & ~filters.COMMAND,
            on_text,
        )
    )

    logger.info("Запуск long polling (оставьте это окно открытым)…")
    app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)


if __name__ == "__main__":
    main()
