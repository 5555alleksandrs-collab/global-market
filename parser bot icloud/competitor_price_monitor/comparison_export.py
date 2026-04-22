from __future__ import annotations

import csv
import json
import logging
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError, as_completed
from datetime import datetime
from pathlib import Path
from threading import Event
from typing import Callable, Dict, List, Optional, Tuple

from competitor_price_monitor.device_catalog import SOURCE_CATALOG, load_supported_devices
from competitor_price_monitor.query_compare import (
    COMPARED_STORE_NAMES,
    QueryMatch,
    compare_query_text,
    fetch_store_match_by_url,
)


logger = logging.getLogger(__name__)

DEFAULT_EXPORT_PATH = Path(__file__).resolve().parent / "data" / "price_comparison_matrix.csv"
DEFAULT_DETAILS_SNAPSHOT_PATH = Path(__file__).resolve().parent / "data" / "price_comparison_latest.details.json"
EXPORT_COMPARE_WORKERS = 4
NO_PRICE_MARKER = ""
PRIMARY_STORE_NAME_BY_SITE_KEY = {
    "iLab": "iLab",
    "ilabstore": "iLab",
    "I LITE": "I LITE",
    "ilite": "I LITE",
    "KingStore Saratov": "KingStore Saratov",
    "kingstore_saratov": "KingStore Saratov",
    "RE:premium": "RE:premium",
    "repremium": "RE:premium",
    "Хатико": "Хатико",
    "hatiko": "Хатико",
}
STORE_COLUMNS: Tuple[str, ...] = (
    "iLab",
    "I LITE",
    "KingStore Saratov",
    "RE:premium",
    "Хатико",
)


class ExportCancelledError(RuntimeError):
    pass


