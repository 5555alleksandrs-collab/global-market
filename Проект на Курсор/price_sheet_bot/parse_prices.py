"""
Извлечение чисел из текста и выбор минимальной и второй по величине цены.
"""

from __future__ import annotations

import re
from typing import Optional


def extract_prices(text: str, price_min: float, price_max: float) -> list[float]:
    """
    Находит в тексте числа, похожие на цены (пробелы/запятые как разделители тысяч).
    """
    if not text or not text.strip():
        return []

    s = text.replace("\u00a0", " ")
    out: list[float] = []

    for m in re.finditer(r"(?:\d{1,3}(?:[\s,]\d{3})+|\d+)\b", s):
        raw = m.group(0).replace(" ", "").replace(",", "")
        if not raw:
            continue
        try:
            v = float(raw)
        except ValueError:
            continue
        if price_min <= v <= price_max:
            out.append(v)

    return out


def two_lowest_distinct(values: list[float]) -> tuple[Optional[float], Optional[float]]:
    """
    Самая низкая цена и вторая по величине среди различных значений.
    Если уникальная только одна — второе значение None.
    """
    if not values:
        return None, None
    uniq = sorted(set(values))
    first = uniq[0]
    second = uniq[1] if len(uniq) > 1 else None
    return first, second
