"""
Отличение приветствий и коротких фраз от кодов поставщиков и прайсов.
"""

from __future__ import annotations

import re

# Одна строка — явно не «код поставщика» и не прайс
_SMALLTALK_NORMALIZED: frozenset[str] = frozenset(
    {
        "привет",
        "здравствуй",
        "здравствуйте",
        "добрый день",
        "добрый вечер",
        "доброе утро",
        "доброй ночи",
        "hi",
        "hello",
        "hey",
        "hallo",
        "спасибо",
        "спс",
        "благодарю",
        "thanks",
        "thank you",
        "thx",
        "пока",
        "bye",
        "до свидания",
        "ок",
        "окей",
        "okay",
        "ok",
        "да",
        "нет",
        "yes",
        "no",
        "yep",
        "nope",
        "помощь",
        "help",
        "хелп",
        "что умеешь",
        "что ты умеешь",
        "как дела",
        "как ты",
        "что нового",
        "как жизнь",
        "как сам",
        "ты тут",
        "ладно",
        "понятно",
        "хорошо",
        "ага",
        "угу",
        "алло",
        "эй",
        "слушай",
        "?",
        "!",
        "…",
        "спс большое",
    }
)


def _normalize_chat_phrase(text: str) -> str:
    s = (text or "").strip().lower()
    s = re.sub(r"[.!?…]+$", "", s).strip()
    s = re.sub(r"\s+", " ", s)
    return s


def is_smalltalk_message(text: str) -> bool:
    """
    Короткое сообщение-«болтовня»: привет, спасибо, help — не код поставщика и не прайс.
    """
    raw = (text or "").strip()
    if not raw or "\n" in raw:
        return False
    if len(raw) > 120:
        return False

    t = _normalize_chat_phrase(raw)
    if not t:
        return False

    if t in _SMALLTALK_NORMALIZED:
        return True

    first = t.split(maxsplit=1)[0]
    if first in _SMALLTALK_NORMALIZED:
        return True

    # «привет как дела», «спасибо большое»
    if t.startswith("привет ") or t.startswith("здравствуй "):
        return True
    if t.startswith("спасибо ") or t.startswith("thanks "):
        return True
    if t.startswith("как ") and len(t) < 48:
        return True
    if t.startswith("что ") and len(t) < 48 and "gb" not in t and "tb" not in t and "$" not in t:
        return True

    return False
