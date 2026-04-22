"""
Разделение сообщения: название телефона (модель) и блок с ценами.
"""

from __future__ import annotations

import re


def split_model_and_price_text(text: str) -> tuple[str | None, str]:
    """
    Возвращает (модель, текст_только_с_ценами).

    Форматы:
    - Первая строка — модель, остальное — прайс.
    - Или первая строка «Модель: ...» / «Model: ...» / «Телефон: ...».
    """
    raw = (text or "").strip()
    if not raw:
        return None, ""

    lines = [ln.strip() for ln in raw.splitlines() if ln.strip()]
    if not lines:
        return None, ""

    first = lines[0]
    low = first.lower()
    prefix_match = re.match(
        r"^(?:модель|model|телефон|phone|iphone|мод)\s*[:：]\s*(.+)$",
        first,
        re.IGNORECASE,
    )
    if prefix_match:
        model = prefix_match.group(1).strip()
        rest = "\n".join(lines[1:])
        return model, rest

    model = first
    rest = "\n".join(lines[1:]) if len(lines) > 1 else ""

    if len(lines) == 1:
        # Одна строка: если в ней только числа — нет названия модели
        if re.fullmatch(r"[\d\s,]+", first.replace("\u00a0", " ")):
            return None, first
        # Одна строка с буквами, но без цен — модель без прайса
        return model, ""

    return model, rest


def model_line_required_error_hint() -> str:
    # HTML (см. bot.py parse_mode): не использовать Markdown — _ ломает разбор.
    return (
        "В <b>первой строке</b> — название товара <b>как в колонке A</b> таблицы "
        "(или строка <code>Модель: ...</code>).\n"
        "Со <b>второй строки</b> — по одной строке на поставщика: <code>ИмяПоставщика цена</code>."
    )
