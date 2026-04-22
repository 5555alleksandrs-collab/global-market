"""
Заполнение F/G из накопленных прайсов: среди всех поставщиков по товару выбираются
две позиции — самая низкая цена (F) и вторая по рангу у другого поставщика (G).
Один поставщик не занимает обе ячейки; остальные цены в таблицу не выводятся.
"""

from __future__ import annotations

import math
from typing import Any

from price_store import min_and_second


def parse_cell_float(val: Any) -> float | None:
    """Число из ячейки Google Sheets (строка с запятой или число)."""
    if val is None or val == "":
        return None
    try:
        return float(str(val).replace(",", ".").strip())
    except ValueError:
        return None


def merge_two_lowest(
    old_f: float | None,
    old_g: float | None,
    new_p1: float | None,
    new_p2: float | None,
) -> tuple[float | None, float | None]:
    """
    Два наименьших значения среди (старый F, старый G, новая лучшая, вторая новая).
    Дубликаты учитываются: [650, 650, 800] → 650 и 650.
    """
    vals: list[float] = []
    for x in (old_f, old_g, new_p1, new_p2):
        if x is not None and x > 0:
            vals.append(float(x))
    if not vals:
        return None, None
    vals.sort()
    f = vals[0]
    g = vals[1] if len(vals) > 1 else None
    return f, g


def _close(a: float, b: float, *, eps: float = 0.5) -> bool:
    return math.isclose(a, b, rel_tol=0, abs_tol=eps)


def supplier_for_merged_price(
    value: float,
    s1: str,
    p1: float | None,
    s2: str | None,
    p2: float | None,
) -> str:
    """Какому поставщику соответствует итоговая цена (для заливки). Пусто = нейтральный фон."""
    if p1 is not None and _close(value, p1):
        return s1
    if p2 is not None and s2 is not None and _close(value, p2):
        return s2
    return ""


def supplier_for_slot_id(slot_id: str) -> str:
    """Имя поставщика для заливки; пусто для значений из старых ячеек F/G (legacy)."""
    if not slot_id or slot_id.startswith("_legacy"):
        return ""
    return slot_id


def pick_two_distinct_price_slots(
    old_f: float | None,
    old_g: float | None,
    offers: dict[str, float],
) -> tuple[tuple[float, str] | None, tuple[float, str] | None]:
    """
    Режимы:

    - Несколько поставщиков в offers: глобальный рейтинг по цене — F = минимум, G = второй
      поставщик в отсортированном списке (дороже первого или равен при ничьей между двумя
      разными поставщиками). Старые F/G из листа не участвуют — только данные из store.
    - Один поставщик в offers: его цена сравнивается с уже введёнными в таблице F/G (legacy),
      чтобы не потерять ручные значения, пока нет второго поставщика в базе.
    - offers пуст: только legacy из F/G, если они есть.
    """
    off: dict[str, float] = {}
    for sup, price in (offers or {}).items():
        if price is None:
            continue
        try:
            p = float(price)
        except (TypeError, ValueError):
            continue
        if p > 0:
            sk = str(sup).strip() or "_"
            off[sk] = p

    if len(off) >= 2:
        first_t, second_t = min_and_second(off)
        if first_t is None or second_t is None:
            return None, None
        s1, p1 = first_t
        s2, p2 = second_t
        return (float(p1), s1), (float(p2), s2)

    if len(off) == 1:
        (sn, pv) = next(iter(off.items()))
        pv = float(pv)
        candidates: list[tuple[float, str]] = [(pv, sn)]
        if old_f is not None and old_f > 0:
            candidates.append((float(old_f), "_legacy_f"))
        if old_g is not None and old_g > 0:
            candidates.append((float(old_g), "_legacy_g"))
        candidates.sort(key=lambda x: (x[0], x[1]))
        first = candidates[0]
        second: tuple[float, str] | None = None
        for c in candidates[1:]:
            if c[1] != first[1]:
                second = c
                break
        return first, second

    candidates = []
    if old_f is not None and old_f > 0:
        candidates.append((float(old_f), "_legacy_f"))
    if old_g is not None and old_g > 0:
        candidates.append((float(old_g), "_legacy_g"))
    if not candidates:
        return None, None
    candidates.sort(key=lambda x: (x[0], x[1]))
    first = candidates[0]
    second = None
    for c in candidates[1:]:
        if c[1] != first[1]:
            second = c
            break
    return first, second
