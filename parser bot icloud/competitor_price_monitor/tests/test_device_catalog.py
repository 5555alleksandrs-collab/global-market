import csv
import tempfile
import unittest
from pathlib import Path

from competitor_price_monitor.device_catalog import export_supported_devices_csv, load_supported_devices


class DeviceCatalogTests(unittest.TestCase):
    def test_load_supported_devices_reads_query_and_variant(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            source_path = Path(tmp_dir) / "devices.csv"
            source_path.write_text(
                "\n".join(
                    [
                        "key,label,url,my_price,site,enabled",
                        "iphone-17-pro-256-silver,iPhone 17 Pro 256GB Silver,https://ilabstore.ru/catalog/iphone/iphone-17-pro-sim-esim/iphone-17-pro-256gb-silver-sim-esim/,121000,ilabstore,false",
                        "iphone-16-256-black,iPhone 16 256GB Black,https://ilabstore.ru/catalog/iphone/iphone-16/iphone-16-256gb-black/,,ilabstore,false",
                    ]
                ),
                encoding="utf-8",
            )

            devices = load_supported_devices(source_path)

            self.assertEqual(len(devices), 2)
            self.assertEqual(devices[0].query, "17 pro 256 silver sim")
            self.assertEqual(devices[0].my_price, 121000)
            self.assertEqual(devices[0].sim_variant, "SIM + eSIM")
            self.assertEqual(devices[1].query, "16 256 black")
            self.assertIsNone(devices[1].my_price)
            self.assertEqual(devices[1].sim_variant, "not_specified")

    def test_export_supported_devices_csv_writes_expected_columns(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            source_path = Path(tmp_dir) / "devices.csv"
            export_path = Path(tmp_dir) / "supported_devices.csv"
            source_path.write_text(
                "\n".join(
                    [
                        "key,label,url,my_price,site,enabled",
                        "iphone-17-256-black-esim,iPhone 17 256GB Black,https://ilabstore.ru/catalog/iphone/iphone-17/iphone-17-256gb-black-esim/,99990,ilabstore,false",
                    ]
                ),
                encoding="utf-8",
            )

            written_path = export_supported_devices_csv(export_path=export_path, source_path=source_path)

            self.assertEqual(written_path, export_path)
            self.assertTrue(export_path.exists())

            with export_path.open("r", encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))

            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["label"], "iPhone 17 256GB Black")
            self.assertEqual(rows[0]["query"], "17 256 black esim")
            self.assertEqual(rows[0]["sim_variant"], "eSIM")
            self.assertEqual(rows[0]["my_price"], "99990")
            self.assertEqual(rows[0]["site"], "ilabstore")

    def test_load_supported_devices_keeps_raw_query_for_non_iphone_labels(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            source_path = Path(tmp_dir) / "devices.csv"
            source_path.write_text(
                "\n".join(
                    [
                        "key,label,url,my_price,site,enabled",
                        ",PlayStation Portal,,32990,,true",
                    ]
                ),
                encoding="utf-8",
            )

            devices = load_supported_devices(source_path)

            self.assertEqual(len(devices), 1)
            self.assertEqual(devices[0].label, "PlayStation Portal")
            self.assertEqual(devices[0].query, "PlayStation Portal")
            self.assertEqual(devices[0].model, "")
            self.assertEqual(devices[0].sim_variant, "not_specified")
            self.assertTrue(devices[0].key.startswith("playstation-portal"))


if __name__ == "__main__":
    unittest.main()
