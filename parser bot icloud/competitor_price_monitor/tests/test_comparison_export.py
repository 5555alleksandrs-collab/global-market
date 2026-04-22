import csv
import json
import tempfile
import time
import unittest
from pathlib import Path
from threading import Event
from threading import Timer
from unittest.mock import patch

from competitor_price_monitor.comparison_export import (
    ExportCancelledError,
    build_details_export_path,
    build_details_snapshot_path,
    compare_device_matches,
    build_comparison_entry,
    export_price_comparison_csv,
)
from competitor_price_monitor.query_compare import QueryMatch, parse_model_query
from competitor_price_monitor.device_catalog import load_supported_devices


class ComparisonExportTests(unittest.TestCase):
    def test_export_price_comparison_csv_persists_previous_prices_for_next_run(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            source_path = Path(tmp_dir) / "devices.csv"
            export_path = Path(tmp_dir) / "price_comparison_matrix.csv"
            source_path.write_text(
                "\n".join(
                    [
                        "key,label,url,my_price,site,enabled,store_urls_json",
                        'iphone-17-pro-256-silver,iPhone 17 Pro 256GB Silver,https://ilabstore.ru/catalog/iphone/iphone-17-pro-sim-esim/iphone-17-pro-256gb-silver-sim-esim/,,ilabstore,false,"{""iLab"": ""https://ilabstore.ru/item""}"',
                    ]
                ),
                encoding="utf-8",
            )

            with patch(
                "competitor_price_monitor.comparison_export.fetch_store_match_by_url",
                return_value=QueryMatch(
                    site_key="ilabstore",
                    site_name="iLab",
                    name="iPhone 17 Pro 256GB Silver",
                    url="https://ilabstore.ru/item",
                    price=118900,
                    old_price=130700,
                    availability_text="В наличии",
                    availability_status="in_stock",
                ),
            ):
                export_price_comparison_csv(
                    export_path=export_path,
                    source_path=source_path,
                    compare_fn=lambda query_text: (parse_model_query(query_text), []),
                )

            with patch(
                "competitor_price_monitor.comparison_export.fetch_store_match_by_url",
                return_value=QueryMatch(
                    site_key="ilabstore",
                    site_name="iLab",
                    name="iPhone 17 Pro 256GB Silver",
                    url="https://ilabstore.ru/item",
                    price=117900,
                    old_price=129900,
                    availability_text="В наличии",
                    availability_status="in_stock",
                ),
            ):
                export_price_comparison_csv(
                    export_path=export_path,
                    source_path=source_path,
                    compare_fn=lambda query_text: (parse_model_query(query_text), []),
                )

            details_path = build_details_export_path(export_path)
            details = json.loads(details_path.read_text(encoding="utf-8"))
            self.assertEqual(details[0]["matches"][0]["previous_price"], 118900)

            snapshot_path = build_details_snapshot_path(export_path)
            snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
            self.assertEqual(snapshot[0]["matches"][0]["price"], 117900)

    def test_export_price_comparison_csv_writes_store_columns(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            source_path = Path(tmp_dir) / "devices.csv"
            export_path = Path(tmp_dir) / "price_comparison_matrix.csv"
            source_path.write_text(
                "\n".join(
                    [
                        "key,label,url,my_price,site,enabled,store_urls_json",
                        'iphone-17-pro-256-silver,iPhone 17 Pro 256GB Silver,https://ilabstore.ru/catalog/iphone/iphone-17-pro-sim-esim/iphone-17-pro-256gb-silver-sim-esim/,,ilabstore,false,"{""iLab"": ""https://ilabstore.ru/item"", ""Хатико"": ""https://hatiko.ru/item""}"',
                        "iphone-16-256-black,iPhone 16 256GB Black,https://ilabstore.ru/catalog/iphone/iphone-16/iphone-16-256gb-black/,,ilabstore,false,",
                    ]
                ),
                encoding="utf-8",
            )

            def fake_direct_fetch(store_name: str, url: str):
                if store_name == "iLab" and url == "https://ilabstore.ru/item":
                    return QueryMatch(
                        site_key="ilabstore",
                        site_name="iLab",
                        name="iPhone 17 Pro 256GB Silver",
                        url="https://ilabstore.ru/item",
                        price=118900,
                        old_price=130700,
                        availability_text="В наличии",
                        availability_status="in_stock",
                    )
                if store_name == "Хатико":
                    return QueryMatch(
                        site_key="hatiko",
                        site_name="Хатико",
                        name="Смартфон Apple iPhone 17 Pro 256GB Silver",
                        url="https://hatiko.ru/item",
                        price=115490,
                        old_price=133090,
                        availability_text="В наличии",
                        availability_status="in_stock",
                    )
                return None

            with patch(
                "competitor_price_monitor.comparison_export.fetch_store_match_by_url",
                side_effect=fake_direct_fetch,
            ):
                written_path = export_price_comparison_csv(
                    export_path=export_path,
                    source_path=source_path,
                    compare_fn=lambda query_text: (parse_model_query(query_text), []),
                )

            self.assertEqual(written_path, export_path)
            with export_path.open("r", encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))

            self.assertEqual(len(rows), 2)
            by_label = {row["Модель"]: row for row in rows}

            rich_row = by_label["iPhone 17 Pro 256GB Silver"]
            self.assertEqual(rich_row["Найдено магазинов"], "2")
            self.assertEqual(rich_row["Где дешевле"], "Хатико")
            self.assertEqual(rich_row["Лучшая цена"], "115490")
            self.assertEqual(rich_row["Разница max-min"], "3410")
            self.assertEqual(rich_row["iLab"], "118900")
            self.assertEqual(rich_row["I LITE"], "")
            self.assertEqual(rich_row["RE:premium"], "")
            self.assertEqual(rich_row["Хатико"], "115490")
            self.assertEqual(rich_row["Статус"], "ok")

            empty_row = by_label["iPhone 16 256GB Black"]
            self.assertEqual(empty_row["Статус"], "not_found")
            self.assertEqual(empty_row["iLab"], "")
            self.assertEqual(empty_row["Лучшая цена"], "")

    def test_export_price_comparison_csv_can_be_cancelled(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            source_path = Path(tmp_dir) / "devices.csv"
            export_path = Path(tmp_dir) / "price_comparison_matrix.csv"
            source_path.write_text(
                "\n".join(
                    [
                        "key,label,url,my_price,site,enabled",
                        "iphone-17-pro-256-silver,iPhone 17 Pro 256GB Silver,https://ilabstore.ru/catalog/iphone/iphone-17-pro-sim-esim/iphone-17-pro-256gb-silver-sim-esim/,,ilabstore,false",
                    ]
                ),
                encoding="utf-8",
            )
            cancel_event = Event()
            cancel_event.set()

            with self.assertRaises(ExportCancelledError):
                export_price_comparison_csv(
                    export_path=export_path,
                    source_path=source_path,
                    compare_fn=lambda query_text: (parse_model_query(query_text), []),
                    cancel_event=cancel_event,
                )

    def test_export_price_comparison_csv_cancels_quickly_while_worker_is_running(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            source_path = Path(tmp_dir) / "devices.csv"
            export_path = Path(tmp_dir) / "price_comparison_matrix.csv"
            source_path.write_text(
                "\n".join(
                    [
                        "key,label,url,my_price,site,enabled,store_urls_json",
                        'iphone-17-pro-256-silver,iPhone 17 Pro 256GB Silver,https://ilabstore.ru/item,,ilabstore,false,"{""iLab"": ""https://ilabstore.ru/item""}"',
                    ]
                ),
                encoding="utf-8",
            )
            cancel_event = Event()

            def slow_direct_fetch(_store_name, _url):
                time.sleep(3)
                return QueryMatch(
                    site_key="ilabstore",
                    site_name="iLab",
                    name="iPhone 17 Pro 256GB Silver",
                    url="https://ilabstore.ru/item",
                    price=118900,
                    old_price=None,
                    availability_text="В наличии",
                    availability_status="in_stock",
                )

            timer = Timer(0.2, cancel_event.set)
            timer.start()
            started = time.perf_counter()
            try:
                with patch(
                    "competitor_price_monitor.comparison_export.fetch_store_match_by_url",
                    side_effect=slow_direct_fetch,
                ):
                    with self.assertRaises(ExportCancelledError):
                        export_price_comparison_csv(
                            export_path=export_path,
                            source_path=source_path,
                            compare_fn=lambda query_text: (parse_model_query(query_text), []),
                            cancel_event=cancel_event,
                        )
            finally:
                timer.cancel()

            elapsed = time.perf_counter() - started
            self.assertLess(elapsed, 2.0)

    def test_build_comparison_entry_keeps_not_found_when_links_are_missing(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            source_path = Path(tmp_dir) / "devices.csv"
            source_path.write_text(
                "\n".join(
                    [
                        "key,label,url,my_price,site,enabled",
                        "iphone-17-256-black,iPhone 17 256GB Black,,99990,,true",
                    ]
                ),
                encoding="utf-8",
            )
            device = load_supported_devices(source_path)[0]
            entry = build_comparison_entry(device, "2026-03-31T10:00:00", lambda _text: (_text, []))
            self.assertEqual(entry["status"], "not_found")
            self.assertNotIn("error", entry)

    def test_compare_device_matches_does_not_search_when_no_direct_links(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            source_path = Path(tmp_dir) / "devices.csv"
            source_path.write_text(
                "\n".join(
                    [
                        "key,label,url,my_price,site,enabled,store_urls_json",
                        'iphone-17-256-black,iPhone 17 256GB Black,,99990,,true,"{}"',
                    ]
                ),
                encoding="utf-8",
            )

            device = load_supported_devices(source_path)[0]
            matches = compare_device_matches(device, lambda _text: (_text, []))
            self.assertEqual(matches, [])

    def test_compare_device_matches_uses_primary_direct_url_without_store_urls_json(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            source_path = Path(tmp_dir) / "devices.csv"
            source_path.write_text(
                "\n".join(
                    [
                        "key,label,url,my_price,site,enabled,store_urls_json",
                        "iphone-17-256-black,iPhone 17 256GB Black,https://i-lite.ru/product/iphone-17-256-black,99990,ilite,true,",
                    ]
                ),
                encoding="utf-8",
            )

            device = load_supported_devices(source_path)[0]
            with patch(
                "competitor_price_monitor.comparison_export.fetch_store_match_by_url",
                return_value=QueryMatch(
                    site_key="ilite",
                    site_name="I LITE",
                    name="iPhone 17 256GB Black",
                    url="https://i-lite.ru/product/iphone-17-256-black",
                    price=109990,
                    old_price=None,
                    availability_text="В наличии",
                    availability_status="in_stock",
                ),
            ):
                matches = compare_device_matches(device, lambda _text: (_text, []))

            self.assertEqual([match.site_name for match in matches], ["I LITE"])


if __name__ == "__main__":
    unittest.main()
