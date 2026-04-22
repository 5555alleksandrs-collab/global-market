"""
Нормализация запросов на закупку iPhone: модель, память, цвет, SIM, регион.
"""

from __future__ import annotations

import re
from typing import Any

_GENERATIONS = tuple(range(12, 18))


def _build_model_patterns() -> list[tuple[re.Pattern[str], str]]:
    """Строит список (regex, замена) для моделей iPhone."""
    patterns: list[tuple[re.Pattern[str], str]] = []

    for gen in _GENERATIONS:
        g = str(gen)
        patterns.append(
            (
                re.compile(
                    rf"\b{g}\s*pm\b|\b{g}\s+pm\b|\b{g}pm\b|\b{g}\s*pro\s*max\b|\b{g}\s+pro\s+max\b",
                    re.IGNORECASE,
                ),
                f"{g} Pro Max",
            )
        )
        patterns.append(
            (
                re.compile(rf"\b{g}\s*p\b|\b{g}p\b|\b{g}\s+pro\b|\b{g}pro\b", re.IGNORECASE),
                f"{g} Pro",
            )
        )
        patterns.append(
            (
                re.compile(rf"\b{g}\s+plus\b|\b{g}plus\b", re.IGNORECASE),
                f"{g} Plus",
            )
        )

    for gen in _GENERATIONS:
        g = str(gen)
        patterns.append(
            (
                re.compile(rf"\biphone\s*{g}\s*pro\s*max\b", re.IGNORECASE),
                f"{g} Pro Max",
            )
        )
        patterns.append(
            (
                re.compile(rf"\biphone\s*{g}\s*pro\b(?!\s*max)", re.IGNORECASE),
                f"{g} Pro",
            )
        )
        patterns.append(
            (
                re.compile(rf"\biphone\s*{g}\s*plus\b", re.IGNORECASE),
                f"{g} Plus",
            )
        )
        patterns.append(
            (
                re.compile(rf"\biphone\s*{g}\b(?!\s*(?:pro|plus))", re.IGNORECASE),
                f"{g}",
            )
        )

    for gen in _GENERATIONS:
        g = str(gen)
        patterns.append(
            (
                re.compile(rf"(?<!\d)\b{g}\b(?!\s*(?:pro|plus|pm|p)\b)", re.IGNORECASE),
                f"{g}",
            )
        )

    return patterns


_MODEL_PATTERNS = _build_model_patterns()

_MEMORY_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\b1\s*tb\b|\b1024\s*gb\b|\b1tb\b", re.IGNORECASE), "1TB"),
    (re.compile(r"\b512\s*gb\b|\b512gb\b", re.IGNORECASE), "512GB"),
    (re.compile(r"\b256\s*gb\b|\b256gb\b", re.IGNORECASE), "256GB"),
    (re.compile(r"\b128\s*gb\b|\b128gb\b", re.IGNORECASE), "128GB"),
]


def _memory_from_standalone(s: str) -> tuple[str | None, str]:
    """Ищет 128/256/512 без gb как память (после отдельных паттернов gb)."""
    for mem, label in (
        ("512", "512GB"),
        ("256", "256GB"),
        ("128", "128GB"),
    ):
        rx = re.compile(rf"(?<![\d.])\b{mem}\b(?![\d])", re.IGNORECASE)
        m = rx.search(s)
        if m:
            return label, s[: m.start()] + " " + s[m.end() :]
    return None, s


_COLOR_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\bblue\b|\bсиний\b|\bблу\b", re.IGNORECASE), "Blue"),
    (re.compile(r"\bblack\b|\bчерный\b|\bчёрный\b|\bблэк\b", re.IGNORECASE), "Black"),
    (re.compile(r"\bwhite\b|\bбелый\b", re.IGNORECASE), "White"),
    (re.compile(r"\bsilver\b|\bсеребро\b|\bсеребристый\b", re.IGNORECASE), "Silver"),
    (re.compile(r"\bgold\b|\bзолото\b|\bзолотой\b", re.IGNORECASE), "Gold"),
    (re.compile(r"\bnatural\b|\bнатурал\b", re.IGNORECASE), "Natural"),
    (re.compile(r"\bdesert\s+titanium\b|\bdesert\b|\bдезерт\b", re.IGNORECASE), "Desert Titanium"),
    (re.compile(r"\btitanium\b", re.IGNORECASE), "Titanium"),
]

