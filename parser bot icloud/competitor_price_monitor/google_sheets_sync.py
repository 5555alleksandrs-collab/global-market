from __future__ import annotations

import csv
import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional, Sequence

from competitor_price_monitor.comparison_export import STORE_COLUMNS, build_details_export_path
from competitor_price_monitor.device_catalog import (
    SOURCE_CATALOG,
    SupportedDevice,
    load_supported_devices,
    parse_store_urls_json,
    slugify_device_key,
)
from competitor_price_monitor.models import GoogleSheetsConfig
from competitor_price_monitor.query_compare import detect_store_name_from_url, url_matches_store_domain

logger = logging.getLogger(__name__)

DEFAULT_COMPARISON_WORKSHEET_NAME = "Сравнение цен"
DEFAULT_CATALOG_WORKSHEET_NAME = "Список моделей"
FIRST_WORKSHEET_TOKEN = "__FIRST__"
FIRST_WORKSHEET_DATA_START_ROW = 5
FIRST_WORKSHEET_HEADER_END_ROW = FIRST_WORKSHEET_DATA_START_ROW - 1
FIRST_WORKSHEET_SUMMARY_COLUMN_COUNT = 9
FIRST_WORKSHEET_FIRST_STORE_COLUMN = FIRST_WORKSHEET_SUMMARY_COLUMN_COUNT + 1
FIRST_WORKSHEET_FIXED_COLUMN_COUNT = FIRST_WORKSHEET_SUMMARY_COLUMN_COUNT + (len(STORE_COLUMNS) * 4) + 1
FIRST_WORKSHEET_CHANGED_HIGHLIGHT_COLOR = {
    "red": 0.84,
    "green": 0.95,
    "blue": 0.84,
}
RUNTIME_SOURCE_FIELDNAMES: Sequence[str] = (
    "key",
    "label",
    "url",
    "my_price",
    "site",
    "enabled",
    "store_urls_json",
)

COMPARISON_SHEET_COLUMNS: Sequence[str] = (
    "Модель",
    "Запрос",
    "Моя цена",
    *STORE_COLUMNS,
    "Лучшая цена",
    "Где дешевле",
    "Разница max-min",
    "На сколько я дороже лучшей",
    "Конкурент дешевле меня",
    "Найдено магазинов",
    "Статус",
)

CATALOG_SHEET_COLUMNS: Sequence[str] = (
    "Ключ",
    "Модель",
    "Запрос",
    "Моя цена",
    "Линейка",
    "Память",
    "Цвет",
    "SIM",
    "Источник",
    "URL",
)


@dataclass(frozen=True)
class FirstWorksheetLayout:
    store_start_columns: dict[str, int]
    found_store_names: tuple[str, ...]
    count_column: int
    total_columns: int


def sync_exports_to_google_sheets(
    config: GoogleSheetsConfig,
    comparison_csv_path: Path,
    source_path: Path = SOURCE_CATALOG,
) -> str:
    _validate_google_sheets_config(config)

    try:
        import gspread
        from google.oauth2.service_account import Credentials
    except ImportError as error:
        raise RuntimeError(
            "Google Sheets support is not installed. Install dependencies from requirements.txt."
        ) from error

    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    credentials = Credentials.from_service_account_file(config.credentials_path, scopes=scopes)
    client = gspread.authorize(credentials)
    spreadsheet = client.open_by_key(config.spreadsheet_id)

    comparison_values = build_comparison_sheet_values(comparison_csv_path, source_path)
    catalog_values = build_catalog_sheet_values(source_path)
    comparison_title = config.comparison_worksheet_name or DEFAULT_COMPARISON_WORKSHEET_NAME

    if _is_first_worksheet_token(comparison_title):
        worksheet = _get_or_create_worksheet(
            spreadsheet,
            comparison_title,
            rows=100,
            cols=max(FIRST_WORKSHEET_FIXED_COLUMN_COUNT + 2, 10),
        )
        layout = _read_first_worksheet_layout(worksheet)
        existing_my_prices, existing_label_order = _load_existing_template_state(
            worksheet,
            start_row=FIRST_WORKSHEET_DATA_START_ROW,
        )
        template_values = build_first_worksheet_template_values(
            build_details_export_path(comparison_csv_path),
            source_path,
            retail_prices_by_label=existing_my_prices,
        )
        template_values = _sort_template_values(template_values, existing_label_order)
        template_values = _align_template_values_to_sheet_layout(template_values, layout)
        _write_values_to_existing_template(
            spreadsheet,
            comparison_title,
            template_values,
            start_row=FIRST_WORKSHEET_DATA_START_ROW,
            column_count=layout.total_columns,
            preserve_columns=(2,),
        )
        _sync_first_worksheet_change_highlight_rule(
            spreadsheet,
            worksheet.id,
            layout,
            row_count=len(template_values),
            start_row=FIRST_WORKSHEET_DATA_START_ROW,
        )
    else:
        _write_values_to_worksheet(
            spreadsheet,
            comparison_title,
            comparison_values,
        )
    _write_values_to_worksheet(
        spreadsheet,
        config.catalog_worksheet_name or DEFAULT_CATALOG_WORKSHEET_NAME,
        catalog_values,
    )

    return build_spreadsheet_url(config.spreadsheet_id)


