"""
Имя поставщика из сообщения Telegram (пересланное или от себя).
"""

from __future__ import annotations

from telegram import Message, User


def user_display_name(user: User | None) -> str:
    if user is None:
        return "unknown"
    parts = [user.first_name or "", user.last_name or ""]
    name = " ".join(p for p in parts if p).strip()
    if name:
        return name
    if user.username:
        return f"@{user.username}"
    return str(user.id)


def supplier_name_from_message(message: Message) -> str:
    """
    Поставщик: автор пересланного сообщения; иначе отправитель текущего чата.
    """
    fo = getattr(message, "forward_origin", None)
    if fo is not None:
        su = getattr(fo, "sender_user", None)
        if su is not None:
            return user_display_name(su)
        ch = getattr(fo, "sender_chat", None)
        if ch is not None:
            return getattr(ch, "title", None) or getattr(ch, "username", None) or str(ch.id)
        name = getattr(fo, "sender_user_name", None)
        if name:
            return str(name)

    if getattr(message, "forward_from", None):
        return user_display_name(message.forward_from)

    if getattr(message, "forward_sender_name", None):
        return str(message.forward_sender_name)

    if message.from_user:
        return user_display_name(message.from_user)

    return "unknown"
