from __future__ import annotations

from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery, TelegramObject

from config import config
from database import db


class AccessMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        if isinstance(event, Message):
            user = event.from_user
            if not user:
                return await handler(event, data)

            if user.id in config.ADMIN_IDS:
                return await handler(event, data)

            text = event.text or ""
            if text.startswith("/start"):
                return await handler(event, data)

            if await db.is_user_approved(user.id):
                return await handler(event, data)

            await event.answer("⛔ Доступ не одобрен. Нажмите /start, чтобы отправить заявку.")
            return None

        if isinstance(event, CallbackQuery):
            user = event.from_user
            if not user:
                return await handler(event, data)

            if user.id in config.ADMIN_IDS or await db.is_user_approved(user.id):
                return await handler(event, data)

            await event.answer("Доступ не одобрен. Нажмите /start.", show_alert=True)
            return None

        return await handler(event, data)