def export_source_catalog_from_first_worksheet(
    config: GoogleSheetsConfig,
    export_path: Path,
    fallback_source_path: Path = SOURCE_CATALOG,
) -> Path:
    _validate_google_sheets_config(config)
    if not _is_first_worksheet_token(config.comparison_worksheet_name or DEFAULT_COMPARISON_WORKSHEET_NAME):
        raise RuntimeError("Runtime source export from Google Sheets requires __FIRST__ comparison worksheet mode.")

    spreadsheet = _open_google_spreadsheet(config)
    worksheet = _get_or_create_worksheet(
        spreadsheet,
        config.comparison_worksheet_name or DEFAULT_COMPARISON_WORKSHEET_NAME,
        rows=100,
        cols=max(FIRST_WORKSHEET_FIXED_COLUMN_COUNT + 2, 10),
    )
    layout = _read_first_worksheet_layout(worksheet)
    rows = _read_first_worksheet_source_rows(worksheet, start_row=FIRST_WORKSHEET_DATA_START_ROW)
    devices_by_label = {device.label: device for device in load_supported_devices(fallback_source_path)}
    runtime_rows = build_runtime_source_catalog_rows(rows, devices_by_label.values(), layout.store_start_columns)

    export_path.parent.mkdir(parents=True, exist_ok=True)
    with export_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(RUNTIME_SOURCE_FIELDNAMES))
        writer.writeheader()
        writer.writerows(runtime_rows)
    return export_path


def export_source_catalog_from_catalog_worksheet(
    config: GoogleSheetsConfig,
    export_path: Path,
) -> Path:
    _validate_google_sheets_config(config)
    spreadsheet = _open_google_spreadsheet(config)
    worksheet = _get_or_create_worksheet(
        spreadsheet,
        config.catalog_worksheet_name or DEFAULT_CATALOG_WORKSHEET_NAME,
        rows=100,
        cols=10,
    )
    rows = worksheet.get_all_values() or []
    runtime_rows = build_runtime_source_catalog_rows_from_catalog_sheet(rows)
    if not runtime_rows:
        raise RuntimeError("Catalog worksheet does not contain data rows to build runtime source catalog.")

    export_path.parent.mkdir(parents=True, exist_ok=True)
    with export_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(RUNTIME_SOURCE_FIELDNAMES))
        writer.writeheader()
        writer.writerows(runtime_rows)
    return export_path


