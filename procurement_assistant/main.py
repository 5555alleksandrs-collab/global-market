"""
Точка входа: Telegram-ассистент закупщика iPhone (Telethon).
"""

from __future__ import annotations

import asyncio
import os
import sys
from typing import Any

import config
from logger import Logger
from matcher import match
from normalizer import normalize
from parser import parse_reply
from session_store import SessionStore
from telegram_client import ProcurementClient


def _format_price(p: float | None, currency: str) -> str:
    if p is None:
        return "—"
    sym = {"USD": "$", "RUB": "₽", "CNY": "¥", "EUR": "€"}.get(currency, "")
    if sym:
        if currency == "USD":
            return f"{p:g}$"
        return f"{p:g} {currency}"
    return f"{p:g} {currency}"


def _build_final(
    normalized: dict[str, Any],
    store: SessionStore,
    session_id: str,
    wait_seconds: int,
    had_any_reply: bool,
) -> str:
    """Формирует итоговый текст по результатам сессии."""
    exact = store.get_exact_matches(session_id)
    close = store.get_close_matches(session_id)
    wait_min = max(1, wait_seconds // 60)

    if not had_any_reply:
        return f"Никто не ответил за {wait_min} минут."

    if not exact and not close:
        return "Нет ответов с подходящим товаром."

    line = normalized.get("raw") or ""

    if len(exact) == 1:
        r = exact[0]
        price = r.get("parsed_price")
        cur = str(r.get("parsed_currency") or "USD")
        return (
            f"{line}\n"
            f"Цена: {_format_price(float(price) if price is not None else None, cur)}\n"
            f"Поставщик: {r.get('chat_name')}"
        )

    if len(exact) > 1:
        lines_sorted = sorted(
            [x for x in exact if x.get("parsed_price") is not None],
            key=lambda x: float(x["parsed_price"]),
        )
        if not lines_sorted:
            return "Нет ответов с подходящим товаром."
        parts = ["Варианты (точные совпадения):"]
        for i, r in enumerate(lines_sorted, start=1):
            p = r.get("parsed_price")
            cur = str(r.get("parsed_currency") or "USD")
            parts.append(
                f"{i}) {_format_price(float(p) if p is not None else None, cur)} — {r.get('chat_name')}"
            )
        best = lines_sorted[0]
        bp = best.get("parsed_price")
        bcur = str(best.get("parsed_currency") or "USD")
        parts.append(
            f"\nЛучшая цена: {_format_price(float(bp) if bp is not None else None, bcur)} ({best.get('chat_name')})"
        )
        return "\n".join(parts)

    # Нет точных, есть близкие
    if close:
        parts = ["Точного совпадения нет.", "", "Близкие варианты:"]
        for i, r in enumerate(close, start=1):
            p = r.get("parsed_price")
            cur = str(r.get("parsed_currency") or "USD")
            mn = (r.get("match_notes") or "").strip()
            note = f" ({mn})" if mn else ""
            parts.append(
                f"{i}) {_format_price(float(p) if p is not None else None, cur)} — {r.get('chat_name')}{note}"
            )
        return "\n".join(parts)

    return "Нет ответов с подходящим товаром."


async def _run_session(
    client: ProcurementClient,
    logger: Logger,
    store: SessionStore,
    original_query: str,
) -> None:
    """Полный цикл: нормализация, подтверждение, рассылка, сбор, отчёт."""
    normalized = normalize(original_query)
    session_id = store.new_session(original_query, normalized)
    logger.log_session_start(session_id, original_query, normalized)

    try:
        msg = config.MESSAGE_TEMPLATE.format(query=normalized.get("raw") or original_query)
    except Exception as e:
        logger.log_error("MESSAGE_TEMPLATE", e)
        await client.send_result("Ошибка шаблона сообщения.")
        return

    if config.HUMAN_IN_THE_LOOP and not config.FAST_MODE:
        preview = (
            "Подтвердите рассылку.\n"
            f"Сообщение: {msg}\n"
            f"Адресаты: {config.TARGET_CHATS}\n\n"
            'Ответьте «Да» или «Нет».'
        )
        try:
            await client.send_result(preview)
        except Exception as e:
            logger.log_error("send_result preview", e)
            return

        ok = await client.wait_for_confirm()
        if not ok:
            await client.send_result("Отменено")
            return

    if config.DRY_RUN:
        for tgt in config.TARGET_CHATS:
            logger.log_sent(session_id, tgt, str(tgt), msg, dry_run=True)
        await client.send_result("DRY_RUN: сообщения не отправлялись.")
        store.save(session_id)
        return

    client.set_broadcast_start_time()
    try:
        send_results = await client.send_to_targets(msg, list(config.TARGET_CHATS))
    except Exception as e:
        logger.log_error("send_to_targets", e)
        await client.send_result("Ошибка при отправке сообщений.")
        return

    for row in send_results:
        if row.get("sent"):
            store.add_sent(session_id, row["chat_id"], row["chat_name"])
        logger.log_sent(
            session_id,
            row["chat_id"],
            row["chat_name"],
            msg,
            dry_run=False,
        )

    replies = await client.collect_replies(session_id, config.REPLY_WAIT_SECONDS)
    had_any = len(replies) > 0

    ctx = normalized
    for rep in replies:
        text = rep.get("text") or ""
        parsed = parse_reply(text, ctx)
        if parsed is None:
            continue
        m = match(parsed, ctx)
        store.add_reply(
            session_id,
            rep["chat_id"],
            rep["chat_name"],
            text,
            parsed,
            m,
        )
        logger.log_reply(session_id, rep["chat_id"], rep["chat_name"], text, parsed, m)

    final_text = _build_final(normalized, store, session_id, config.REPLY_WAIT_SECONDS, had_any)
    best = store.get_best_price(session_id)
    if best:
        store.set_final_selected(
            session_id,
            {
                "price": best.get("parsed_price"),
                "chat_name": best.get("chat_name"),
                "raw_reply": best.get("raw_reply"),
            },
        )
    else:
        store.set_final_selected(session_id, None)

    try:
        await client.send_result(final_text)
    except Exception as e:
        logger.log_error("send_result final", e)

    logger.log_result(session_id, final_text)
    store.save(session_id)


async def main_async() -> None:
    """Полный асинхронный цикл приложения."""
    if not config.API_ID or not config.API_HASH:
        print("Заполните API_ID и API_HASH в config.py (my.telegram.org).", file=sys.stderr)
        sys.exit(1)

    if not config.MY_CHAT_ID:
        print("Укажите MY_CHAT_ID в config.py.", file=sys.stderr)
        sys.exit(1)

    logger = Logger()
    store = SessionStore(
        path="logs/sessions.json",
        dedup_window_seconds=config.DEDUP_WINDOW_SECONDS,
    )
    client_holder: dict[str, ProcurementClient | None] = {"c": None}

    async def on_confirm(ok: bool) -> None:
        c = client_holder["c"]
        if c is not None:
            c.set_confirm_result(ok)

    async def on_query(text: str) -> None:
        c = client_holder["c"]
        if c is None:
            return
        try:
            await _run_session(c, logger, store, text.strip())
        except Exception as e:
            logger.log_error("on_query", e)
            try:
                await c.send_result("Произошла ошибка при обработке запроса.")
            except Exception as e2:
                logger.log_error("on_query.send_result", e2)

    client = ProcurementClient(logger, store, on_query, on_confirm)
    client_holder["c"] = client

    await client.start()
    print("Ассистент запущен. Отправьте запрос в чат MY_CHAT_ID (например, «Избранное»).", flush=True)
    await client.listen_for_queries()


def main() -> None:
    """Синхронная обёртка для asyncio."""
    try:
        asyncio.run(main_async())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    # Позволяет переопределять bool через окружение
    if os.environ.get("DRY_RUN", "").lower() in ("1", "true", "yes"):
        config.DRY_RUN = True
    if os.environ.get("FAST_MODE", "").lower() in ("1", "true", "yes"):
        config.FAST_MODE = True
    main()
