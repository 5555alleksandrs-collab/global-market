"""
Логирование в консоль и JSON-файл (UTC).
"""

from __future__ import annotations

import json
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _utc_ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def _utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class Logger:
    """
    Пишет события в консоль (INFO) и в JSONL-файл `logs/sessions.json` рядом с сессиями:
    фактически используется файл `logs/activity.jsonl` (каждая строка — JSON-объект),
    чтобы не смешивать поток логов со структурой `SessionStore` в `logs/sessions.json`.
    """

    def __init__(self, jsonl_path: str = "logs/activity.jsonl") -> None:
        self._jsonl_path = Path(jsonl_path)

    def _write_jsonl(self, record: dict[str, Any]) -> None:
        self._jsonl_path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(record, ensure_ascii=False) + "\n"
        try:
            with self._jsonl_path.open("a", encoding="utf-8") as f:
                f.write(line)
        except OSError:
            pass

    def _console(self, line: str) -> None:
        print(line, flush=True)

    def log_session_start(self, session_id: str, query: str, normalized: dict[str, Any]) -> None:
        """Логирует начало сессии."""
        msg = f"[{_utc_ts()}] [SESSION:{session_id}] Начало сессии: {query!r} → {normalized.get('raw')!r}"
        self._console(msg)
        self._write_jsonl(
            {
                "ts": _utc_iso(),
                "session_id": session_id,
                "event": "session_start",
                "query": query,
                "normalized": normalized,
            }
        )

    def log_sent(
        self,
        session_id: str,
        chat_id: int | str,
        chat_name: str,
        message: str,
        dry_run: bool,
    ) -> None:
        """Логирует отправку (или dry-run) в чат."""
        mode = "DRY-RUN" if dry_run else "Отправлено"
        msg = f"[{_utc_ts()}] [SESSION:{session_id}] {mode} в {chat_name} ({chat_id}): {message[:200]}"
        self._console(msg)
        self._write_jsonl(
            {
                "ts": _utc_iso(),
                "session_id": session_id,
                "event": "sent",
                "chat_id": chat_id,
                "chat_name": chat_name,
                "message": message,
                "dry_run": dry_run,
            }
        )

    def log_reply(
        self,
        session_id: str,
        chat_id: int | str,
        chat_name: str,
        raw_text: str,
        parsed: dict[str, Any],
        match: dict[str, Any],
    ) -> None:
        """Логирует входящий ответ поставщика."""
        msg = (
            f"[{_utc_ts()}] [SESSION:{session_id}] Ответ от {chat_name}: "
            f"exact={match.get('is_exact')} score={match.get('match_score')}"
        )
        self._console(msg)
        self._write_jsonl(
            {
                "ts": _utc_iso(),
                "session_id": session_id,
                "event": "reply",
                "chat_id": chat_id,
                "chat_name": chat_name,
                "raw_text": raw_text,
                "parsed": parsed,
                "match": match,
            }
        )

    def log_result(self, session_id: str, result_text: str) -> None:
        """Логирует итоговый текст, отправленный пользователю."""
        msg = f"[{_utc_ts()}] [SESSION:{session_id}] Итог:\n{result_text}"
        self._console(msg)
        self._write_jsonl(
            {
                "ts": _utc_iso(),
                "session_id": session_id,
                "event": "result",
                "result_text": result_text,
            }
        )

    def log_error(self, context: str, error: Exception) -> None:
        """Логирует ошибку с трассировкой."""
        tb = traceback.format_exc()
        msg = f"[{_utc_ts()}] ОШИБКА [{context}]: {error!s}\n{tb}"
        self._console(msg)
        self._write_jsonl(
            {
                "ts": _utc_iso(),
                "event": "error",
                "context": context,
                "error": str(error),
                "traceback": tb,
            }
        )
