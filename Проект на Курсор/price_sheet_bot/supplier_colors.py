"""
Сопоставление имени поставщика с цветом заливки (JSON, 0–1 RGB).
"""

from __future__ import annotations

import json
import re
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any


def normalize_key(s: str) -> str:
    s = (s or "").strip().lower().replace("\u00a0", " ")
    s = re.sub(r"\s+", " ", s)
    return s


def load_color_map(path: str | Path) -> dict[str, dict[str, float]]:
    p = Path(path)
    if not p.is_file():
        return {}
    raw = json.loads(p.read_text(encoding="utf-8"))
    out: dict[str, dict[str, float]] = {}
    if isinstance(raw, dict):
        for k, v in raw.items():
            if isinstance(v, dict) and all(x in v for x in ("red", "green", "blue")):
                out[str(k)] = {
                    "red": float(v["red"]),
                    "green": float(v["green"]),
                    "blue": float(v["blue"]),
                }
    return out


def resolve_background_color(
    supplier_from_message: str,
    color_map: dict[str, dict[str, float]],
    *,
    min_similarity: float = 0.75,
) -> tuple[dict[str, float], str | None]:
    """
    Возвращает RGB 0–1 и ключ из таблицы цветов, если найден.

    Если не найден — нейтрально-серый фон.
    """
    default = {"red": 0.93, "green": 0.93, "blue": 0.93}
    q = normalize_key(supplier_from_message)
    if not q:
        return default, None

    # точное совпадение ключа
    for key, rgb in color_map.items():
        if normalize_key(key) == q:
            return dict(rgb), key

    best_key: str | None = None
    best_sim = 0.0
    for key in color_map:
        kn = normalize_key(key)
        sim = SequenceMatcher(None, q, kn).ratio()
        if q in kn or kn in q:
            sim = max(sim, 0.88)
        if sim > best_sim:
            best_sim = sim
            best_key = key

    if best_key is not None and best_sim >= min_similarity:
        return dict(color_map[best_key]), best_key

    return default, None
