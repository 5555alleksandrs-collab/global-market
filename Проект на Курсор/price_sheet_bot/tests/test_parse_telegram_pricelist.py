"""Регрессия: qty «100+», дедуп ключей (последняя цена)."""

import unittest

import config

from parse_telegram_pricelist import (
    _dedupe_product_prices_last_wins,
    _parse_color_qty_tail_price_line,
    _region_from_text_section_header,
    parse_telegram_pricelist,
)


class TestColorQtyTail(unittest.TestCase):
    def test_plain_qty_and_price(self):
        r = _parse_color_qty_tail_price_line("Orange 50 Kr 🇰🇷 1580")
        self.assertIsNotNone(r)
        self.assertEqual(r[0].lower(), "orange")
        self.assertEqual(r[1], 1580.0)

    def test_qty_100_plus_usa_dollar(self):
        r = _parse_color_qty_tail_price_line("Blue 100+ usa $1172")
        self.assertIsNotNone(r)
        self.assertEqual(r[0].lower(), "blue")
        self.assertEqual(r[1], 1172.0)

    def test_strips_coming_suffix(self):
        r = _parse_color_qty_tail_price_line("Blue 12 Aus $1580 coming")
        self.assertIsNotNone(r)
        self.assertEqual(r[1], 1580.0)


class TestDedupe(unittest.TestCase):
    def test_last_price_wins(self):
        pairs = [
            ("iphone 17 pro blue esim", 100.0),
            ("iphone 17 pro blue esim", 200.0),
        ]
        out = _dedupe_product_prices_last_wins(pairs)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0][1], 200.0)


class TestSimEsimSectionHeaders(unittest.TestCase):
    def test_banner_keywords(self):
        self.assertEqual(
            _region_from_text_section_header("ESIM"), config.REGION_SUFFIX_JP
        )
        self.assertEqual(_region_from_text_section_header("SIM"), config.REGION_SUFFIX_GB)
        self.assertEqual(
            _region_from_text_section_header("--- SIM ---"), config.REGION_SUFFIX_GB
        )
        self.assertIsNone(_region_from_text_section_header("SIM free"))

    def test_e_dash_sim_and_1_sim_headers(self):
        """Как в прайсе BB: «JAPAN ,USA E - SIM» и «UK … 1-SIM»."""
        self.assertEqual(
            _region_from_text_section_header("JAPAN ,USA E - SIM"),
            config.REGION_SUFFIX_JP,
        )
        self.assertEqual(
            _region_from_text_section_header("UK , KR , HK 1-SIM"),
            config.REGION_SUFFIX_GB,
        )

    def test_parse_switches_region(self):
        text = """IPHONE 17 256GB $700
SIM
Orange=60 $800
ESIM
Lavender=60 $900
"""
        pairs = dict(parse_telegram_pricelist(text))
        self.assertEqual(pairs["17 256gb orange sim"], 800.0)
        self.assertEqual(pairs["17 256gb lavender esim"], 900.0)

    def test_bb_style_two_blocks_no_overwrite(self):
        text = """JAPAN ,USA E - SIM
IPHONE 17 256GB $735
Black=40
=============
UK , KR , HK 1-SIM
IPHONE 17 256GB $780
Black=100+
"""
        pairs = dict(parse_telegram_pricelist(text))
        self.assertEqual(pairs["17 256gb black esim"], 735.0)
        self.assertEqual(pairs["17 256gb black sim"], 780.0)


if __name__ == "__main__":
    unittest.main()
