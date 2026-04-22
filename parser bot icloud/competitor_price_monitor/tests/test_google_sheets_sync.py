import csv
import json
import tempfile
import unittest
from pathlib import Path

from competitor_price_monitor.device_catalog import load_supported_devices
from competitor_price_monitor.google_sheets_sync import (
    FIRST_WORKSHEET_TOKEN,
    _build_first_worksheet_change_formula,
    _build_first_worksheet_change_highlight_requests,
    _build_column_segments,
    _align_template_values_to_sheet_layout,
    _sort_template_values,
    _detect_first_worksheet_layout,
    _repair_first_worksheet_store_links,
    build_runtime_source_catalog_rows,
    build_first_worksheet_template_values,
    build_catalog_sheet_values,
    build_comparison_sheet_values,
    build_spreadsheet_url,
    _get_or_create_worksheet,
    build_runtime_source_catalog_rows_from_catalog_sheet,
)


class GoogleSheetsSyncTests(unittest.TestCase):
    def test_build_first_worksheet_template_values_matches_sheet_layout(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            source_path = Path(tmp_dir) / "devices.csv"
            details_path = Path(tmp_dir) / "matrix.details.json"

            source_path.write_text(
                "\n".join(
                    [
                        "key,label,url,my_price,site,enabled",
                        "iphone-17-pro-256-silver,iPhone 17 Pro 256GB Silver,https://ilabstore.ru/catalog/iphone/iphone-17-pro-sim-esim/iphone-17-pro-256gb-silver-sim-esim/,121000,ilabstore,false",
                    ]
                ),
                encoding="utf-8",
            )
            details_path.write_text(
                json.dumps(
                    [
                        {
                            "label": "iPhone 17 Pro 256GB Silver",
                            "query": "17 pro 256 silver sim",
                            "my_price": 121000,
                            "matches": [
                                {
                                    "site_name": "iLab",
                                    "url": "https://ilab.example/item",
                                    "price": 118900,
                                    "old_price": 130700,
                                    "previous_price": 120900,
                                },
                                {
                                    "site_name": "I LITE",
                                    "url": "https://ilite.example/item",
                                    "price": 116990,
                                    "old_price": None,
                                    "previous_price": None,
                                },
                                {
                                    "site_name": "Хатико",
                                    "url": "https://hatiko.example/item",
                                    "price": 114490,
                                    "old_price": 119990,
                                    "previous_price": 118990,
                                },
                            ],
                        }
                    ],
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            values = build_first_worksheet_template_values(details_path, source_path)

            self.assertEqual(values[0][0], "iPhone 17 Pro 256GB Silver")
            self.assertEqual(values[0][1], "")
            self.assertEqual(values[0][2], 113990)
            self.assertEqual(values[0][3], 114490)
            self.assertEqual(values[0][4], 118990)
            self.assertEqual(values[0][5], "")
            self.assertEqual(values[0][6], "")
            self.assertEqual(values[0][7], "Хатико")
            self.assertEqual(values[0][8], "Хатико")
            self.assertTrue(str(values[0][9]).startswith('=HYPERLINK("https://ilab.example/item"'))
            self.assertEqual(values[0][10], 118900)
            self.assertEqual(values[0][11], 120900)
            self.assertEqual(values[0][12], -2000)
            self.assertEqual(values[0][21], "нет")
            self.assertTrue(str(values[0][25]).startswith('=HYPERLINK("https://hatiko.example/item"'))

    def test_build_first_worksheet_template_values_uses_manual_sheet_price(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            source_path = Path(tmp_dir) / "devices.csv"
            details_path = Path(tmp_dir) / "matrix.details.json"

            source_path.write_text(
                "\n".join(
                    [
                        "key,label,url,my_price,site,enabled",
                        "iphone-17-pro-256-silver,iPhone 17 Pro 256GB Silver,https://ilab.example/item,121000,ilabstore,false",
                    ]
                ),
                encoding="utf-8",
            )
            details_path.write_text(
                json.dumps(
                    [
                        {
                            "label": "iPhone 17 Pro 256GB Silver",
                            "my_price": 121000,
                            "matches": [
                                {
                                    "site_name": "iLab",
                                    "url": "https://ilab.example/item",
                                    "price": 118900,
                                    "previous_price": 120900,
                                }
                            ],
                        }
                    ],
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            values = build_first_worksheet_template_values(
                details_path,
                source_path,
                retail_prices_by_label={"iPhone 17 Pro 256GB Silver": 123456},
            )

            self.assertEqual(values[0][1], 123456)
            self.assertEqual(values[0][5], -4556)
            self.assertEqual(values[0][6], -2556)

    def test_build_first_worksheet_template_values_keeps_source_links_and_marks_missing_as_no(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            source_path = Path(tmp_dir) / "devices.csv"
            details_path = Path(tmp_dir) / "matrix.details.json"

            source_path.write_text(
                "\n".join(
                    [
                        "key,label,url,my_price,site,enabled,store_urls_json",
                        'iphone-13-128-blue,iPhone 13 128 Blue,,,custom,true,"{""iLab"": ""https://ilabstore.ru/catalog/test-item/"", ""Хатико"": ""https://hatiko.ru/product/test-item/""}"',
                    ]
                ),
                encoding="utf-8",
            )
            details_path.write_text(
                json.dumps(
                    [
                        {
                            "label": "iPhone 13 128 Blue",
                            "matches": [
                                {
                                    "site_name": "iLab",
                                    "price": 44900,
                                    "previous_price": 45900,
                                }
                            ],
                        }
                    ],
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            values = build_first_worksheet_template_values(details_path, source_path)

            self.assertTrue(str(values[0][9]).startswith('=HYPERLINK("https://ilabstore.ru/catalog/test-item/"'))
            self.assertEqual(values[0][10], 44900)
            self.assertEqual(values[0][11], 45900)
            self.assertEqual(values[0][13], "нет")
            self.assertEqual(values[0][17], "нет")
            self.assertEqual(values[0][21], "нет")
            self.assertTrue(str(values[0][25]).startswith('=HYPERLINK("https://hatiko.ru/product/test-item/"'))

    def test_build_runtime_source_catalog_rows_uses_header_based_store_columns(self):
        header_rows = [
            ["", "", "", "", "", "", "", "", "", "iLab", "", "", "", "I LITE", "", "", "", "KingStore Saratov", "", "", "", "RE:premium", "", "", "", "Хатико", "", "", "", "Найдено магазинов"],
        ]
        layout = _detect_first_worksheet_layout(header_rows, col_count=30)
        rows = build_runtime_source_catalog_rows(
            [
                [
                    "iPhone 13 128 Blue",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    '=HYPERLINK("https://ilabstore.ru/catalog/test-item/";"ссылка")',
                    "",
                    "",
                    "",
                    "https://i-lite.ru/test-item",
                    "",
                    "",
                    "",
                    "https://saratov.kingstore.io/catalog/test-item/",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    '=HYPERLINK("https://hatiko.ru/product/test-item/";"ссылка")',
                ],
            ],
            [],
            layout.store_start_columns,
        )

        self.assertIn('"KingStore Saratov": "https://saratov.kingstore.io/catalog/test-item/"', rows[0]["store_urls_json"])

    def test_detect_first_worksheet_layout_preserves_actual_sheet_store_order(self):
        header_rows = [
            ["", "", "", "", "", "", "", "", "", "RE:premium", "", "", "", "iLab", "", "", "", "Хатико", "", "", "", "KingStore Saratov", "", "", "", "Найдено магазинов"],
        ]

        layout = _detect_first_worksheet_layout(header_rows, col_count=30)

        self.assertEqual(
            layout.found_store_names,
            ("RE:premium", "iLab", "Хатико", "KingStore Saratov"),
        )

    def test_build_first_worksheet_change_formula_uses_best_price_and_store_delta_columns(self):
        header_rows = [
            ["", "", "", "", "", "", "", "", "", "iLab", "", "", "", "KingStore Saratov", "", "", "", "Хатико", "", "", "", "Найдено магазинов"],
        ]
        layout = _detect_first_worksheet_layout(header_rows, col_count=22)

        formula = _build_first_worksheet_change_formula(layout, 5)

        self.assertEqual(
            formula,
            '=OR(AND($D5<>"";$E5<>"";$D5<>$E5);AND($M5<>"";$M5<>0);AND($Q5<>"";$Q5<>0);AND($U5<>"";$U5<>0))',
        )

    def test_build_first_worksheet_change_highlight_requests_replaces_existing_bot_rule(self):
        header_rows = [
            ["", "", "", "", "", "", "", "", "", "iLab", "", "", "", "RE:premium", "", "", "", "Хатико", "", "", "", "Найдено магазинов"],
        ]
        layout = _detect_first_worksheet_layout(header_rows, col_count=22)
        existing_rules = [
            {
                "ranges": [
                    {
                        "sheetId": 123,
                        "startRowIndex": 4,
                        "endRowIndex": 50,
                        "startColumnIndex": 0,
                        "endColumnIndex": 1,
                    }
                ],
                "booleanRule": {
                    "condition": {
                        "type": "CUSTOM_FORMULA",
                        "values": [{"userEnteredValue": '=OR(AND($D5<>"";$E5<>"";$D5<>$E5))'}],
                    },
                    "format": {
                        "backgroundColor": {
                            "red": 0.84,
                            "green": 0.95,
                            "blue": 0.84,
                        }
                    },
                },
            }
        ]

        requests = _build_first_worksheet_change_highlight_requests(
            existing_rules,
            sheet_id=123,
            layout=layout,
            row_count=10,
            start_row=5,
        )

        self.assertEqual(requests[0]["deleteConditionalFormatRule"]["sheetId"], 123)
        add_rule = requests[1]["addConditionalFormatRule"]["rule"]
        self.assertEqual(add_rule["ranges"][0]["startColumnIndex"], 0)
        self.assertEqual(add_rule["ranges"][0]["endColumnIndex"], 1)
        self.assertEqual(add_rule["ranges"][0]["startRowIndex"], 4)
        self.assertEqual(add_rule["ranges"][0]["endRowIndex"], 14)
        self.assertEqual(
            add_rule["booleanRule"]["condition"]["values"][0]["userEnteredValue"],
            '=OR(AND($D5<>"";$E5<>"";$D5<>$E5);AND($M5<>"";$M5<>0);AND($Q5<>"";$Q5<>0);AND($U5<>"";$U5<>0))',
        )

    def test_align_template_values_skips_store_blocks_missing_from_sheet(self):
        header_rows = [
            ["", "", "", "", "", "", "", "", "", "iLab", "", "", "", "RE:premium", "", "", "", "Хатико", "", "", "", "Найдено магазинов"],
        ]
        layout = _detect_first_worksheet_layout(header_rows, col_count=22)
        source_row = [
            "iPhone 17 Pro 256GB Silver",
            "",
            113990,
            114490,
            118990,
            "",
            "",
            "Хатико",
            "Хатико",
            '=HYPERLINK("https://ilab.example/item";"ссылка")',
            118900,
            120900,
            -2000,
            '=HYPERLINK("https://ilite.example/item";"ссылка")',
            116990,
            "",
            "",
            '=HYPERLINK("https://kingstore.example/item";"ссылка")',
            115990,
            116990,
            -1000,
            '=HYPERLINK("https://repremium.example/item";"ссылка")',
            114990,
            115990,
            -1000,
            '=HYPERLINK("https://hatiko.example/item";"ссылка")',
            114490,
            118990,
            -4500,
            4,
        ]

        aligned = _align_template_values_to_sheet_layout([source_row], layout)[0]

        self.assertEqual(aligned[9], '=HYPERLINK("https://ilab.example/item";"ссылка")')
        self.assertEqual(aligned[13], '=HYPERLINK("https://repremium.example/item";"ссылка")')
        self.assertEqual(aligned[17], '=HYPERLINK("https://hatiko.example/item";"ссылка")')
        self.assertNotIn("https://ilite.example/item", "".join(str(cell) for cell in aligned))
        self.assertNotIn("https://kingstore.example/item", "".join(str(cell) for cell in aligned))

    def test_build_runtime_source_catalog_rows_keeps_repremium_ru_link(self):
        header_rows = [
            ["", "", "", "", "", "", "", "", "", "iLab", "", "", "", "I LITE", "", "", "", "KingStore Saratov", "", "", "", "RE:premium", "", "", "", "Хатико", "", "", "", "Найдено магазинов"],
        ]
        layout = _detect_first_worksheet_layout(header_rows, col_count=30)
        rows = build_runtime_source_catalog_rows(
            [
                [
                    "iPhone 17 Air 512GB White",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    '=HYPERLINK("https://repremium.ru/catalog/smartfon_apple_iphone_17_air_512_gb_belyy/";"ссылка")',
                    "",
                    "",
                    "",
                ],
            ],
            [],
            layout.store_start_columns,
        )

        self.assertIn(
            '"RE:premium": "https://repremium.ru/catalog/smartfon_apple_iphone_17_air_512_gb_belyy/"',
            rows[0]["store_urls_json"],
        )

    def test_first_worksheet_token_uses_first_sheet(self):
        class FakeWorksheet:
            def __init__(self, title: str):
                self.title = title

        class FakeSpreadsheet:
            def __init__(self):
                self.first = FakeWorksheet("Лист1")

            def get_worksheet(self, index: int):
                if index == 0:
                    return self.first
                return None

            def worksheet(self, title: str):
                raise AssertionError("worksheet() should not be called for first-sheet mode")

            def add_worksheet(self, title: str, rows: int, cols: int):
                raise AssertionError("add_worksheet() should not be called when first sheet exists")

        worksheet = _get_or_create_worksheet(FakeSpreadsheet(), FIRST_WORKSHEET_TOKEN, rows=100, cols=10)

        self.assertEqual(worksheet.title, "Лист1")

    def test_repair_first_worksheet_store_links_rewrites_columns_from_runtime_rows(self):
        class FakeWorksheet:
            def __init__(self):
                self.calls = []

            def update(self, values, cell, value_input_option="RAW"):
                self.calls.append((cell, values, value_input_option))

        header_rows = [
            ["", "", "", "", "", "", "", "", "", "iLab", "", "", "", "I LITE", "", "", "", "KingStore Saratov", "", "", "", "RE:premium", "", "", "", "Хатико", "", "", "", "Найдено магазинов"],
        ]
        layout = _detect_first_worksheet_layout(header_rows, col_count=30)
        worksheet = FakeWorksheet()
        runtime_rows = [
            {
                "label": "iPhone 17 Air 512GB White",
                "store_urls_json": json.dumps(
                    {
                        "iLab": "https://ilabstore.ru/catalog/test-item/",
                        "RE:premium": "https://repremium.ru/catalog/smartfon_apple_iphone_17_air_512_gb_belyy/",
                    },
                    ensure_ascii=False,
                ),
            }
        ]

        _repair_first_worksheet_store_links(
            worksheet,
            runtime_rows,
            layout,
            start_row=5,
        )

        by_cell = {cell: values for cell, values, _ in worksheet.calls}
        self.assertEqual(by_cell["J5"], [['=HYPERLINK("https://ilabstore.ru/catalog/test-item/";"ссылка")']])
        self.assertEqual(by_cell["V5"], [['=HYPERLINK("https://repremium.ru/catalog/smartfon_apple_iphone_17_air_512_gb_belyy/";"ссылка")']])
        self.assertEqual(by_cell["N5"], [["нет"]])
        self.assertEqual(by_cell["R5"], [["нет"]])
        self.assertEqual(by_cell["Z5"], [["нет"]])

    def test_build_comparison_sheet_values_adds_my_price_columns(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            source_path = Path(tmp_dir) / "devices.csv"
            comparison_path = Path(tmp_dir) / "matrix.csv"

            source_path.write_text(
                "\n".join(
                    [
                        "key,label,url,my_price,site,enabled",
                        "iphone-17-pro-256-silver,iPhone 17 Pro 256GB Silver,https://ilabstore.ru/catalog/iphone/iphone-17-pro-sim-esim/iphone-17-pro-256gb-silver-sim-esim/,121000,ilabstore,false",
                    ]
                ),
                encoding="utf-8",
            )

            with comparison_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow(
                    [
                        "Модель",
                        "iLab",
                        "I LITE",
                        "KingStore Saratov",
                        "RE:premium",
                        "Хатико",
                        "Лучшая цена",
                        "Где дешевле",
                        "Разница max-min",
                        "Найдено магазинов",
                        "Статус",
                    ]
                )
                writer.writerow(
                    [
                        "iPhone 17 Pro 256GB Silver",
                        "118900",
                        "",
                        "115990",
                        "",
                        "114490",
                        "114490",
                        "Хатико",
                        "4410",
                        "3",
                        "ok",
                    ]
                )

            values = build_comparison_sheet_values(comparison_path, source_path)

            self.assertEqual(values[0][0], "Модель")
            self.assertEqual(values[0][2], "Моя цена")
            self.assertEqual(values[1][0], "iPhone 17 Pro 256GB Silver")
            self.assertEqual(values[1][1], "17 pro 256 silver sim")
            self.assertEqual(values[1][2], 121000)
            self.assertEqual(values[1][3], 118900)
            self.assertEqual(values[1][6], "")
            self.assertEqual(values[1][7], 114490)
            self.assertEqual(values[1][11], 6510)
            self.assertEqual(values[1][12], "да")

    def test_build_catalog_sheet_values_uses_human_readable_columns(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            source_path = Path(tmp_dir) / "devices.csv"
            source_path.write_text(
                "\n".join(
                    [
                        "key,label,url,my_price,site,enabled",
                        "iphone-17-256-black-esim,iPhone 17 256GB Black,https://ilabstore.ru/catalog/iphone/iphone-17/iphone-17-256gb-black-esim/,99990,ilabstore,false",
                    ]
                ),
                encoding="utf-8",
            )

            values = build_catalog_sheet_values(source_path)

            self.assertEqual(values[0], ["Ключ", "Модель", "Запрос", "Моя цена", "Линейка", "Память", "Цвет", "SIM", "Источник", "URL"])
            self.assertEqual(values[1][0], "iphone-17-256-black-esim")
            self.assertEqual(values[1][1], "iPhone 17 256GB Black")
            self.assertEqual(values[1][2], "17 256 black esim")
            self.assertEqual(values[1][3], 99990)
            self.assertEqual(values[1][7], "eSIM")

    def test_build_spreadsheet_url(self):
        self.assertEqual(
            build_spreadsheet_url("abc123"),
            "https://docs.google.com/spreadsheets/d/abc123/edit",
        )

    def test_build_column_segments_skips_manual_retail_column(self):
        self.assertEqual(_build_column_segments(10, preserve_columns=(2,)), [(1, 1), (3, 10)])

    def test_sort_template_values_keeps_existing_sheet_order(self):
        values = [
            ["iPhone 17 256GB Black", "", 74990],
            ["iPhone 16 Pro Max 256GB Black", "", 111900],
            ["iPhone 15 128 Blue", "", 53990],
        ]

        sorted_values = _sort_template_values(
            values,
            preferred_labels=[
                "iPhone 15 128 Blue",
                "iPhone 17 256GB Black",
            ],
        )

        self.assertEqual(
            [row[0] for row in sorted_values],
            [
                "iPhone 15 128 Blue",
                "iPhone 17 256GB Black",
                "iPhone 16 Pro Max 256GB Black",
            ],
        )

    def test_build_runtime_source_catalog_rows_uses_sheet_rows_and_fallback_metadata(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            source_path = Path(tmp_dir) / "devices.csv"
            source_path.write_text(
                "\n".join(
                    [
                        "key,label,url,my_price,site,enabled",
                        "iphone-17-pro-256-silver,iPhone 17 Pro 256GB Silver,https://ilab.example/item,121000,ilabstore,false",
                    ]
                ),
                encoding="utf-8",
            )

            rows = build_runtime_source_catalog_rows(
                [
                    ["iPhone 17 Pro 256GB Silver", 123456],
                    ["PlayStation Portal", ""],
                ],
                load_supported_devices(source_path),
            )

            self.assertEqual(rows[0]["label"], "iPhone 17 Pro 256GB Silver")
            self.assertEqual(rows[0]["my_price"], 123456)
            self.assertEqual(rows[0]["url"], "https://ilab.example/item")
            self.assertEqual(rows[0]["store_urls_json"], "")
            self.assertEqual(rows[1]["label"], "PlayStation Portal")
            self.assertEqual(rows[1]["site"], "")
            self.assertEqual(rows[1]["enabled"], "true")
            self.assertEqual(rows[1]["store_urls_json"], "")

    def test_build_runtime_source_catalog_rows_reads_store_links_from_template_row(self):
        rows = build_runtime_source_catalog_rows(
            [
                [
                    "iPhone 17 Pro 256GB Silver",
                    123456,
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    '=HYPERLINK("https://ilabstore.ru/catalog/test-item/";"ссылка")',
                    "",
                    "",
                    "",
                    "https://i-lite.ru/test-item",
                ],
            ],
            [],
        )

        self.assertIn('"iLab": "https://ilabstore.ru/catalog/test-item/"', rows[0]["store_urls_json"])
        self.assertIn('"I LITE": "https://i-lite.ru/test-item"', rows[0]["store_urls_json"])

    def test_build_runtime_source_catalog_rows_reassigns_mismatched_store_domain(self):
        rows = build_runtime_source_catalog_rows(
            [
                [
                    "iPhone 13 128 Blue",
                    43990,
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    '=HYPERLINK("https://hatiko.ru/product/smartfon_apple_iphone_13_128gb_siniy/";"ссылка")',
                    "",
                    "",
                    "",
                ],
            ],
            [],
        )

        self.assertNotIn('"RE:premium"', rows[0]["store_urls_json"])
        self.assertIn('"Хатико": "https://hatiko.ru/product/smartfon_apple_iphone_13_128gb_siniy/"', rows[0]["store_urls_json"])

    def test_build_runtime_source_catalog_rows_from_catalog_sheet_uses_human_headers(self):
        rows = build_runtime_source_catalog_rows_from_catalog_sheet(
            [
                ["Ключ", "Модель", "Запрос", "Моя цена", "Линейка", "Память", "Цвет", "SIM", "Источник", "URL"],
                ["iphone-17-256-black-esim", "iPhone 17 256GB Black", "17 256 black esim", "99990", "", "", "", "", "ilabstore", "https://ilabstore.ru/catalog/iphone-17-256gb-black-esim/"],
                ["", "PlayStation Portal", "playstation portal", "", "", "", "", "", "kingstore_saratov", "https://saratov.kingstore.io/catalog/playstation-portal/"],
            ]
        )

        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["key"], "iphone-17-256-black-esim")
        self.assertEqual(rows[0]["label"], "iPhone 17 256GB Black")
        self.assertEqual(rows[0]["my_price"], 99990)
        self.assertEqual(rows[1]["key"], "playstation-portal")
        self.assertEqual(rows[1]["enabled"], "true")


if __name__ == "__main__":
    unittest.main()
