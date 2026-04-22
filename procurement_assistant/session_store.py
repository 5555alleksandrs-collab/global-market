"""
Хранение сессий рассылки в памяти и в JSON на диске.
"""

from __future__ import annotations

import json
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class SessionStore:
    """
    Хранит состояние сессий и дедупликацию отправок по чатам.
    """

    def __init__(self, path: str = "logs/sessions.json", dedup_window_seconds: int = 300) -> None:
        self._path = Path(path)
        self._dedup_window_seconds = dedup_window_seconds
        self._sessions: dict[str, dict[str, Any]] = {}
        self._dedup: dict[tuple[int | str, str], float] = {}
        self._load()

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            raw = self._path.read_text(encoding="utf-8")
            data = json.loads(raw) if raw.strip() else {}
            if isinstance(data, dict) and "sessions" in data:
                self._sessions = {k: v for k, v in data["sessions"].items() if isinstance(v, dict)}
        except (json.JSONDecodeError, OSError):
            self._sessions = {}

    def new_session(self, original_query: str, normalized: dict[str, Any]) -> str:
        """Создаёт новую сессию и возвращает session_id (UUID)."""
        session_id = str(uuid.uuid4())
        nq = normalized.get("raw") or ""
        self._sessions[session_id] = {
            "session_id": session_id,
            "datetime": _utc_now_iso(),
            "original_query": original_query,
            "normalized_query": nq,
            "targets_sent": [],
            "replies": [],
            "final_selected": None,
        }
        return session_id

    def add_sent(self, session_id: str, chat_id: int | str, chat_name: str) -> None:
        """Фиксирует отправку сообщения в чат."""
        s = self._sessions.get(session_id)
        if not s:
            return
        s.setdefault("targets_sent", []).append(
            {
                "chat_id": chat_id,
                "chat_name": chat_name,
                "sent_at": _utc_now_iso(),
            }
        )

    def add_reply(
        self,
        session_id: str,
        chat_id: int | str,
        chat_name: str,
        raw_text: str,
        parsed: dict[str, Any],
        match: dict[str, Any],
    ) -> None:
        """Добавляет ответ поставщика в сессию."""
        s = self._sessions.get(session_id)
        if not s:
            return
        entry = {
            "chat_id": chat_id,
            "chat_name": chat_name,
            "received_at": _utc_now_iso(),
            "raw_reply": raw_text,
            "parsed_model": parsed.get("model"),
            "parsed_memory": parsed.get("memory"),
            "parsed_color": parsed.get("color"),
            "parsed_sim": parsed.get("sim"),
            "parsed_region": parsed.get("region"),
            "parsed_price": parsed.get("price"),
            "parsed_currency": parsed.get("currency") or "USD",
            "exact_match": bool(match.get("is_exact")),
            "match_score": float(match.get("match_score") or 0.0),
            "mismatches": list(match.get("mismatches") or []),
            "match_notes": match.get("notes") or "",
        }
        s.setdefault("replies", []).append(entry)

    def get_exact_matches(self, session_id: str) -> list[dict[str, Any]]:
        """Возвращает ответы с точным совпадением."""
        s = self._sessions.get(session_id)
        if not s:
            return []
        return [r for r in s.get("replies", []) if r.get("exact_match")]

    def get_close_matches(self, session_id: str) -> list[dict[str, Any]]:
        """Возвращает неточные совпадения с match_score > 0.5."""
        s = self._sessions.get(session_id)
        if not s:
            return []
        out: list[dict[str, Any]] = []
        for r in s.get("replies", []):
            if r.get("exact_match"):
                continue
            sc = float(r.get("match_score") or 0.0)
            if sc > 0.5:
                out.append(r)
        return out

    def get_best_price(self, session_id: str) -> dict[str, Any] | None:
        """Среди точных совпадений — запись с минимальной ценой."""
        exact = self.get_exact_matches(session_id)
        best: dict[str, Any] | None = None
        best_price: float | None = None
        for r in exact:
            p = r.get("parsed_price")
            if p is None:
                continue
            try:
                pf = float(p)
            except (TypeError, ValueError):
                continue
            if best_price is None or pf < best_price:
                best_price = pf
                best = r
        return best

    def set_final_selected(self, session_id: str, final: dict[str, Any] | None) -> None:
        """Сохраняет итоговый выбранный вариант."""
        s = self._sessions.get(session_id)
        if s is not None:
            s["final_selected"] = final

    def save(self, session_id: str) -> None:
        """Сохраняет все сессии в JSON-файл."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"sessions": dict(self._sessions), "updated_at": _utc_now_iso()}
        tmp = self._path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self._path)

    def check_dedup(self, chat_id: int | str, message_hash: str) -> bool:
        """
        True, если такое же сообщение уже отправлялось в этот чат недавно.

        При первом вызове с новой парой записывает время и возвращает False.
        """
        key = (chat_id, message_hash)
        now = time.time()
        self._prune_dedup(now)
        if key in self._dedup:
            return True
        self._dedup[key] = now
        return False

    def _prune_dedup(self, now: float) -> None:
        cutoff = now - self._dedup_window_seconds
        dead = [k for k, t in self._dedup.items() if t < cutoff]
        for k in dead:
            del self._dedup[k]

    def get_session(self, session_id: str) -> dict[str, Any] | None:
        """Возвращает копию данных сессии."""
        s = self._sessions.get(session_id)
        if s is None:
            return None
        return dict(s)
