import csv
from pathlib import Path
from typing import Iterable, List

from competitor_price_monitor.models import GoogleSheetsConfig, ProductRecord


CSV_COLUMNS = [
    "product_key",
    "product_label",
    "scraped_name",
    "site_key",
    "url",
    "checked_at",
    "competitor_price",
    "competitor_old_price",
    "previous_competitor_price",
    "price_changed",
    "my_price",
    "price_diff_rub",
    "cheaper_side",
    "competitor_cheaper",
    "availability_status",
    "availability_text",
    "renderer_used",
    "status",
    "error",
]


def write_csv_report(report_path: str, records: Iterable[ProductRecord]) -> None:
    path = Path(report_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = [_record_to_row(record) for record in records]

    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def append_csv_history(history_path: str, records: Iterable[ProductRecord]) -> None:
    path = Path(history_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    file_exists = path.exists()
    rows = [_record_to_row(record) for record in records]

    with path.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_COLUMNS)
        if not file_exists:
            writer.writeheader()
        writer.writerows(rows)


def write_google_sheet(config: GoogleSheetsConfig, records: Iterable[ProductRecord]) -> None:
    if not config.enabled:
        return
    if not config.spreadsheet_id or not config.credentials_path:
        raise ValueError("Google Sheets is enabled, but spreadsheet_id or credentials_path is missing.")

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

    try:
        worksheet = spreadsheet.worksheet(config.worksheet_name)
    except gspread.WorksheetNotFound:
        worksheet = spreadsheet.add_worksheet(title=config.worksheet_name, rows=2000, cols=len(CSV_COLUMNS))

    rows = [_record_to_row(record) for record in records]
    values: List[List[str]] = [CSV_COLUMNS]
    for row in rows:
        values.append([_serialize_cell(row[column]) for column in CSV_COLUMNS])

    worksheet.clear()
    worksheet.update(values)


def _record_to_row(record: ProductRecord) -> dict:
    return {
        "product_key": record.product_key,
        "product_label": record.product_label,
        "scraped_name": record.scraped_name or "",
        "site_key": record.site_key,
        "url": record.url,
        "checked_at": record.checked_at,
        "competitor_price": record.competitor_price,
        "competitor_old_price": record.competitor_old_price,
        "previous_competitor_price": record.previous_competitor_price,
        "price_changed": record.price_changed,
        "my_price": record.my_price,
        "price_diff_rub": record.price_diff_rub,
        "cheaper_side": record.cheaper_side,
        "competitor_cheaper": record.competitor_cheaper,
        "availability_status": record.availability_status,
        "availability_text": record.availability_text or "",
        "renderer_used": record.renderer_used or "",
        "status": record.status,
        "error": record.error or "",
    }


def _serialize_cell(value) -> str:
    if value is None:
        return ""
    return str(value)
