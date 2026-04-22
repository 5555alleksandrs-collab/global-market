"""
Поиск номера строки по названию товара в колонке A.
"""

from __future__ import annotations

from catalog_match import best_catalog_match
from column_match import IndexedHeaderRow, build_column_index_cache, find_column_index


def find_row_index(
    row_pairs: list[tuple[int, str]],
    user_product: str,
    *,
    catalog_lines: list[str] | None = None,
    indexed_cache: list[IndexedHeaderRow] | None = None,
) -> tuple[int, str]:
    """
    row_pairs: список (номер_строки_в_таблице, текст_из_A).

    Returns:
        (sheet_row_1based, matched_cell_text)
    """
    if not row_pairs:
        raise ValueError("В колонке «Наименование» нет ни одной заполненной строки в выбранном диапазоне.")

    names = [p[1] for p in row_pairs]
    cache = indexed_cache if indexed_cache is not None else build_column_index_cache(names)
    try:
        idx_1based, matched = find_column_index(
            names, user_product, _indexed_cache=cache
        )
    except ValueError as err:
        if not catalog_lines:
            raise
        canonical = best_catalog_match(user_product, catalog_lines)
        if canonical is None:
            raise err
        try:
            idx_1based, matched = find_column_index(
                names, canonical, _indexed_cache=cache
            )
        except ValueError:
            raise err
    sheet_row = row_pairs[idx_1based - 1][0]
    return sheet_row, matched
