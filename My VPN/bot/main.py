"""Telegram-бот: выдача WireGuard peer-конфигов (linuxserver/wireguard volume /config)."""

from __future__ import annotations

import io
import logging
import os
import sqlite3
from pathlib import Path

import qrcode
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
    level=logging.INFO,
)
log = logging.getLogger("vpn-bot")

WIREGUARD_DIR = Path(os.environ.get("WIREGUARD_CONFIG_DIR", "/config")).resolve()
DB_PATH = Path(os.environ.get("BOT_DB_PATH", "/data/bot.sqlite3"))


def _admin_ids() -> set[int]:
    raw = os.environ.get("ADMIN_TELEGRAM_IDS", "")
    return {int(x.strip()) for x in raw.split(",") if x.strip().isdigit()}


def _ensure_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS user_peer (
                telegram_id INTEGER PRIMARY KEY,
                peer_num INTEGER NOT NULL UNIQUE
            )
            """
        )
        conn.commit()


def _peer_conf_path(peer_num: int) -> Path | None:
    """Пути linuxserver/wireguard: /config/peerN/peerN.conf"""
    for base in (
        WIREGUARD_DIR / f"peer{peer_num}" / f"peer{peer_num}.conf",
        WIREGUARD_DIR / f"peer_{peer_num}" / f"peer_{peer_num}.conf",
    ):
        if base.is_file():
            return base
    return None


def _read_peer_conf(peer_num: int) -> str | None:
    path = _peer_conf_path(peer_num)
    if not path:
        return None
    return path.read_text(encoding="utf-8")


def _get_peer_for_user(telegram_id: int) -> int | None:
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute(
            "SELECT peer_num FROM user_peer WHERE telegram_id = ?",
            (telegram_id,),
        ).fetchone()
    return int(row[0]) if row else None


def _set_mapping(telegram_id: int, peer_num: int) -> None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("DELETE FROM user_peer WHERE peer_num = ?", (peer_num,))
        conn.execute(
            """
            INSERT INTO user_peer (telegram_id, peer_num) VALUES (?, ?)
            ON CONFLICT(telegram_id) DO UPDATE SET peer_num = excluded.peer_num
            """,
            (telegram_id, peer_num),
        )
        conn.commit()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user:
        return
    await update.message.reply_text(
        "Команды:\n"
        "/vpn — получить конфиг WireGuard (файл и QR)\n"
        "/help — справка\n\n"
        "Доступ выдаёт администратор командой /assign."
    )


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    admins = _admin_ids()
    lines = [
        "Бот работает вместе с контейнером linuxserver/wireguard.",
        "Пиры создаются при старте VPN (PEERS в docker-compose).",
        "",
        "Пользователь: /vpn — скачать .conf и QR.",
        "",
        "Админ: /assign <telegram_id> <peer_num> — привязать пользователя к номеру пира (1…N).",
        "Пример: /assign 987654321 2",
    ]
    if not admins:
        lines.append("\n⚠️ ADMIN_TELEGRAM_IDS не задан — /assign недоступен.")
    await update.message.reply_text("\n".join(lines))


async def assign(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user or not update.message:
        return
    if update.effective_user.id not in _admin_ids():
        await update.message.reply_text("Недостаточно прав.")
        return
    args = context.args or []
    if len(args) != 2 or not args[0].isdigit() or not args[1].isdigit():
        await update.message.reply_text("Использование: /assign <telegram_id> <peer_num>")
        return
    tid, peer_num = int(args[0]), int(args[1])
    if peer_num < 1:
        await update.message.reply_text("peer_num должен быть ≥ 1.")
        return
    text = _read_peer_conf(peer_num)
    if not text:
        await update.message.reply_text(
            f"Файл пира {peer_num} не найден в {WIREGUARD_DIR}. "
            "Проверьте, что WireGuard уже создал peer-каталоги (первый запуск контейнера)."
        )
        return
    _set_mapping(tid, peer_num)
    await update.message.reply_text(f"Пользователь {tid} → peer {peer_num}.")


async def vpn(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user or not update.message:
        return
    uid = update.effective_user.id
    peer_num = _get_peer_for_user(uid)
    if peer_num is None:
        await update.message.reply_text(
            "Вам ещё не назначен VPN. Напишите администратору или дождитесь команды /assign."
        )
        return
    text = _read_peer_conf(peer_num)
    if not text:
        await update.message.reply_text(
            "Конфиг на сервере не найден. Обратитесь к администратору (проблема с томом WireGuard)."
        )
        return
    fname = f"wireguard-peer{peer_num}.conf"
    await update.message.reply_document(
        document=io.BytesIO(text.encode("utf-8")),
        filename=fname,
    )
    qr = qrcode.make(text)
    buf = io.BytesIO()
    qr.save(buf, format="PNG")
    buf.seek(0)
    await update.message.reply_photo(photo=buf, caption=f"QR для импорта (peer {peer_num})")


def main() -> None:
    token = os.environ.get("BOT_TOKEN", "").strip()
    if not token:
        raise SystemExit("BOT_TOKEN не задан")

    _ensure_db()
    admins = _admin_ids()
    log.info("WireGuard config dir: %s", WIREGUARD_DIR)
    log.info("Admins: %s", admins or "none")

    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("vpn", vpn))
    app.add_handler(CommandHandler("assign", assign))

    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
