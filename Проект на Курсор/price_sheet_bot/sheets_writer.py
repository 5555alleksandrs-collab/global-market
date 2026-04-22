"""
Запись в колонки F/G по строке товара (колонка A) с цветом поставщика (Google Sheets API v4).
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

import config as app_config
from catalog_match import load_price_sheet_catalog
from price_merge import parse_cell_float, pick_two_distinct_price_slots, supplier_for_slot_id
from price_store import load_store
from column_match import build_column_index_cache
from row_match import find_row_index
from supplier_colors import load_color_map, resolve_background_color

logger = logging.getLogger(__name__)


def _catalog_lines() -> list[str] | None:
    raw = getattr(app_config, "PRICE_SHEET_CATALOG_PATH", "") or ""
    lines = load_price_sheet_catalog(raw.strip() or None)
    return lines if lines else None


SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


def _unique_preserve(names: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for n in names:
        n = (n or "").strip()
        if not n or n in seen:
            continue
        seen.add(n)
        out.append(n)
    return out


def _norm_sheet_title(s: str) -> str:
    return " ".join((s or "").strip().split()).lower()


def _resolve_worksheet(
    credentials_path: str,
    spreadsheet_id: str,
    preferred_name: str,
) -> tuple[Any, str]:
    """
    Открывает лист по имени: точное совпадение, без учёта регистра,
    запасные имена из конфига, типичные «Лист1»/«Sheet1», иначе первый лист.
    """
    import gspread

    creds = Credentials.from_service_account_file(credentials_path, scopes=SCOPES)
    client = gspread.authorize(creds)
    sh = client.open_by_key(spreadsheet_id)
    worksheets = sh.worksheets()
    titles = [ws.title for ws in worksheets]
    if not titles:
        raise ValueError("В Google-таблице нет ни одного листа.")

    # Один и тот же лист в Google часто имеет хвостовой пробел в имени — сопоставляем по strip().
    strip_to_title: dict[str, str] = {}
    for t in titles:
        k = t.strip()
        if k not in strip_to_title:
            strip_to_title[k] = t

    candidates = _unique_preserve(
        [
            preferred_name,
            *list(app_config.WORKSHEET_FALLBACK_NAMES),
            "Лист1",
            "Лист 1",
            "Sheet1",
            "Sheet 1",
            "Sheet",
            "Лист",
        ]
    )

    for cand in candidates:
        ck = cand.strip()
        if ck in strip_to_title:
            t = strip_to_title[ck]
            if t.strip() != preferred_name.strip():
                logger.warning(
                    "Лист: в .env указано %r, используется вкладка %r (совпало после trim с кандидатом %r)",
                    preferred_name,
                    t,
                    cand,
                )
            return sh.worksheet(t), t

    for cand in candidates:
        cn = _norm_sheet_title(cand)
        for k, t in strip_to_title.items():
            if _norm_sheet_title(k) == cn:
                if _norm_sheet_title(k) != _norm_sheet_title(preferred_name):
                    logger.warning(
                        "Лист: в .env указано %r, используется вкладка %r (без учёта регистра, кандидат %r)",
                        preferred_name,
                        t,
                        cand,
                    )
                return sh.worksheet(t), t

    if app_config.WORKSHEET_FALLBACK_TO_FIRST:
        logger.warning(
            "Лист %r не найден среди %s — используется первый лист %r. "
            "Задайте WORKSHEET_NAME как имя вкладки в Google Таблице.",
            preferred_name,
            titles,
            titles[0],
        )
        return sh.sheet1, titles[0]

    raise ValueError(
        f"Лист «{preferred_name}» не найден. Доступные вкладки: {', '.join(repr(t) for t in titles)}"
    )


def _build_column_a_pairs(
    ws: Any,
    data_start_row: int,
    max_rows: int,
) -> list[tuple[int, str]]:
    """Список (номер строки, текст в A) для непустых ячеек."""
    all_a = ws.col_values(1)
    if not all_a:
        return []
    last = min(len(all_a), data_start_row - 1 + max_rows)
    out: list[tuple[int, str]] = []
    for row_idx in range(data_start_row - 1, last):
        raw = all_a[row_idx] if row_idx < len(all_a) else ""
        text = str(raw).strip() if raw is not None else ""
        if not text:
            continue
        out.append((row_idx + 1, text))
    return out


def _sheets_service(credentials_path: str):
    creds = Credentials.from_service_account_file(credentials_path, scopes=SCOPES)
    return build("sheets", "v4", credentials=creds, cache_discovery=False)


def _repeat_cell_request(
    sheet_gid: int,
    row_0based: int,
    col_0based: int,
    number_value: float | int,
    bg: dict[str, float],
) -> dict[str, Any]:
    return {
        "repeatCell": {
            "range": {
                "sheetId": sheet_gid,
                "startRowIndex": row_0based,
                "endRowIndex": row_0based + 1,
                "startColumnIndex": col_0based,
                "endColumnIndex": col_0based + 1,
            },
            "cell": {
                "userEnteredValue": {"numberValue": float(number_value)},
                "userEnteredFormat": {"backgroundColor": bg},
            },
            "fields": "userEnteredValue,userEnteredFormat.backgroundColor",
        }
    }


def write_row_prices_with_supplier_colors(
    credentials_path: str,
    spreadsheet_id: str,
    worksheet_name: str,
    *,
    data_start_row: int,
    first_price_column_index: int,
    second_price_column_index: int,
    max_scan_rows: int,
    supplier_colors_path: str,
    product_name: str,
    first_supplier: str,
    first_price: float,
    second_supplier: str | None,
    second_price: float | None,
) -> tuple[int, str, str]:
    """
    Ищет строку по колонке A, пишет цены в F/G с заливкой по поставщику.

    column indices: 1-based (A=1, F=6, G=7).

    Returns:
        (sheet_row, matched_product_text, краткое описание ячеек, имя листа)
    """
    ws, _title_used = _resolve_worksheet(credentials_path, spreadsheet_id, worksheet_name)
    pairs = _build_column_a_pairs(ws, data_start_row, max_scan_rows)
    sheet_row, matched = find_row_index(pairs, product_name, catalog_lines=_catalog_lines())

    cmap = load_color_map(supplier_colors_path)

    sheet_gid = int(ws.id)
    row0 = sheet_row - 1
    f0 = first_price_column_index - 1
    g0 = second_price_column_index - 1

    f_letter = _col_a1(first_price_column_index)
    g_letter = _col_a1(second_price_column_index)
    raw = ws.batch_get([f"{f_letter}{sheet_row}:{g_letter}{sheet_row}"])
    matrix = raw[0] if raw else []
    row_cells: list[Any] = []
    if matrix and len(matrix) > 0:
        row0_cells = matrix[0]
        row_cells = list(row0_cells) if isinstance(row0_cells, list) else [row0_cells]
    while len(row_cells) < 2:
        row_cells.append("")
    old_f = parse_cell_float(row_cells[0])
    old_g = parse_cell_float(row_cells[1])

    offers: dict[str, float] = {first_supplier: float(first_price)}
    if second_supplier is not None and second_price is not None:
        offers[second_supplier] = float(second_price)

    slot_f, slot_g = pick_two_distinct_price_slots(old_f, old_g, offers)
    if slot_f is None:
        nf = float(first_price)
        id_f = first_supplier
    else:
        nf, id_f = slot_f
    if slot_g is None:
        ng = None
        id_g = ""
    else:
        ng, id_g = slot_g

    sup_f = supplier_for_slot_id(id_f)
    sup_g = supplier_for_slot_id(id_g) if ng is not None else ""

    bg1, key1 = resolve_background_color(sup_f, cmap)
    requests: list[dict[str, Any]] = [
        _repeat_cell_request(sheet_gid, row0, f0, nf, bg1),
    ]
    if ng is not None:
        bg2, key2 = resolve_background_color(sup_g, cmap)
        requests.append(_repeat_cell_request(sheet_gid, row0, g0, ng, bg2))
    else:
        requests.append(
            {
                "repeatCell": {
                    "range": {
                        "sheetId": sheet_gid,
                        "startRowIndex": row0,
                        "endRowIndex": row0 + 1,
                        "startColumnIndex": g0,
                        "endColumnIndex": g0 + 1,
                    },
                    "cell": {
                        "userEnteredValue": {"stringValue": ""},
                        "userEnteredFormat": {
                            "backgroundColor": {"red": 1.0, "green": 1.0, "blue": 1.0}
                        },
                    },
                    "fields": "userEnteredValue,userEnteredFormat.backgroundColor",
                }
            }
        )

    service = _sheets_service(credentials_path)
    service.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body={"requests": requests},
    ).execute()

    col_f_letter = _col_a1(first_price_column_index)
    col_g_letter = _col_a1(second_price_column_index)
    if ng is None:
        note = f"{col_f_letter}{sheet_row} = {nf:g} ({key1 or sup_f or first_supplier}); {col_g_letter} очищена"
    else:
        note = (
            f"{col_f_letter}{sheet_row} = {nf:g} ({key1 or sup_f or first_supplier}); "
            f"{col_g_letter}{sheet_row} = {ng:g} ({key2 or sup_g or second_supplier})"
        )

    return sheet_row, matched, note, _title_used


def _fallback_fg_slots_from_items(
    p1: float,
    s1: str,
    s2: str | None,
    p2: float | None,
) -> tuple[tuple[float, str] | None, tuple[float, str] | None]:
    """Если pick_two не смог — всё равно пишем цены из items (p1/p2 уже min/2-я)."""
    if p1 <= 0:
        return None, None
    id1 = str(s1).strip() or "_"
    first = (float(p1), id1)
    if s2 is None or p2 is None:
        return first, None
    if float(p2) <= 0:
        return first, None
    id2 = str(s2).strip() or "_"
    if id2 == id1:
        return first, None
    return first, (float(p2), id2)


def batch_write_fg_for_products(
    credentials_path: str,
    spreadsheet_id: str,
    worksheet_name: str,
    *,
    data_start_row: int,
    first_price_column_index: int,
    second_price_column_index: int,
    max_scan_rows: int,
    supplier_colors_path: str,
    items: list[tuple[str, str, float, str | None, float | None]],
    # product_query, first_supplier, first_price, second_supplier, second_price
) -> tuple[list[str], list[str], str]:
    """
    Одна batchUpdate: для каждого товара — строка по колонке A, F и G с цветами.
    Возвращает (успешные строки отчёта, ошибки, фактическое имя листа).
    """
    ws, title_used = _resolve_worksheet(credentials_path, spreadsheet_id, worksheet_name)
    pairs = _build_column_a_pairs(ws, data_start_row, max_scan_rows)
    cat = _catalog_lines()
    cmap = load_color_map(supplier_colors_path)
    sheet_gid = int(ws.id)
    f0 = first_price_column_index - 1
    g0 = second_price_column_index - 1

    requests: list[dict[str, Any]] = []
    ok: list[str] = []
    err: list[str] = []

    names_only = [p[1] for p in pairs]
    idx_cache = build_column_index_cache(names_only)

    resolved: list[tuple[int, str, str, str, float, str | None, float | None]] = []
    for product_query, s1, p1, s2, p2 in items:
        try:
            sheet_row, matched = find_row_index(
                pairs, product_query, catalog_lines=cat, indexed_cache=idx_cache
            )
        except ValueError as e:
            err.append(f"«{product_query}»: {e}")
            continue
        resolved.append(
            (
                sheet_row,
                matched,
                product_query,
                s1,
                float(p1),
                s2,
                float(p2) if p2 is not None else None,
            )
        )

    cf = _col_a1(first_price_column_index)
    cg = _col_a1(second_price_column_index)

    row_fg: dict[int, tuple[float | None, float | None]] = {}
    if resolved:
        rows_sorted = sorted({r[0] for r in resolved})
        ranges = [f"{cf}{r}:{cg}{r}" for r in rows_sorted]
        try:
            batch_parts = ws.batch_get(ranges)
        except Exception:
            batch_parts = []
        for r, part in zip(rows_sorted, batch_parts or []):
            cells: list[Any] = []
            if part and len(part) > 0:
                row0_cells = part[0]
                cells = list(row0_cells) if isinstance(row0_cells, list) else [row0_cells]
            while len(cells) < 2:
                cells.append("")
            row_fg[r] = (parse_cell_float(cells[0]), parse_cell_float(cells[1]))

    store = load_store(app_config.OFFERS_STORE_PATH)

    for sheet_row, matched, pk, s1, p1, s2, p2 in resolved:
        row0 = sheet_row - 1
        old_f, old_g = row_fg.get(sheet_row, (None, None))
        offers: dict[str, float] = dict(store.get(pk, {}) or {})
        # Всегда подмешиваем итог min/2-я из items: иначе при «грязном» store (все ≤0)
        # if not offers: не срабатывал — словарь непустой, но после фильтра p>0 в pick_two
        # не остаётся цен → slot_f=None и строка молча не пишется.
        offers[str(s1).strip() or "_"] = float(p1)
        if s2 is not None and p2 is not None:
            offers[str(s2).strip() or "_"] = float(p2)

        slot_f, slot_g = pick_two_distinct_price_slots(old_f, old_g, offers)
        if slot_f is None:
            slot_f, slot_g = _fallback_fg_slots_from_items(
                float(p1), s1, s2, p2
            )
        if slot_f is None:
            logger.warning(
                "pick_two None: pk=%r offers=%r old_f=%r old_g=%r",
                pk,
                offers,
                old_f,
                old_g,
            )
            err.append(
                f"«{pk}»: не удалось вычислить F/G (цены в store или в ячейках)."
            )
            continue
        nf, id_f = slot_f
        ng = None
        id_g = ""
        if slot_g is not None:
            ng, id_g = slot_g

        sup_f = supplier_for_slot_id(id_f)
        sup_g = supplier_for_slot_id(id_g) if ng is not None else ""
        bg1, kf = resolve_background_color(sup_f, cmap)
        requests.append(_repeat_cell_request(sheet_gid, row0, f0, nf, bg1))

        if ng is not None:
            bg2, kg = resolve_background_color(sup_g, cmap)
            requests.append(_repeat_cell_request(sheet_gid, row0, g0, ng, bg2))
        else:
            requests.append(
                {
                    "repeatCell": {
                        "range": {
                            "sheetId": sheet_gid,
                            "startRowIndex": row0,
                            "endRowIndex": row0 + 1,
                            "startColumnIndex": g0,
                            "endColumnIndex": g0 + 1,
                        },
                        "cell": {
                            "userEnteredValue": {"stringValue": ""},
                            "userEnteredFormat": {
                                "backgroundColor": {"red": 1.0, "green": 1.0, "blue": 1.0}
                            },
                        },
                        "fields": "userEnteredValue,userEnteredFormat.backgroundColor",
                    }
                }
            )

        if ng is not None:
            ok.append(
                f"«{matched}» {cf}{sheet_row}={nf:g} ({kf or sup_f or s1}) "
                f"{cg}{sheet_row}={ng:g} ({kg or sup_g or s2})"
            )
        else:
            ok.append(
                f"«{matched}» {cf}{sheet_row}={nf:g} ({kf or sup_f or s1}); {cg} пусто"
            )

    if requests:
        service = _sheets_service(credentials_path)
        # Лимит Google Sheets API: не более 100 запросов в одном batchUpdate.
        batch_size = 100
        for start in range(0, len(requests), batch_size):
            chunk = requests[start : start + batch_size]
            service.spreadsheets().batchUpdate(
                spreadsheetId=spreadsheet_id,
                body={"requests": chunk},
            ).execute()

    return ok, err, title_used


def _col_a1(col_1based: int) -> str:
    n = col_1based
    s = ""
    while n > 0:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s