_SIM_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (
        re.compile(
            r"\b1\s*sim\b|\b1sim\b|\bone\s*sim\b|\bфиз\s*sim\b|\bфизическая\b|\bdual\b|\bфизсим\b",
            re.IGNORECASE,
        ),
        "1SIM",
    ),
    (
        re.compile(r"\besim\b|\bе[\s-]?сим\b|\bесим\b|\bе\s*sim\b|\besim\s*only\b", re.IGNORECASE),
        "eSIM",
    ),
]

_REGION_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\beu\b|\bевро\b|\bевропа\b", re.IGNORECASE), "EU"),
    (re.compile(r"\bjp\b|\bjapan\b|\bяпония\b", re.IGNORECASE), "JP"),
    (re.compile(r"\bus\b|\busa\b|\bсша\b", re.IGNORECASE), "US"),
    (re.compile(r"\bch\b|\bкитай\b|\bchina\b", re.IGNORECASE), "CH"),
    (re.compile(r"\bvc\b|\bвс\b", re.IGNORECASE), "VC"),
    (re.compile(r"\bxa\b", re.IGNORECASE), "XA"),
    (re.compile(r"\bru\b|\bроссия\b", re.IGNORECASE), "RU"),
]

_BRAND_PREFIX = re.compile(
    r"^[\s,;]*(?:iphone|айфон|iphon)\b[\s,;]*",
    re.IGNORECASE,
)


def _clean_input(raw_query: str) -> str:
    """Приводит строку к нижнему регистру и убирает лишние пробелы."""
    s = raw_query.strip().lower()
    s = re.sub(r"[\t\r\n]+", " ", s)
    s = re.sub(r"[,;]+", " ", s)
    s = re.sub(r"[^\w\s\u0400-\u04FF$€¥₽.+-]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _extract_model(s: str) -> str | None:
    """Извлекает нормализованную модель из строки после замен."""
    for gen in reversed(_GENERATIONS):
        g = str(gen)
        if re.search(rf"\b{re.escape(g)}\s+Pro\s+Max\b", s, re.IGNORECASE):
            return f"{g} Pro Max"
        if re.search(rf"\b{re.escape(g)}\s+Pro\b", s, re.IGNORECASE):
            return f"{g} Pro"
        if re.search(rf"\b{re.escape(g)}\s+Plus\b", s, re.IGNORECASE):
            return f"{g} Plus"
        if re.search(rf"(?<![\d.])\b{re.escape(g)}\b(?![\d])", s, re.IGNORECASE):
            return g
    return None


def _first_match(patterns: list[tuple[re.Pattern[str], str]], text: str) -> str | None:
    """Возвращает каноническое значение первого совпавшего паттерна."""
    for rx, canonical in patterns:
        if rx.search(text):
            return canonical
    return None


def normalize(raw_query: str) -> dict[str, Any]:
    """
    Нормализует строку запроса пользователя в словарь полей и строку raw.

    Returns:
        dict с ключами model, memory, color, sim, region, raw.
    """
    if not raw_query or not raw_query.strip():
        return {
            "model": None,
            "memory": None,
            "color": None,
            "sim": None,
            "region": None,
            "raw": "",
        }

    cleaned = _clean_input(raw_query)
    cleaned = _BRAND_PREFIX.sub("", cleaned).strip()
    cleaned = re.sub(r"\s+", " ", cleaned)

    working = cleaned
    for rx, repl in _MODEL_PATTERNS:
        working = rx.sub(repl, working)

    model = _extract_model(working)

    memory = _first_match(_MEMORY_PATTERNS, cleaned)
    if memory is None:
        memory, _ = _memory_from_standalone(cleaned)

    color = _first_match(_COLOR_PATTERNS, cleaned)
    sim = _first_match(_SIM_PATTERNS, cleaned)
    region = _first_match(_REGION_PATTERNS, cleaned)

    parts: list[str] = []
    if model:
        parts.append(model)
    if memory:
        parts.append(memory)
    if color:
        parts.append(color)
    if sim:
        parts.append(sim)
    if region:
        parts.append(region)

    raw = " ".join(parts)
    raw = re.sub(r"\s+", " ", raw).strip()

    return {
        "model": model,
        "memory": memory,
        "color": color,
        "sim": sim,
        "region": region,
        "raw": raw,
    }