def build_comparison_sheet_values(
    comparison_csv_path: Path,
    source_path: Path = SOURCE_CATALOG,
) -> List[List[object]]:
    devices_by_label = {device.label: device for device in load_supported_devices(source_path)}
    values: List[List[object]] = [list(COMPARISON_SHEET_COLUMNS)]

    with comparison_csv_path.open("r", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            label = row.get("Модель", "")
            device = devices_by_label.get(label)
            my_price = device.my_price if device else None
            best_price = _parse_int(row.get("Лучшая цена"))
            overpriced_by = None
            competitor_cheaper = ""

            if my_price is not None and best_price is not None:
                overpriced_by = max(my_price - best_price, 0)
                competitor_cheaper = "да" if best_price < my_price else "нет"

            values.append(
                [
                    label,
                    device.query if device else "",
                    my_price if my_price is not None else "",
                    *[
                        _value_or_blank(_parse_int(row.get(store_name)))
                        for store_name in STORE_COLUMNS
                    ],
                    best_price if best_price is not None else "",
                    row.get("Где дешевле", ""),
                    _value_or_blank(_parse_int(row.get("Разница max-min"))),
                    overpriced_by if overpriced_by is not None else "",
                    competitor_cheaper,
                    _value_or_blank(_parse_int(row.get("Найдено магазинов"))),
                    row.get("Статус", ""),
                ]
            )

    return values


def build_catalog_sheet_values(source_path: Path = SOURCE_CATALOG) -> List[List[object]]:
    values: List[List[object]] = [list(CATALOG_SHEET_COLUMNS)]

    for device in load_supported_devices(source_path):
        values.append(
            [
                device.key,
                device.label,
                device.query,
                device.my_price if device.my_price is not None else "",
                device.model,
                device.storage,
                device.color,
                device.sim_variant,
                device.site,
                device.url,
            ]
        )

    return values


def build_first_worksheet_template_values(
    details_path: Path,
    source_path: Path = SOURCE_CATALOG,
    retail_prices_by_label: Optional[dict[str, Optional[int]]] = None,
) -> List[List[object]]:
    if not details_path.exists():
        raise RuntimeError(
            "Не найден подробный файл сравнения для заполнения шаблона Google Sheets: {0}".format(
                details_path
            )
        )

    raw_entries = json.loads(details_path.read_text(encoding="utf-8"))
    manual_prices = retail_prices_by_label or {}
    devices_by_label = {device.label: device for device in load_supported_devices(source_path)}
    values: List[List[object]] = []

    for entry in raw_entries:
        label = str(entry.get("label") or "")
        my_price = manual_prices.get(label)
        device = devices_by_label.get(label)
        store_urls = dict(device.store_urls) if device and device.store_urls else {}

        matches = {
            str(match.get("site_name") or ""): match
            for match in entry.get("matches") or []
            if match.get("site_name")
        }
        new_prices = [
            _coalesce_int(match.get("price"))
            for match in matches.values()
            if _coalesce_int(match.get("price")) is not None
        ]
        old_prices = [
            _coalesce_int(match.get("previous_price"))
            for match in matches.values()
            if _coalesce_int(match.get("previous_price")) is not None
        ]

        best_new = min(new_prices) if new_prices else None
        best_old = min(old_prices) if old_prices else None
        best_new_stores = ", ".join(
            sorted(
                store_name
                for store_name, match in matches.items()
                if _coalesce_int(match.get("price")) == best_new
            )
        ) if best_new is not None else ""
        best_old_stores = ", ".join(
            sorted(
                store_name
                for store_name, match in matches.items()
                if _coalesce_int(match.get("previous_price")) == best_old
            )
        ) if best_old is not None else ""

        row: List[object] = [
            label,
            my_price if my_price is not None else "",
            _recommended_price(best_new),
            best_new if best_new is not None else "",
            best_old if best_old is not None else "",
            _diff_vs_my_price(best_new, my_price),
            _diff_vs_my_price(best_old, my_price),
            best_new_stores,
            best_old_stores,
        ]

        for store_name in STORE_COLUMNS:
            match = matches.get(store_name) or {}
            link_url = str(match.get("url") or store_urls.get(store_name) or "").strip()
            price = _coalesce_int(match.get("price"))
            old_price = _coalesce_int(match.get("previous_price"))
            row.extend(
                [
                    _build_template_link_cell(link_url),
                    price if price is not None else "",
                    old_price if old_price is not None else "",
                    _store_price_delta(price, old_price),
                ]
            )

        row.append(len(new_prices))

        values.append(row)

    return values


def build_runtime_source_catalog_rows(
    template_rows: Sequence[Sequence[object]],
    fallback_devices: Iterable[SupportedDevice],
    store_start_columns: Optional[dict[str, int]] = None,
) -> List[dict[str, object]]:
    devices_by_label = {device.label: device for device in fallback_devices}
    rows: List[dict[str, object]] = []

    for row in template_rows:
        label = str(row[0]).strip() if row else ""
        if not label:
            continue

        fallback_device = devices_by_label.get(label)
        my_price = _coalesce_int(row[1]) if len(row) > 1 else None
        rows.append(
            {
                "key": fallback_device.key if fallback_device else slugify_device_key(label),
                "label": label,
                "url": fallback_device.url if fallback_device else "",
                "my_price": my_price if my_price is not None else "",
                "site": fallback_device.site if fallback_device else "",
                "enabled": fallback_device.enabled if fallback_device else "true",
                "store_urls_json": _serialize_store_urls_from_template_row(row, store_start_columns),
            }
        )

    return rows


def build_runtime_source_catalog_rows_from_catalog_sheet(
    rows: Sequence[Sequence[object]],
) -> List[dict[str, object]]:
    if not rows:
        return []

    header = [str(cell or "").strip().lower() for cell in rows[0]]
    column_index = {name: idx for idx, name in enumerate(header)}

    def cell(row: Sequence[object], *names: str) -> str:
        for name in names:
            idx = column_index.get(name)
            if idx is None or idx >= len(row):
                continue
            value = str(row[idx] or "").strip()
            if value:
                return value
        return ""

    runtime_rows: List[dict[str, object]] = []
    for row in rows[1:]:
        label = cell(row, "модель", "label")
        if not label:
            continue
        runtime_rows.append(
            {
                "key": cell(row, "ключ", "key") or slugify_device_key(label),
                "label": label,
                "url": cell(row, "url"),
                "my_price": _coalesce_int(cell(row, "моя цена", "my_price")) or "",
                "site": cell(row, "источник", "site"),
                "enabled": cell(row, "enabled") or "true",
                "store_urls_json": "",
            }
        )
    return runtime_rows


def build_spreadsheet_url(spreadsheet_id: str) -> str:
    return "https://docs.google.com/spreadsheets/d/{0}/edit".format(spreadsheet_id)


def _validate_google_sheets_config(config: GoogleSheetsConfig) -> None:
    if not config.enabled:
        raise ValueError("Google Sheets export is disabled.")
    if not config.spreadsheet_id or not config.credentials_path:
        raise ValueError("Google Sheets is enabled, but spreadsheet_id or credentials_path is missing.")


def _open_google_spreadsheet(config: GoogleSheetsConfig):
    try:
        import gspread
        from google.oauth2.service_account import Credentials
    except ImportError as error:
        raise RuntimeError(
            "Google Sheets support is not installed. Install dependencies from requirements.txt."
        ) from error

    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    credentials = Credentials.from_service_account_file(config.credentials_path, scopes=scopes)
    client = gspread.authorize(credentials)
    return client.open_by_key(config.spreadsheet_id)


def _write_values_to_worksheet(spreadsheet, title: str, values: List[List[object]]) -> None:
    worksheet = _get_or_create_worksheet(
        spreadsheet,
        title,
        rows=max(len(values) + 10, 100),
        cols=max(len(values[0]) + 2, 10),
    )
    worksheet.clear()
    worksheet.resize(rows=max(len(values), 1), cols=max(len(values[0]), 1))
    worksheet.update(values, "A1", value_input_option="USER_ENTERED")
    _apply_worksheet_formatting(spreadsheet, worksheet.id, len(values), len(values[0]))


def _write_values_to_existing_template(
    spreadsheet,
    title: str,
    values: List[List[object]],
    start_row: int,
    column_count: int,
    preserve_columns: Sequence[int] = (),
) -> None:
    worksheet = _get_or_create_worksheet(
        spreadsheet,
        title,
        rows=max(start_row + len(values) + 10, 100),
        cols=max(column_count + 2, 10),
    )
    last_row = max(getattr(worksheet, "row_count", start_row), start_row)
    clear_ranges = [
        "{0}{1}:{2}{3}".format(
            _column_letter(start_column),
            start_row,
            _column_letter(end_column),
            last_row,
        )
        for start_column, end_column in _build_column_segments(column_count, preserve_columns)
    ]
    if clear_ranges:
        worksheet.batch_clear(clear_ranges)

    required_rows = max(last_row, start_row + len(values) - 1)
    required_cols = max(column_count, getattr(worksheet, "col_count", column_count))
    if required_rows > getattr(worksheet, "row_count", 0) or required_cols > getattr(worksheet, "col_count", 0):
        worksheet.resize(rows=max(required_rows, getattr(worksheet, "row_count", required_rows)), cols=required_cols)

    if values:
        for start_column, end_column in _build_column_segments(column_count, preserve_columns):
            segment_values = [row[start_column - 1:end_column] for row in values]
            worksheet.update(
                segment_values,
                "{0}{1}".format(_column_letter(start_column), start_row),
                value_input_option="USER_ENTERED",
            )


def _get_or_create_worksheet(spreadsheet, title: str, rows: int, cols: int):
    if _is_first_worksheet_token(title):
        worksheet = spreadsheet.get_worksheet(0)
        if worksheet is not None:
            return worksheet
        return spreadsheet.add_worksheet(
            title=DEFAULT_COMPARISON_WORKSHEET_NAME,
            rows=rows,
            cols=cols,
        )

    try:
        return spreadsheet.worksheet(title)
    except Exception as error:  # noqa: BLE001
        if type(error).__name__ != "WorksheetNotFound":
            raise
        return spreadsheet.add_worksheet(title=title, rows=rows, cols=cols)


def _is_first_worksheet_token(title: str) -> bool:
    return str(title).strip().upper() == FIRST_WORKSHEET_TOKEN


def _apply_worksheet_formatting(spreadsheet, sheet_id: int, row_count: int, column_count: int) -> None:
    spreadsheet.batch_update(
        {
            "requests": [
                {
                    "updateSheetProperties": {
                        "properties": {
                            "sheetId": sheet_id,
                            "gridProperties": {
                                "frozenRowCount": 1,
                                "frozenColumnCount": 1,
                            },
                        },
                        "fields": "gridProperties.frozenRowCount,gridProperties.frozenColumnCount",
                    }
                },
                {
                    "repeatCell": {
                        "range": {
                            "sheetId": sheet_id,
                            "startRowIndex": 0,
                            "endRowIndex": 1,
                        },
                        "cell": {
                            "userEnteredFormat": {
                                "backgroundColor": {
                                    "red": 0.92,
                                    "green": 0.95,
                                    "blue": 0.99,
                                },
                                "horizontalAlignment": "CENTER",
                                "textFormat": {
                                    "bold": True,
                                },
                            }
                        },
                        "fields": "userEnteredFormat(backgroundColor,horizontalAlignment,textFormat)",
                    }
                },
                {
                    "setBasicFilter": {
                        "filter": {
                            "range": {
                                "sheetId": sheet_id,
                                "startRowIndex": 0,
                                "endRowIndex": max(row_count, 1),
                                "startColumnIndex": 0,
                                "endColumnIndex": max(column_count, 1),
                            }
                        }
                    }
                },
                {
                    "autoResizeDimensions": {
                        "dimensions": {
                            "sheetId": sheet_id,
                            "dimension": "COLUMNS",
                            "startIndex": 0,
                            "endIndex": max(column_count, 1),
                        }
                    }
                },
            ]
        }
    )


def _parse_int(value: Optional[str]) -> Optional[int]:
    if value is None:
        return None
    raw = str(value).strip()
    if not raw:
        return None
    return int(raw)


def _value_or_blank(value: Optional[int]) -> object:
    if value is None:
        return ""
    return value


def _coalesce_int(value) -> Optional[int]:
    if value is None:
        return None
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    raw = str(value).strip()
    if not raw:
        return None
    normalized = (
        raw.replace("\xa0", "")
        .replace(" ", "")
        .replace("−", "-")
        .replace("–", "-")
    )
    if not normalized:
        return None
    return int(normalized)


def _load_existing_template_state(
    worksheet,
    start_row: int,
) -> tuple[dict[str, Optional[int]], List[str]]:
    last_row = max(getattr(worksheet, "row_count", start_row), start_row)
    range_name = "A{0}:B{1}".format(start_row, last_row)
    try:
        rows = worksheet.get(range_name, value_render_option="UNFORMATTED_VALUE")
    except TypeError:
        rows = worksheet.get(range_name)
    except Exception:  # noqa: BLE001
        return {}, []

    my_prices_by_label: dict[str, Optional[int]] = {}
    label_order: List[str] = []
    for row in rows or []:
        label = str(row[0]).strip() if row else ""
        if not label:
            continue
        my_prices_by_label[label] = _coalesce_int(row[1]) if len(row) > 1 else None
        label_order.append(label)
    return my_prices_by_label, label_order


def _read_first_worksheet_source_rows(
    worksheet,
    start_row: int,
) -> List[List[object]]:
    last_row = max(getattr(worksheet, "row_count", start_row), start_row)
    range_name = "A{0}:{1}{2}".format(
        start_row,
        _column_letter(max(getattr(worksheet, "col_count", FIRST_WORKSHEET_FIXED_COLUMN_COUNT), FIRST_WORKSHEET_FIXED_COLUMN_COUNT)),
        last_row,
    )
    try:
        rows = worksheet.get(range_name, value_render_option="FORMULA")
    except TypeError:
        rows = worksheet.get(range_name)
    except Exception:  # noqa: BLE001
        return []
    return rows or []


def _read_first_worksheet_layout(worksheet) -> FirstWorksheetLayout:
    header_rows = _read_first_worksheet_header_rows(worksheet)
    return _detect_first_worksheet_layout(
        header_rows,
        col_count=max(getattr(worksheet, "col_count", FIRST_WORKSHEET_FIXED_COLUMN_COUNT), FIRST_WORKSHEET_FIXED_COLUMN_COUNT),
    )


def _read_first_worksheet_header_rows(worksheet) -> List[List[object]]:
    range_name = "A1:{0}{1}".format(
        _column_letter(max(getattr(worksheet, "col_count", FIRST_WORKSHEET_FIXED_COLUMN_COUNT), FIRST_WORKSHEET_FIXED_COLUMN_COUNT)),
        FIRST_WORKSHEET_HEADER_END_ROW,
    )
    try:
        rows = worksheet.get(range_name, value_render_option="FORMULA")
    except TypeError:
        rows = worksheet.get(range_name)
    except Exception:  # noqa: BLE001
        return []
    return rows or []


def _detect_first_worksheet_layout(header_rows: Sequence[Sequence[object]], col_count: int) -> FirstWorksheetLayout:
    store_start_columns: dict[str, int] = {}
    count_column: Optional[int] = None

    for row in header_rows:
        for column_index, cell in enumerate(row, start=1):
            value = str(cell or "").strip()
            if not value:
                continue
            if value in STORE_COLUMNS and value not in store_start_columns:
                store_start_columns[value] = column_index
            if value == "Найдено магазинов" and count_column is None:
                count_column = column_index

    if not store_start_columns:
        store_start_columns = _default_store_start_columns()
    ordered_store_names = tuple(
        store_name
        for store_name, _column in sorted(store_start_columns.items(), key=lambda item: item[1])
    )
    default_count_column = FIRST_WORKSHEET_SUMMARY_COLUMN_COUNT + (len(STORE_COLUMNS) * 4) + 1
    total_columns = max(
        col_count,
        count_column or default_count_column,
        max((start + 3) for start in store_start_columns.values()),
    )
    return FirstWorksheetLayout(
        store_start_columns=store_start_columns,
        found_store_names=ordered_store_names,
        count_column=count_column or default_count_column,
        total_columns=total_columns,
    )


def _sort_template_values(
    values: List[List[object]],
    preferred_labels: Sequence[str],
) -> List[List[object]]:
    if not values or not preferred_labels:
        return values

    order_map = {label: index for index, label in enumerate(preferred_labels)}
    return sorted(
        values,
        key=lambda row: (
            order_map.get(str(row[0]), len(order_map)),
            str(row[0]),
        ),
    )


def _build_column_segments(
    column_count: int,
    preserve_columns: Sequence[int],
) -> List[tuple[int, int]]:
    preserved = {
        column
        for column in preserve_columns
        if 1 <= column <= column_count
    }
    segments: List[tuple[int, int]] = []
    segment_start: Optional[int] = None

    for column in range(1, column_count + 1):
        if column in preserved:
            if segment_start is not None:
                segments.append((segment_start, column - 1))
                segment_start = None
            continue
        if segment_start is None:
            segment_start = column

    if segment_start is not None:
        segments.append((segment_start, column_count))

    return segments


def _diff_vs_my_price(price: Optional[int], my_price: Optional[int]) -> object:
    if price is None or my_price is None:
        return ""
    return price - my_price


def _recommended_price(best_new_price: Optional[int]) -> object:
    if best_new_price is None:
        return ""
    return best_new_price - 500


def _store_price_delta(price: Optional[int], old_price: Optional[int]) -> object:
    if price is None or old_price is None:
        return ""
    return price - old_price


def _build_hyperlink_formula(url: Optional[str]) -> str:
    raw = str(url or "").strip()
    if not raw:
        return ""
    escaped = raw.replace('"', '""')
    return '=HYPERLINK("{0}";"ссылка")'.format(escaped)


def _build_template_link_cell(url: Optional[str]) -> str:
    raw = str(url or "").strip()
    if not raw:
        return "нет"
    return _build_hyperlink_formula(raw)


def _serialize_store_urls_from_template_row(
    row: Sequence[object],
    store_start_columns: Optional[dict[str, int]] = None,
) -> str:
    store_urls = _extract_store_urls_from_template_row(row, store_start_columns)
    if not store_urls:
        return ""
    return json.dumps(store_urls, ensure_ascii=False, sort_keys=True)


def _extract_store_urls_from_template_row(
    row: Sequence[object],
    store_start_columns: Optional[dict[str, int]] = None,
) -> dict[str, str]:
    store_urls: dict[str, str] = {}
    store_columns = store_start_columns or _default_store_start_columns()

    for store_name, start_column in store_columns.items():
        cell_index = start_column - 1
        if cell_index >= len(row) or store_name not in STORE_COLUMNS:
            continue
        url = _extract_url_from_cell(row[cell_index])
        if not url:
            continue

        detected_store_name = detect_store_name_from_url(url)
        if detected_store_name and detected_store_name != store_name:
            logger.debug(
                "Reassigning direct URL from %s column to %s based on domain: %s",
                store_name,
                detected_store_name,
                url,
            )
            store_urls.setdefault(detected_store_name, url)
            continue
        if not detected_store_name and not url_matches_store_domain(store_name, url):
            logger.debug("Ignoring direct URL for %s due to unknown domain: %s", store_name, url)
            continue

        store_urls[store_name] = url

    return store_urls


def _default_store_start_columns() -> dict[str, int]:
    first_store_column_index = FIRST_WORKSHEET_FIRST_STORE_COLUMN
    store_block_size = 4
    return {
        store_name: first_store_column_index + (store_index * store_block_size)
        for store_index, store_name in enumerate(STORE_COLUMNS)
    }


def _build_first_worksheet_change_formula(
    layout: FirstWorksheetLayout,
    row_number: int,
) -> str:
    clauses: List[str] = [
        'AND($D{0}<>"";$E{0}<>"";$D{0}<>$E{0})'.format(row_number),
    ]

    for store_name in layout.found_store_names:
        start_column = layout.store_start_columns.get(store_name)
        if start_column is None:
            continue
        delta_column = start_column + 3
        delta_letter = _column_letter(delta_column)
        clauses.append(
            'AND(${0}{1}<>"";${0}{1}<>0)'.format(delta_letter, row_number)
        )

    return "=OR({0})".format(";".join(clauses))


def _is_bot_change_highlight_rule(
    rule: dict,
    sheet_id: int,
    start_row: int,
) -> bool:
    ranges = rule.get("ranges") or []
    if len(ranges) != 1:
        return False

    target_range = ranges[0] or {}
    if (
        target_range.get("sheetId") != sheet_id
        or target_range.get("startColumnIndex") != 0
        or target_range.get("endColumnIndex") != 1
        or target_range.get("startRowIndex") != start_row - 1
    ):
        return False

    boolean_rule = rule.get("booleanRule") or {}
    condition = boolean_rule.get("condition") or {}
    if condition.get("type") != "CUSTOM_FORMULA":
        return False

    fmt = boolean_rule.get("format") or {}
    background = fmt.get("backgroundColor") or {}
    return background == FIRST_WORKSHEET_CHANGED_HIGHLIGHT_COLOR


def _build_first_worksheet_change_highlight_requests(
    existing_rules: Sequence[dict],
    *,
    sheet_id: int,
    layout: FirstWorksheetLayout,
    row_count: int,
    start_row: int,
) -> List[dict]:
    requests: List[dict] = []

    matched_indexes = [
        index
        for index, rule in enumerate(existing_rules)
        if _is_bot_change_highlight_rule(rule, sheet_id, start_row)
    ]
    for rule_index in reversed(matched_indexes):
        requests.append(
            {
                "deleteConditionalFormatRule": {
                    "sheetId": sheet_id,
                    "index": rule_index,
                }
            }
        )

    if row_count <= 0:
        return requests

    formula = _build_first_worksheet_change_formula(layout, start_row)
    requests.append(
        {
            "addConditionalFormatRule": {
                "index": 0,
                "rule": {
                    "ranges": [
                        {
                            "sheetId": sheet_id,
                            "startRowIndex": start_row - 1,
                            "endRowIndex": start_row - 1 + row_count,
                            "startColumnIndex": 0,
                            "endColumnIndex": 1,
                        }
                    ],
                    "booleanRule": {
                        "condition": {
                            "type": "CUSTOM_FORMULA",
                            "values": [
                                {
                                    "userEnteredValue": formula,
                                }
                            ],
                        },
                        "format": {
                            "backgroundColor": FIRST_WORKSHEET_CHANGED_HIGHLIGHT_COLOR,
                            "textFormat": {
                                "bold": True,
                            },
                        },
                    },
                },
            }
        }
    )
    return requests


def _sync_first_worksheet_change_highlight_rule(
    spreadsheet,
    sheet_id: int,
    layout: FirstWorksheetLayout,
    row_count: int,
    start_row: int,
) -> None:
    try:
        metadata = spreadsheet.fetch_sheet_metadata(
            params={"fields": "sheets(properties(sheetId),conditionalFormats)"}
        )
    except Exception as error:  # noqa: BLE001
        logger.warning("Failed to fetch Google Sheets metadata for change highlighting: %s", error)
        return

    existing_rules: List[dict] = []
    for sheet in metadata.get("sheets") or []:
        properties = sheet.get("properties") or {}
        if properties.get("sheetId") == sheet_id:
            existing_rules = list(sheet.get("conditionalFormats") or [])
            break

    requests = _build_first_worksheet_change_highlight_requests(
        existing_rules,
        sheet_id=sheet_id,
        layout=layout,
        row_count=row_count,
        start_row=start_row,
    )
    if not requests:
        return

    spreadsheet.batch_update({"requests": requests})


def _repair_first_worksheet_store_links(
    worksheet,
    runtime_rows: Sequence[dict[str, object]],
    layout: FirstWorksheetLayout,
    start_row: int,
) -> None:
    if not runtime_rows:
        return

    for store_name in layout.found_store_names:
        target_column = layout.store_start_columns[store_name]

        column_values = []
        for runtime_row in runtime_rows:
            store_urls = parse_store_urls_json(runtime_row.get("store_urls_json"))
            column_values.append([_build_template_link_cell(store_urls.get(store_name))])

        worksheet.update(
            column_values,
            "{0}{1}".format(_column_letter(target_column), start_row),
            value_input_option="USER_ENTERED",
        )


def _align_template_values_to_sheet_layout(
    values: List[List[object]],
    layout: FirstWorksheetLayout,
) -> List[List[object]]:
    if not values:
        return values

    default_store_columns = _default_store_start_columns()
    default_count_column = FIRST_WORKSHEET_SUMMARY_COLUMN_COUNT + (len(STORE_COLUMNS) * 4) + 1
    layout_store_names = layout.found_store_names or tuple(
        store_name
        for store_name, _column in sorted(layout.store_start_columns.items(), key=lambda item: item[1])
    )
    aligned_rows: List[List[object]] = []

    for row in values:
        aligned = [""] * layout.total_columns
        aligned[:FIRST_WORKSHEET_SUMMARY_COLUMN_COUNT] = row[:FIRST_WORKSHEET_SUMMARY_COLUMN_COUNT]

        for store_name in layout_store_names:
            source_start_column = default_store_columns.get(store_name)
            target_start_column = layout.store_start_columns.get(store_name)
            if source_start_column is None or target_start_column is None:
                continue
            source_start = source_start_column - 1
            target_start = target_start_column - 1
            aligned[target_start:target_start + 4] = row[source_start:source_start + 4]

        if len(row) >= default_count_column:
            aligned[layout.count_column - 1] = row[default_count_column - 1]

        aligned_rows.append(aligned)

    return aligned_rows


def _extract_url_from_cell(value: object) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    hyperlink_match = re.search(r'=HYPERLINK\("([^"]+)"\s*[;,]', raw, re.IGNORECASE)
    if hyperlink_match:
        return hyperlink_match.group(1).strip()
    if raw.startswith("http://") or raw.startswith("https://"):
        return raw
    return ""


def _column_letter(index: int) -> str:
    letters: List[str] = []
    current = index
    while current > 0:
        current, remainder = divmod(current - 1, 26)
        letters.append(chr(65 + remainder))
    return "".join(reversed(letters))


__all__ = [
    "CATALOG_SHEET_COLUMNS",
    "COMPARISON_SHEET_COLUMNS",
    "DEFAULT_CATALOG_WORKSHEET_NAME",
    "DEFAULT_COMPARISON_WORKSHEET_NAME",
    "FIRST_WORKSHEET_TOKEN",
    "build_first_worksheet_template_values",
    "build_catalog_sheet_values",
    "build_comparison_sheet_values",
    "build_spreadsheet_url",
    "sync_exports_to_google_sheets",
]
