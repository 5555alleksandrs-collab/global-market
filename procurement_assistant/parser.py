"""
Разбор ответов поставщиков: цена, характеристики, фильтрация шума.
"""

from __future__ import annotations

import re
from typing import Any

from normalizer import normalize

_IGNORE_EXACT = frozenset(
    {
        "есть",
        "ок",
        "ok",
        "окей",
        "уточню",
        "уточняю",
        "посмотрю",
        "узнаю",
        "нет",
        "нету",
        "скоро",
        "+",
    }
)

_CURRENCY_MAP: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\brub\b|руб|₽", re.IGNORECASE), "RUB"),
    (re.compile(r"\busd\b|\$", re.IGNORECASE), "USD"),
    (re.compile(r"\bcny\b|¥|元", re.IGNORECASE), "CNY"),
    (re.compile(r"\beur\b|€", re.IGNORECASE), "EUR"),
]


def _strip_memory_numbers_for_price(text: str) -> str:
    """Убирает из текста явные обозначения памяти, чтобы не путать их с ценой."""
    t = text
    t = re.sub(r"\b\d+\s*gb\b", " ", t, flags=re.IGNORECASE)
    t = re.sub(r"\b\d+\s*tb\b", " ", t, flags=re.IGNORECASE)
    t = re.sub(r"\b1\s*tb\b", " ", t, flags=re.IGNORECASE)
    t = re.sub(r"\b1024\s*gb\b", " ", t, flags=re.IGNORECASE)
    return t


def _extract_price_and_currency(text: str) -> tuple[float | None, str]:
    """
    Извлекает цену (100–99999) и валюту из текста.
    """
    currency = "USD"
    for rx, code in _CURRENCY_MAP:
        if rx.search(text):
            currency = code
            break

    work = _strip_memory_numbers_for_price(text)

    candidates: list[float] = []

    # ¥9800
    for m in re.finditer(r"¥\s*([\d\s.,]+)", text):
        candidates.extend(_parse_number_group(m.group(1)))

    # $1285 или 1285$
    for m in re.finditer(r"\$\s*([\d\s.,]+)|([\d\s.,]+)\s*\$", text):
        g = m.group(1) or m.group(2)
        if g:
            candidates.extend(_parse_number_group(g))

    # 1290 usd / 1300 руб
    for m in re.finditer(
        r"([\d\s.,]+)\s*(?:usd|rub|cny|eur|руб|дол|€|¥|\$)?",
        work,
        re.IGNORECASE,
    ):
        candidates.extend(_parse_number_group(m.group(1)))

    # Общие числа с разделителями
    for m in re.finditer(r"(?<![\d.])\b([\d]{1,3}(?:[\s,][\d]{3})+|[\d]{3,5})\b(?![\d])", work):
        candidates.extend(_parse_number_group(m.group(1)))

    for m in re.finditer(r"(?<![\d.])(\d{3,5})(?![\d])", work):
        try:
            v = float(m.group(1))
            if 100 <= v <= 99999:
                candidates.append(v)
        except ValueError:
            continue

    best: float | None = None
    for c in candidates:
        if 100 <= c <= 99999:
            # Несколько чисел: обычно цена выше объёма памяти (256 vs 1285)
            if best is None or c > best:
                best = c

    return best, currency


def _parse_number_group(s: str) -> list[float]:
    s = s.strip()
    s = s.replace(" ", "").replace(",", "")
    out: list[float] = []
    if not s:
        return out
    try:
        v = float(s)
        if 100 <= v <= 99999:
            out.append(v)
    except ValueError:
        pass
    return out


def parse_reply(text: str, context: dict[str, Any]) -> dict[str, Any] | None:
    """
    Парсит текст ответа поставщика.

    Args:
        text: сырое сообщение.
        context: нормализованный запрос (результат normalizer).

    Returns:
        Словарь с полями model, memory, color, sim, region, price, currency,
        raw_text, parse_confidence; или None если ответ следует игнорировать.
    """
    raw_text = (text or "").strip()
    low = raw_text.lower()

    if len(raw_text) < 5:
        if low in _IGNORE_EXACT or raw_text in _IGNORE_EXACT:
            return None
        # короткий текст без цены и без признаков характеристик
        price_try, _ = _extract_price_and_currency(raw_text)
        if price_try is None and not _has_spec_hints(low):
            return None

    if low in _IGNORE_EXACT:
        return None

    for ign in ("уточню", "уточняю", "посмотрю", "узнаю"):
        if low == ign or (len(low) < 40 and ign in low and not re.search(r"\d{3,}", low)):
            return None

    price, currency = _extract_price_and_currency(raw_text)
    norm = normalize(raw_text)
    has_specs = any(
        [
            norm.get("model"),
            norm.get("memory"),
            norm.get("color"),
            norm.get("sim"),
        ]
    )

    if price is None and not has_specs and len(raw_text) < 5:
        return None

    if price is None and not has_specs:
        # нет ни цены, ни характеристик в явном виде
        if not re.search(r"\d{3,}", raw_text):
            return None

    confidence = 0.5
    if price is not None:
        confidence += 0.25
    if has_specs:
        confidence += 0.25
    if norm.get("model") and context.get("model") and norm["model"] == context.get("model"):
        confidence += 0.1
    confidence = min(1.0, confidence)

    return {
        "model": norm.get("model"),
        "memory": norm.get("memory"),
        "color": norm.get("color"),
        "sim": norm.get("sim"),
        "region": norm.get("region"),
        "price": price,
        "currency": currency,
        "raw_text": raw_text,
        "parse_confidence": confidence,
    }


def _has_spec_hints(low: str) -> bool:
    """Грубая проверка наличия слов о характеристиках."""
    hints = (
        "gb",
        "tb",
        "sim",
        "esim",
        "pro",
        "max",
        "blue",
        "black",
        "white",
        "silver",
        "gold",
        "iphone",
        "айфон",
    )
    return any(h in low for h in hints)
