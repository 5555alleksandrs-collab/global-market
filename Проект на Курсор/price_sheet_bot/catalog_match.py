"""
Загрузка локального каталога позиций (как в колонке A) и выбор ближайшей строки для fallback-сопоставления.
"""

from __future__ import annotations

import re
from difflib import SequenceMatcher
from pathlib import Path

from column_match import normalize_for_match_key, sim_suffix_from_normalized_name


def load_price_sheet_catalog(path: str | None) -> list[str]:
    """
    Читает файл: одна позиция на строку, пустые и строки # — пропуск.
    Несколько путей: через запятую в PRICE_SHEET_CATALOG_PATH.
    """
    if not path or not str(path).strip():
        return []
    out: list[str] = []
    for part in [x.strip() for x in str(path).split(",") if x.strip()]:
        p = Path(part)
        if not p.is_file():
            continue
        for raw in p.read_text(encoding="utf-8").splitlines():
            line = raw.strip().strip('"').strip()
            if not line or line.startswith("#"):
                continue
            line = line.replace("\u2060", "").strip()
            if line:
                out.append(line)
    return out


def best_catalog_match(
    user_product: str,
    catalog: list[str],
    *,
    min_similarity: float = 0.82,
) -> str | None:
    """
    Выбирает строку каталога с максимальной похожестью на запрос.
    Сравнение по ключу без артикула (как в find_column_index).
    Заголовки-секции (💻 …) не участвуют.
    """
    uq = normalize_for_match_key(user_product)
    if not uq or not catalog:
        return None
    adaptive_min = min_similarity
    if len(uq) > 55:
        adaptive_min = max(0.74, min_similarity - 0.06)

    suf_u = sim_suffix_from_normalized_name(uq)
    storage_m = re.search(r"\b(\d+)\s*(gb|tb)\b", uq, re.I)
    storage_pat = (
        re.compile(
            rf"\b{re.escape(storage_m.group(1))}\s*{re.escape(storage_m.group(2).lower())}\b",
            re.I,
        )
        if storage_m
        else None
    )

    def _scan(strict_suffix: bool) -> tuple[str | None, float]:
        best_line: str | None = None
        best_score = 0.0
        for line in catalog:
            st = line.strip()
            if st.startswith("💻"):
                continue
            ck = normalize_for_match_key(line)
            if not ck:
                continue
            if storage_pat is not None and not storage_pat.search(st):
                continue
            if strict_suffix and suf_u:
                ck_parts = ck.split()
                ck_suf = ck_parts[-1].lower() if ck_parts else ""
                if ck_suf in ("esim", "sim"):
                    if ck_suf != suf_u:
                        continue
                else:
                    continue
            sim = SequenceMatcher(None, uq, ck).ratio()
            if sim > best_score:
                best_score = sim
                best_line = line
        return best_line, best_score

    best_line, best_score = _scan(True)
    if best_line is None and suf_u:
        best_line, best_score = _scan(False)
    if best_score >= adaptive_min:
        return best_line
    return None
