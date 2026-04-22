import logging
import re
from pathlib import Path

from competitor_price_monitor.models import LoggingConfig


TELEGRAM_TOKEN_URL_RE = re.compile(r"(https://api\.telegram\.org/bot)([^/\s]+)")
ENV_TOKEN_RE = re.compile(r"(COMPETITOR_PRICE_BOT_TOKEN=)([^\s]+)")
BOT_TOKEN_LITERAL_RE = re.compile(r"(bot)(\d{6,}:[A-Za-z0-9_-]{20,})")


class SafeLogFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        message = super().format(record)
        return self._redact_secrets(message)

    @staticmethod
    def _redact_secrets(message: str) -> str:
        sanitized = TELEGRAM_TOKEN_URL_RE.sub(r"\1***REDACTED***", message)
        sanitized = ENV_TOKEN_RE.sub(r"\1***REDACTED***", sanitized)
        sanitized = BOT_TOKEN_LITERAL_RE.sub(r"\1***REDACTED***", sanitized)
        return sanitized


def configure_noisy_loggers() -> None:
    noisy_logger_levels = {
        "httpx": logging.WARNING,
        "httpcore": logging.WARNING,
        "telegram": logging.WARNING,
        "urllib3": logging.WARNING,
        "gspread": logging.WARNING,
        "google.auth": logging.WARNING,
    }
    for logger_name, level in noisy_logger_levels.items():
        logging.getLogger(logger_name).setLevel(level)


def setup_logging(config: LoggingConfig, verbose: bool = False) -> None:
    level_name = "DEBUG" if verbose else config.level
    level = getattr(logging, level_name, logging.INFO)

    log_path = Path(config.file_path)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    formatter = SafeLogFormatter(
        fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    root_logger.handlers[:] = []

    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(formatter)
    file_handler.setLevel(level)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    stream_handler.setLevel(level)

    root_logger.addHandler(file_handler)
    root_logger.addHandler(stream_handler)
    configure_noisy_loggers()
