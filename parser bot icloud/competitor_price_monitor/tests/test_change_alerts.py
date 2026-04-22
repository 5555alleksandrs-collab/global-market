import json
import tempfile
import unittest
from pathlib import Path

from competitor_price_monitor.change_alerts import (
    format_price_change_messages,
    load_price_change_events,
)


class ChangeAlertsTests(unittest.TestCase):
    def test_load_price_change_events_uses_previous_price_and_my_price(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            source_path = Path(tmp_dir) / "devices.csv"
            details_path = Path(tmp_dir) / "matrix.details.json"

            source_path.write_text(
                "\n".join(
                    [
                        "key,label,url,my_price,site,enabled",
                        "iphone-17-pro-256-silver,iPhone 17 Pro 256GB Silver,https://example.com,121000,ilabstore,false",
                    ]
                ),
                encoding="utf-8",
            )
            details_path.write_text(
                json.dumps(
                    [
                        {
                            "label": "iPhone 17 Pro 256GB Silver",
                            "matches": [
                                {
                                    "site_name": "iLab",
                                    "url": "https://ilab.example/item",
                                    "price": 118900,
                                    "previous_price": 121900,
                                },
                                {
                                    "site_name": "I LITE",
                                    "url": "https://ilite.example/item",
                                    "price": 121500,
                                    "previous_price": 120500,
                                },
                            ],
                        }
                    ],
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            events = load_price_change_events(details_path, source_path)

            self.assertEqual(len(events), 2)
            self.assertEqual(events[0].store_name, "iLab")
            self.assertEqual(events[0].old_price, 121900)
            self.assertEqual(events[0].new_price, 118900)
            self.assertEqual(events[0].diff_rub, -3000)
            self.assertTrue(events[0].cheaper_than_me)
            self.assertTrue(events[0].became_cheaper_than_me)

    def test_format_price_change_messages_adds_sheet_link(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            source_path = Path(tmp_dir) / "devices.csv"
            details_path = Path(tmp_dir) / "matrix.details.json"

            source_path.write_text(
                "\n".join(
                    [
                        "key,label,url,my_price,site,enabled",
                        "iphone-17-pro-256-silver,iPhone 17 Pro 256GB Silver,https://example.com,121000,ilabstore,false",
                    ]
                ),
                encoding="utf-8",
            )
            details_path.write_text(
                json.dumps(
                    [
                        {
                            "label": "iPhone 17 Pro 256GB Silver",
                            "matches": [
                                {
                                    "site_name": "iLab",
                                    "url": "https://ilab.example/item",
                                    "price": 118900,
                                    "previous_price": 121900,
                                }
                            ],
                        }
                    ],
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            events = load_price_change_events(details_path, source_path)
            messages = format_price_change_messages(events, "https://docs.google.com/spreadsheets/d/test/edit")

            self.assertEqual(len(messages), 1)
            self.assertIn("Автообновление цен: 1 изменений.", messages[0])
            self.assertIn("iPhone 17 Pro 256GB Silver | iLab: 121 900 -> 118 900 (-3 000)", messages[0])
            self.assertIn("стал дешевле вашей на 2 100", messages[0])
            self.assertIn("Таблица: https://docs.google.com/spreadsheets/d/test/edit", messages[0])


if __name__ == "__main__":
    unittest.main()
