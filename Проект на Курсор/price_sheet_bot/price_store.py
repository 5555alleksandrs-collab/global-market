"""
Накопление цен по поставщикам для расчёта min / second min по каждому товару.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_store(path: str | Path) -> dict[str, dict[str, float]]:
    p = Path(path)
    if not p.is_file():
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    offers = data.get("offers") if isinstance(data, dict) else None
    if not isinstance(offers, dict):
        return {}
    out: dict[str, dict[str, float]] = {}
    for k, v in offers.items():
        if not isinstance(v, dict):
            continue
        inner: dict[str, float] = {}
        for sk, sv in v.items():
            try:
                inner[str(sk)] = float(sv)
            except (TypeError, ValueError):
                continue
        if inner:
            out[str(k)] = inner
    return out


def save_store(path: str | Path, store: dict[str, dict[str, float]]) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    payload: dict[str, Any] = {"version": 1, "offers": store}
    p.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def merge_supplier_prices(
    store: dict[str, dict[str, float]],
    supplier: str,
    pairs: list[tuple[str, float]],
) -> list[str]:
    """
    Обновляет цены этого поставщика по товарам. Возвращает список изменённых ключей товара.
    """
    touched: list[str] = []
    for product_key, price in pairs:
        if product_key not in store:
            store[product_key] = {}
        store[product_key][supplier] = float(price)
        touched.append(product_key)
    return list(dict.fromkeys(touched))


def min_and_second(
    supplier_prices: dict[str, float],
) -> tuple[tuple[str, float] | None, tuple[str, float] | None]:
    """
    По одной лучшей цене на поставщика: сортируем всех по цене (по возрастанию).

    - В колонку F попадает самая низкая цена среди всех поставщиков.
    - В G — следующая по рангу цена у другого поставщика (может совпадать с F по числу,
      если у двух поставщиков одинаковая цена — в примере 735 и 735 разными цветами).
    - Цены «посередине» или хуже второй в таблицу не попадают — только топ-1 и топ-2
      среди разных поставщиков.
    - Если поставщик только один — вторая ячейка не заполняется из этого словаря.

    При равенстве цен порядок фиксируется по имени поставщика (детерминированно).
    """
    if not supplier_prices:
        return None, None
    items = sorted(supplier_prices.items(), key=lambda x: (x[1], x[0]))
    first = (items[0][0], float(items[0][1]))
    if len(items) == 1:
        return first, None
    second = (items[1][0], float(items[1][1]))
    return first, second
