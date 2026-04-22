import logging
import unittest

from competitor_price_monitor.logging_setup import SafeLogFormatter, configure_noisy_loggers


class LoggingSetupTests(unittest.TestCase):
    def test_safe_formatter_redacts_telegram_token_in_url(self):
        formatter = SafeLogFormatter("%(message)s")
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname=__file__,
            lineno=1,
            msg='HTTP Request: POST https://api.telegram.org/bot123456:ABCDEF_super_secret/getUpdates "HTTP/1.1 200 OK"',
            args=(),
            exc_info=None,
        )

        formatted = formatter.format(record)

        self.assertIn("https://api.telegram.org/bot***REDACTED***/getUpdates", formatted)
        self.assertNotIn("123456:ABCDEF_super_secret", formatted)

    def test_safe_formatter_redacts_token_assignment(self):
        formatter = SafeLogFormatter("%(message)s")
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname=__file__,
            lineno=1,
            msg="COMPETITOR_PRICE_BOT_TOKEN=123456:ABCDEF_super_secret",
            args=(),
            exc_info=None,
        )

        formatted = formatter.format(record)

        self.assertEqual(formatted, "COMPETITOR_PRICE_BOT_TOKEN=***REDACTED***")

    def test_configure_noisy_loggers_raises_library_log_levels(self):
        noisy_names = ("httpx", "httpcore", "telegram", "urllib3", "gspread", "google.auth")
        original_levels = {name: logging.getLogger(name).level for name in noisy_names}
        try:
            for name in noisy_names:
                logging.getLogger(name).setLevel(logging.INFO)

            configure_noisy_loggers()

            for name in noisy_names:
                self.assertEqual(logging.getLogger(name).level, logging.WARNING)
        finally:
            for name, level in original_levels.items():
                logging.getLogger(name).setLevel(level)


if __name__ == "__main__":
    unittest.main()
