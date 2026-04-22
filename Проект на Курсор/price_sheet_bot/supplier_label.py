"""
Короткое сообщение с кодом поставщика перед прайсом (например «AL»).
"""

from __future__ import annotations

import re

from chat_intent import is_smalltalk_message


def looks_like_supplier_label(text: str) -> bool:
    """
    Одна строка без признаков прайса: только имя/код поставщика для следующего сообщения.
    """
    t = (text or "").strip()
    if not t or "\n" in t:
        return False
    if is_smalltalk_message(t):
        return False
    if len(t) > 48:
        return False
    # признаки текста прайса
    if re.search(r"GB|TB|\$|@", t, re.I):
        return False
    if re.search(r"\d+\s*x\s*[\d.]+\s*\$", t, re.I):
        return False
    # только цифры без букв — не код поставщика
    if re.fullmatch(r"[\d\s.,+-]+", t):
        return False
    if not re.search(r"[A-Za-zА-Яа-яЁё]", t):
        return False
    return True
