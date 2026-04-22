"""
Клиент Telethon для рассылки запросов поставщикам и сбора ответов.
"""

from __future__ import annotations

import asyncio
import hashlib
from datetime import datetime, timezone
from typing import Any, Callable, Coroutine

from telethon import TelegramClient, events
from telethon.errors import RPCError
from telethon.tl.types import User
from telethon.utils import get_peer_id

import config


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _message_time_utc(message: Any) -> datetime:
    """Приводит дату сообщения Telethon к UTC aware."""
    d = message.date
    if d.tzinfo is None:
        return d.replace(tzinfo=timezone.utc)
    return d.astimezone(timezone.utc)


class ProcurementClient:
    """
    Обертка над Telethon: отправка, сбор ответов, прослушивание запросов.
    """

    def __init__(
        self,
        logger: Any,
        session_store: Any,
        on_query: Callable[[str], Coroutine[Any, Any, None]],
        on_confirm: Callable[[bool], Coroutine[Any, Any, None]],
    ) -> None:
        self._logger = logger
        self._store = session_store
        self._on_query = on_query
        self._on_confirm = on_confirm
        self._client = TelegramClient(
            config.SESSION_NAME,
            config.API_ID,
            config.API_HASH,
        )
        self._my_peer_id: int | None = None
        self._allowed_peer_ids: set[int] = set()
        self._broadcast_after: datetime | None = None
        self._confirm_future: asyncio.Future[bool] | None = None

    async def start(self) -> None:
        """Авторизация и подключение, кэш идентификаторов."""
        try:
            await self._client.start()
            me = await self._client.get_me()
            my_ent = await self._client.get_entity(config.MY_CHAT_ID)
            self._my_peer_id = get_peer_id(my_ent)
            for src in config.ALLOWED_REPLY_SOURCES:
                try:
                    ent = await self._client.get_entity(src)
                    self._allowed_peer_ids.add(get_peer_id(ent))
                except Exception as e:
                    self._logger.log_error(f"resolve_allowed:{src!r}", e)
        except Exception as e:
            self._logger.log_error("ProcurementClient.start", e)
            raise

    def _is_from_allowed(self, event: events.NewMessage.Event) -> bool:
        if not self._allowed_peer_ids:
            return False
        try:
            sid = event.sender_id
            cid = event.chat_id
            if sid is not None and int(sid) in self._allowed_peer_ids:
                return True
            if cid is not None and int(cid) in self._allowed_peer_ids:
                return True
        except (TypeError, ValueError):
            pass
        return False

    async def send_to_targets(self, message: str, targets: list[Any]) -> list[dict[str, Any]]:
        """
        Отправляет сообщение в каждый чат из списка.

        Учитывает DEDUP_WINDOW_SECONDS и DRY_RUN.
        """
        results: list[dict[str, Any]] = []
        msg_hash = hashlib.sha256(message.encode("utf-8")).hexdigest()

        for tgt in targets:
            chat_name = str(tgt)
            chat_id: int | str = tgt
            try:
                ent = await self._client.get_entity(tgt)
                chat_id = get_peer_id(ent)
                if hasattr(ent, "title") and ent.title:
                    chat_name = ent.title
                elif isinstance(ent, User):
                    fn = ent.first_name or ""
                    ln = ent.last_name or ""
                    chat_name = (fn + " " + ln).strip() or str(chat_id)
            except Exception as e:
                self._logger.log_error(f"send_to_targets.get_entity:{tgt!r}", e)
                results.append(
                    {
                        "chat_id": tgt,
                        "chat_name": str(tgt),
                        "sent": False,
                        "error": str(e),
                    }
                )
                continue

            if self._store.check_dedup(chat_id, msg_hash):
                results.append(
                    {
                        "chat_id": chat_id,
                        "chat_name": chat_name,
                        "sent": False,
                        "error": "dedup: недавно уже отправляли то же сообщение",
                    }
                )
                continue

            if config.DRY_RUN:
                results.append(
                    {
                        "chat_id": chat_id,
                        "chat_name": chat_name,
                        "sent": False,
                        "error": None,
                    }
                )
                continue

            try:
                await self._client.send_message(ent, message)
                results.append(
                    {
                        "chat_id": chat_id,
                        "chat_name": chat_name,
                        "sent": True,
                        "error": None,
                    }
                )
            except RPCError as e:
                self._logger.log_error(f"send_to_targets.send:{chat_id}", e)
                results.append(
                    {
                        "chat_id": chat_id,
                        "chat_name": chat_name,
                        "sent": False,
                        "error": str(e),
                    }
                )
            except Exception as e:
                self._logger.log_error(f"send_to_targets.send:{chat_id}", e)
                results.append(
                    {
                        "chat_id": chat_id,
                        "chat_name": chat_name,
                        "sent": False,
                        "error": str(e),
                    }
                )

        return results

    async def collect_replies(self, session_id: str, wait_seconds: int) -> list[dict[str, Any]]:
        """
        Собирает входящие сообщения от ALLOWED_REPLY_SOURCES после рассылки.
        """
        if self._broadcast_after is None:
            self._broadcast_after = _utc_now()

        cutoff = self._broadcast_after
        collected: list[dict[str, Any]] = []
        lock = asyncio.Lock()

        async def handler(event: events.NewMessage.Event) -> None:
            try:
                if event.message.out:
                    return
                mt = _message_time_utc(event.message)
                if mt < cutoff:
                    return
                if not self._is_from_allowed(event):
                    return
                text = event.message.message or ""
                if not text.strip():
                    return
                ent = await event.get_chat()
                name = getattr(ent, "title", None) or ""
                if isinstance(ent, User):
                    fn = ent.first_name or ""
                    ln = ent.last_name or ""
                    name = (fn + " " + ln).strip() or str(event.chat_id)
                if not name:
                    name = str(event.chat_id)
                row = {
                    "chat_id": event.chat_id,
                    "chat_name": name,
                    "text": text,
                    "received_at": mt.isoformat().replace("+00:00", "Z"),
                }
                async with lock:
                    collected.append(row)
            except Exception as e:
                self._logger.log_error("collect_replies.handler", e)

        self._client.add_event_handler(handler, events.NewMessage(incoming=True))
        try:
            await asyncio.sleep(wait_seconds)
        finally:
            self._client.remove_event_handler(handler)

        return collected

    async def send_result(self, text: str) -> None:
        """Отправляет финальный текст в MY_CHAT_ID."""
        try:
            ent = await self._client.get_entity(config.MY_CHAT_ID)
            await self._client.send_message(ent, text)
        except Exception as e:
            self._logger.log_error("send_result", e)
            raise

    def set_broadcast_start_time(self, t: datetime | None = None) -> None:
        """Фиксирует момент начала рассылки для фильтра ответов."""
        self._broadcast_after = t or _utc_now()

    def set_confirm_result(self, ok: bool) -> None:
        """Передаёт ответ пользователя «Да»/«Нет» в ожидающую корутину."""
        if self._confirm_future is not None and not self._confirm_future.done():
            self._confirm_future.set_result(ok)

    async def wait_for_confirm(self) -> bool:
        """Ожидает подтверждения рассылки (сообщения «Да»/«Нет» в MY_CHAT_ID)."""
        loop = asyncio.get_running_loop()
        self._confirm_future = loop.create_future()
        try:
            return bool(await asyncio.wait_for(self._confirm_future, timeout=3600.0))
        except asyncio.TimeoutError:
            return False
        finally:
            self._confirm_future = None

    async def listen_for_queries(self) -> None:
        """
        Слушает сообщения в MY_CHAT_ID: новые запросы и «Да»/«Нет» для подтверждения.
        """
        if self._my_peer_id is None:
            my_ent = await self._client.get_entity(config.MY_CHAT_ID)
            self._my_peer_id = get_peer_id(my_ent)

        async def handler(event: events.NewMessage.Event) -> None:
            try:
                if int(event.chat_id) != int(self._my_peer_id or 0):
                    return
                # В «Избранном»/чате с собой команды пользователя — исходящие сообщения
                if not event.message.out:
                    return
                text = (event.message.message or "").strip()
                if not text:
                    return
                low = text.lower()
                if low in ("да", "д", "yes", "y") or text == "Да":
                    await self._on_confirm(True)
                    return
                if low in ("нет", "no", "n") or text == "Нет":
                    await self._on_confirm(False)
                    return
                await self._on_query(text)
            except Exception as e:
                self._logger.log_error("listen_for_queries.handler", e)

        self._client.add_event_handler(handler, events.NewMessage(incoming=True))
        await self._client.run_until_disconnected()
