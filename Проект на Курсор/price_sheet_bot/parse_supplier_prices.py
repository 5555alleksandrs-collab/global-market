"""
Парсинг строк вида «Поставщик 1285» или «Celltech: 638».
"""

from __future__ import annotations

import re


def _parse_price_token(raw: str) -> float | None:
    s = raw.replace(" ", "").replace(",", "").strip()
    if not s:
        return None
    try:
        v = float(s)
    except ValueError:
        return None
    return v


def parse_supplier_price_lines(
    block: str,
    price_min: float,
    price_max: float,
) -> list[tuple[str, float]]:
    """
    Разбирает блок строк после названия товара.

    Каждая непустая строка: «Имя поставщика» + число (цена).
    Допускаются разделители : или пробелы перед числом.
    """
    out: list[tuple[str, float]] = []
    for line in (block or "").splitlines():
        line = line.strip()
        if not line:
            continue

        m = re.match(r"^(.+?)\s*[:：]\s*([\d\s,]+)\s*$", line)
        if not m:
            m = re.match(r"^(.+?)\s+([\d\s,]+)\s*$", line)
        if not m:
            continue

        name = m.group(1).strip()
        price = _parse_price_token(m.group(2))
        if price is None or not (price_min <= price <= price_max):
            continue
        if not name:
            continue
        out.append((name, price))

    return out


def two_lowest_with_suppliers(
    pairs: list[tuple[str, float]],
) -> tuple[tuple[str, float] | None, tuple[str, float] | None]:
    """
    Сортирует по цене, возвращает (лучший поставщик, цена), (второй, цена).
    """
    if not pairs:
        return None, None
    sorted_pairs = sorted(pairs, key=lambda x: x[1])
    first = sorted_pairs[0]
    if len(sorted_pairs) == 1:
        return first, None
    second = sorted_pairs[1]
    return first, second