def export_price_comparison_csv(
    export_path: Path = DEFAULT_EXPORT_PATH,
    source_path: Path = SOURCE_CATALOG,
    compare_fn: Callable[[str], Tuple[object, List[QueryMatch]]] = compare_query_text,
    cancel_event: Optional[Event] = None,
) -> Path:
    if is_cancel_requested(cancel_event):
        raise ExportCancelledError("Выгрузка отменена пользователем.")
    devices = load_supported_devices(source_path)
    export_path.parent.mkdir(parents=True, exist_ok=True)
    checked_at = datetime.now().isoformat(timespec="seconds")
    fieldnames = build_fieldnames()
    details_path = build_details_export_path(export_path)
    details_snapshot_path = build_details_snapshot_path(export_path)
    previous_price_map = load_previous_price_map(details_snapshot_path)
    detail_entries: List[Dict[str, object]] = []

    with export_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        executor = ThreadPoolExecutor(max_workers=min(EXPORT_COMPARE_WORKERS, len(devices) or 1))
        should_shutdown_wait = True
        try:
            future_to_index = {}
            device_iter = iter(enumerate(devices))

            def submit_next() -> None:
                if is_cancel_requested(cancel_event):
                    return
                try:
                    index, device = next(device_iter)
                except StopIteration:
                    return
                future = executor.submit(build_comparison_entry, device, checked_at, compare_fn, cancel_event)
                future_to_index[future] = index

            for _ in range(min(EXPORT_COMPARE_WORKERS, len(devices) or 1)):
                submit_next()

            if is_cancel_requested(cancel_event):
                cancel_pending_futures(future_to_index)
                raise ExportCancelledError("Выгрузка отменена пользователем.")

            buffered_entries: Dict[int, Dict[str, object]] = {}
            next_row_index = 0
            written_rows = 0

            while future_to_index:
                if is_cancel_requested(cancel_event):
                    cancel_pending_futures(future_to_index)
                    should_shutdown_wait = False
                    raise ExportCancelledError("Выгрузка отменена пользователем.")
                try:
                    future = next(as_completed(tuple(future_to_index), timeout=0.5))
                except FuturesTimeoutError:
                    continue
                index = future_to_index.pop(future)
                buffered_entries[index] = future.result()
                submit_next()

                while next_row_index in buffered_entries:
                    entry = buffered_entries.pop(next_row_index)
                    attach_previous_prices(entry, previous_price_map)
                    writer.writerow(build_csv_row_from_entry(entry))
                    detail_entries.append(entry)
                    next_row_index += 1
                    written_rows += 1
                    if written_rows % 5 == 0:
                        handle.flush()

            if written_rows % 5 != 0:
                handle.flush()
        finally:
            executor.shutdown(wait=should_shutdown_wait, cancel_futures=True)

        handle.flush()

    details_path.write_text(
        json.dumps(detail_entries, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    details_snapshot_path.write_text(
        json.dumps(detail_entries, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return export_path


def build_fieldnames() -> List[str]:
    fieldnames = [
        "Модель",
    ]
    fieldnames.extend(STORE_COLUMNS)
    fieldnames.extend(
        [
            "Лучшая цена",
            "Где дешевле",
            "Разница max-min",
            "Найдено магазинов",
            "Статус",
        ]
    )

    return fieldnames


def build_comparison_row(device, checked_at: str, compare_fn) -> Dict[str, object]:
    return build_csv_row_from_entry(build_comparison_entry(device, checked_at, compare_fn))


def build_comparison_entry(device, checked_at: str, compare_fn, cancel_event: Optional[Event] = None) -> Dict[str, object]:
    if is_cancel_requested(cancel_event):
        raise ExportCancelledError("Выгрузка отменена пользователем.")
    entry: Dict[str, object] = {
        "label": device.label,
        "query": device.query,
        "my_price": device.my_price,
        "checked_at": checked_at,
        "matches": [],
        "status": "not_found",
    }
    row: Dict[str, object] = {
        "Модель": device.label,
        "Лучшая цена": NO_PRICE_MARKER,
        "Где дешевле": NO_PRICE_MARKER,
        "Разница max-min": NO_PRICE_MARKER,
        "Найдено магазинов": 0,
        "Статус": "not_found",
    }

    for store_name in STORE_COLUMNS:
        row[store_name] = NO_PRICE_MARKER

    try:
        matches = compare_device_matches(device, compare_fn, cancel_event=cancel_event)
    except ExportCancelledError:
        raise
    except Exception as error:  # noqa: BLE001
        logger.exception("Failed to build comparison row for %s", device.query)
        entry["status"] = "error"
        entry["error"] = "{0}: {1}".format(type(error).__name__, error)
        return entry

    if is_cancel_requested(cancel_event):
        raise ExportCancelledError("Выгрузка отменена пользователем.")

    match_by_store = {match.site_name: match for match in matches}

    for store_name in STORE_COLUMNS:
        match = match_by_store.get(store_name)
        if not match:
            continue
        row[store_name] = normalize_cell(match.price)

    row["Найдено магазинов"] = len(matches)
    entry["matches"] = [serialize_match(match) for match in matches]

    prices = [match.price for match in matches if match.price is not None]
    if prices:
        cheapest_price = min(prices)
        highest_price = max(prices)
        cheapest_matches = [match.site_name for match in matches if match.price == cheapest_price]
        row["Лучшая цена"] = cheapest_price
        row["Где дешевле"] = ", ".join(cheapest_matches)
        row["Разница max-min"] = highest_price - cheapest_price
        row["Статус"] = "ok"
        entry["status"] = "ok"

    entry["row"] = row
    return entry


def compare_device_matches(device, compare_fn, cancel_event: Optional[Event] = None) -> List[QueryMatch]:
    del compare_fn
    store_urls = dict(getattr(device, "store_urls", {}) or {})
    primary_url = str(getattr(device, "url", "") or "").strip()
    primary_site = str(getattr(device, "site", "") or "").strip()
    primary_store_name = PRIMARY_STORE_NAME_BY_SITE_KEY.get(primary_site)
    if primary_url and primary_store_name and primary_store_name not in store_urls:
        store_urls[primary_store_name] = primary_url

    direct_matches: List[QueryMatch] = []

    for store_name in STORE_COLUMNS:
        if is_cancel_requested(cancel_event):
            raise ExportCancelledError("Выгрузка отменена пользователем.")
        url = str(store_urls.get(store_name) or "").strip()
        if not url:
            continue
        match = fetch_store_match_by_url(store_name, url)
        if is_cancel_requested(cancel_event):
            raise ExportCancelledError("Выгрузка отменена пользователем.")
        if not match:
            continue
        direct_matches.append(match)

    return sorted(direct_matches, key=lambda item: item.price if item.price is not None else 10**12)


def build_csv_row_from_entry(entry: Dict[str, object]) -> Dict[str, object]:
    row = entry.get("row")
    if isinstance(row, dict):
        return row

    fallback_row: Dict[str, object] = {
        "Модель": entry.get("label", ""),
        "Лучшая цена": NO_PRICE_MARKER,
        "Где дешевле": NO_PRICE_MARKER,
        "Разница max-min": NO_PRICE_MARKER,
        "Найдено магазинов": 0,
        "Статус": entry.get("status", "not_found"),
    }
    for store_name in STORE_COLUMNS:
        fallback_row[store_name] = NO_PRICE_MARKER
    return fallback_row


def serialize_match(match: QueryMatch) -> Dict[str, object]:
    return {
        "site_key": match.site_key,
        "site_name": match.site_name,
        "name": match.name,
        "url": match.url,
        "price": match.price,
        "old_price": match.old_price,
        "site_old_price": match.old_price,
        "previous_price": None,
        "availability_text": match.availability_text,
        "availability_status": match.availability_status,
        "note": match.note,
    }


def build_details_export_path(export_path: Path) -> Path:
    return export_path.with_suffix(".details.json")


def build_details_snapshot_path(export_path: Path) -> Path:
    return export_path.with_name(DEFAULT_DETAILS_SNAPSHOT_PATH.name)


def load_previous_price_map(snapshot_path: Path) -> Dict[Tuple[str, str], int]:
    if not snapshot_path.exists():
        return {}

    raw_entries = json.loads(snapshot_path.read_text(encoding="utf-8"))
    result: Dict[Tuple[str, str], int] = {}
    for entry in raw_entries:
        label = str(entry.get("label") or "")
        for match in entry.get("matches") or []:
            site_name = str(match.get("site_name") or "")
            price = match.get("price")
            if not label or not site_name or price is None:
                continue
            result[(label, site_name)] = int(price)
    return result


def attach_previous_prices(entry: Dict[str, object], previous_price_map: Dict[Tuple[str, str], int]) -> None:
    label = str(entry.get("label") or "")
    for match in entry.get("matches") or []:
        site_name = str(match.get("site_name") or "")
        previous_price = previous_price_map.get((label, site_name))
        match["previous_price"] = previous_price


def normalize_cell(value):
    if value is None:
        return NO_PRICE_MARKER
    return value


def is_cancel_requested(cancel_event: Optional[Event]) -> bool:
    return bool(cancel_event and cancel_event.is_set())


def cancel_pending_futures(future_to_index: Dict[object, int]) -> None:
    for future in future_to_index:
        future.cancel()


__all__ = [
    "COMPARED_STORE_NAMES",
    "DEFAULT_EXPORT_PATH",
    "ExportCancelledError",
    "STORE_COLUMNS",
    "build_details_snapshot_path",
    "build_details_export_path",
    "build_comparison_entry",
    "build_comparison_row",
    "build_fieldnames",
    "export_price_comparison_csv",
]
