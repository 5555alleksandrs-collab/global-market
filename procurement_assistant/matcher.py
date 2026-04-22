"""
Сопоставление разобранного ответа с исходным запросом.
"""

from __future__ import annotations

from typing import Any


def _eq(a: str | None, b: str | None) -> bool:
    """Сравнение строк без учёта регистра; оба None — совпадение."""
    if a is None and b is None:
        return True
    if a is None or b is None:
        return False
    return str(a).strip().lower() == str(b).strip().lower()


def match(parsed: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    """
    Сравнивает разобранный ответ с нормализованным запросом.

    Args:
        parsed: результат parse_reply.
        context: нормализованный запрос (normalizer).

    Returns:
        is_exact, match_score, mismatches, notes.
    """
    mismatches: list[str] = []
    req_region = context.get("region")

    for key in ("model", "memory", "color", "sim"):
        want = context.get(key)
        if want is None:
            continue
        got = parsed.get(key)
        if not _eq(want, got):
            mismatches.append(key)

    if req_region is not None:
        if not _eq(parsed.get("region"), req_region):
            mismatches.append("region")

    is_exact = len(mismatches) == 0

    # Оценка score при несовпадениях
    score = 1.0
    notes_parts: list[str] = []

    if context.get("model") and not _eq(parsed.get("model"), context.get("model")):
        score = 0.0
        notes_parts.append("другая модель")
    else:
        if "memory" in mismatches:
            score -= 0.4
            notes_parts.append("память не совпадает")
        if "color" in mismatches:
            score -= 0.3
            notes_parts.append("цвет не совпадает")
        if "sim" in mismatches:
            score -= 0.2
            notes_parts.append("SIM не совпадает")
        if "region" in mismatches:
            if req_region is None:
                score -= 0.1
            else:
                score -= 0.1
            notes_parts.append("регион не совпадает")

    score = max(0.0, min(1.0, score))

    notes = "; ".join(notes_parts) if notes_parts else ""

    return {
        "is_exact": is_exact,
        "match_score": score,
        "mismatches": mismatches,
        "notes": notes,
    }
