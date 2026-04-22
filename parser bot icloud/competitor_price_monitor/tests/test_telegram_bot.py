import unittest
from pathlib import Path
from threading import Event
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from telegram.error import BadRequest, NetworkError

from competitor_price_monitor.access_control import build_access_config
from competitor_price_monitor.access_requests import AccessRequest
from competitor_price_monitor.telegram_bot import (
    build_admin_list_text,
    build_admin_panel_text,
    build_admin_requests_text,
    build_asyncio_exception_handler,
    classify_transient_telegram_network_error,
    ensure_telegram_api_host_resolves,
    handle_application_error,
    is_expired_callback_error,
    RefreshState,
    safe_answer_callback_query,
    set_refresh_state,
    should_suppress_asyncio_exception,
    report_export_progress,
    request_refresh_cancel,
    update_active_refresh_message,
)


class TelegramBotTests(unittest.IsolatedAsyncioTestCase):
    def test_request_refresh_cancel_sets_cancel_event(self):
        application = SimpleNamespace(bot_data={})
        state = RefreshState(
            owner_chat_id=123,
            kind="sheets",
            cancel_event=Event(),
        )
        set_refresh_state(application, state)

        response = request_refresh_cancel(application, 123)

        self.assertTrue(state.cancel_event.is_set())
        self.assertIn("Останавливаю выгрузку", response)

    async def test_update_active_refresh_message_edits_tracked_status_message(self):
        application = SimpleNamespace(
            bot_data={},
            bot=SimpleNamespace(edit_message_text=AsyncMock()),
        )
        set_refresh_state(
            application,
            RefreshState(
                owner_chat_id=123,
                kind="sheets",
                cancel_event=Event(),
                status_chat_id=777,
                status_message_id=42,
            ),
        )

        await update_active_refresh_message(application, "test-status")

        application.bot.edit_message_text.assert_awaited_once_with(
            chat_id=777,
            message_id=42,
            text="test-status",
            reply_markup=None,
        )

    async def test_update_active_refresh_message_skips_same_message(self):
        application = SimpleNamespace(
            bot_data={},
            bot=SimpleNamespace(edit_message_text=AsyncMock()),
        )
        set_refresh_state(
            application,
            RefreshState(
                owner_chat_id=123,
                kind="csv",
                cancel_event=Event(),
                status_chat_id=777,
                status_message_id=42,
            ),
        )
        current_message = SimpleNamespace(chat_id=777, message_id=42)

        await update_active_refresh_message(
            application,
            "same-message-status",
            skip_message=current_message,
        )

        application.bot.edit_message_text.assert_not_called()

    async def test_report_export_progress_switches_to_cancelling_state(self):
        cancel_event = Event()
        cancel_event.set()
        export_task = SimpleNamespace(done=lambda: False)
        message = SimpleNamespace()

        async def immediate_sleep(_seconds):
            return None

        with patch("competitor_price_monitor.telegram_bot.asyncio.sleep", side_effect=immediate_sleep), patch(
            "competitor_price_monitor.telegram_bot.update_status_message",
            new=AsyncMock(),
        ) as update_status_message_mock:
            await report_export_progress(
                message,
                Path("/tmp/non-existent-export.csv"),
                100,
                export_task,
                cancel_event,
            )

        update_status_message_mock.assert_awaited_once()
        status_text = update_status_message_mock.await_args.args[1]
        self.assertIn("Остановка запрошена", status_text)

    def test_build_admin_panel_text_renders_compact_summary(self):
        with (
            patch("competitor_price_monitor.telegram_bot.read_access_config", return_value=build_access_config([1, 2], [-1001])),
            patch("competitor_price_monitor.telegram_bot.read_env_access_config", return_value=build_access_config([1], [])),
            patch("competitor_price_monitor.telegram_bot.read_stored_access_config", return_value=build_access_config([2], [-1001])),
            patch("competitor_price_monitor.telegram_bot.read_explicit_admin_config", return_value=build_access_config()),
            patch("competitor_price_monitor.telegram_bot.load_pending_access_requests", return_value=[object(), object()]),
        ):
            text = build_admin_panel_text()

        self.assertIn("🛂 Доступ и права", text)
        self.assertIn("Всего разрешено: 2 user_id, 1 chat_id", text)
        self.assertIn("Заявок ждут решения: 2", text)
        self.assertNotIn("allowed_user_ids", text)

    def test_build_admin_list_text_hides_raw_dump(self):
        with (
            patch("competitor_price_monitor.telegram_bot.read_access_config", return_value=build_access_config([1, 2, 3], [-1001])),
            patch("competitor_price_monitor.telegram_bot.read_env_access_config", return_value=build_access_config([1], [])),
            patch("competitor_price_monitor.telegram_bot.read_stored_access_config", return_value=build_access_config([2, 3], [-1001])),
        ):
            text = build_admin_list_text()

        self.assertIn("👥 Доступы", text)
        self.assertIn("Сейчас разрешено:", text)
        self.assertIn("Выдано через панель:", text)
        self.assertNotIn("Текущий доступ:", text)

    def test_build_admin_requests_text_renders_pretty_list(self):
        request = AccessRequest(
            request_id="req-1",
            user_id=123,
            chat_id=456,
            username="demo_user",
            full_name="Иван Петров",
            phone_number="+79990000000",
            requested_at="01.04 10:45",
        )
        with patch("competitor_price_monitor.telegram_bot.load_pending_access_requests", return_value=[request]):
            text = build_admin_requests_text()

        self.assertIn("📝 Заявки", text)
        self.assertIn("Иван Петров", text)
        self.assertIn("user_id 123 · chat_id 456 · @demo_user", text)

    def test_is_expired_callback_error_matches_expected_messages(self):
        self.assertTrue(is_expired_callback_error(BadRequest("Query is too old and response timeout expired or query id is invalid")))
        self.assertTrue(is_expired_callback_error(BadRequest("query id is invalid")))
        self.assertFalse(is_expired_callback_error(BadRequest("Message is not modified")))

    async def test_safe_answer_callback_query_ignores_expired_query(self):
        query = SimpleNamespace(
            data="menu:main",
            answer=AsyncMock(side_effect=BadRequest("Query is too old and response timeout expired or query id is invalid")),
        )

        result = await safe_answer_callback_query(query)

        self.assertFalse(result)
        query.answer.assert_awaited_once()

    async def test_safe_answer_callback_query_re_raises_other_bad_request(self):
        query = SimpleNamespace(
            data="menu:main",
            answer=AsyncMock(side_effect=BadRequest("Message is not modified")),
        )

        with self.assertRaises(BadRequest):
            await safe_answer_callback_query(query)

    async def test_handle_application_error_ignores_expired_callback_error(self):
        context = SimpleNamespace(
            error=BadRequest("Query is too old and response timeout expired or query id is invalid"),
        )

        with patch("competitor_price_monitor.telegram_bot.logger") as logger:
            await handle_application_error(None, context)

        logger.error.assert_not_called()

    async def test_handle_application_error_downgrades_transient_network_errors(self):
        context = SimpleNamespace(
            error=NetworkError("Unknown error in HTTP implementation: SSLError(1, '[SSL] record layer failure (_ssl.c:2580)')"),
        )

        with patch("competitor_price_monitor.telegram_bot.logger") as logger:
            await handle_application_error(None, context)

        logger.warning.assert_called_once()
        logger.error.assert_not_called()

    def test_classify_transient_telegram_network_error_detects_ssl_failure(self):
        summary = classify_transient_telegram_network_error(
            NetworkError("Unknown error in HTTP implementation: SSLError(1, '[SSL] record layer failure (_ssl.c:2580)')")
        )
        self.assertIn("SSL", summary)

    def test_classify_transient_telegram_network_error_detects_remote_protocol_error(self):
        summary = classify_transient_telegram_network_error(
            NetworkError("httpx.RemoteProtocolError: Server disconnected without sending a response.")
        )
        self.assertIn("оборвал соединение", summary)

    def test_should_suppress_asyncio_exception_detects_playwright_driver_shutdown(self):
        self.assertTrue(
            should_suppress_asyncio_exception(
                {"exception": Exception("Connection.init: Connection closed while reading from the driver")}
            )
        )

    def test_build_asyncio_exception_handler_falls_back_to_previous_handler(self):
        previous_handler = unittest.mock.Mock()
        handler = build_asyncio_exception_handler(previous_handler)
        loop = unittest.mock.Mock()
        context = {"message": "plain asyncio error"}

        handler(loop, context)

        previous_handler.assert_called_once_with(loop, context)

    def test_ensure_telegram_api_host_resolves_returns_cleanly(self):
        with patch("competitor_price_monitor.telegram_bot.socket.getaddrinfo", return_value=[object()]):
            ensure_telegram_api_host_resolves()

    def test_ensure_telegram_api_host_resolves_raises_human_message(self):
        with patch(
            "competitor_price_monitor.telegram_bot.socket.getaddrinfo",
            side_effect=OSError("lookup failed"),
        ):
            with self.assertRaises(RuntimeError) as error:
                ensure_telegram_api_host_resolves()

        self.assertIn("Не удаётся подключиться к Telegram API", str(error.exception))


if __name__ == "__main__":
    unittest.main()
