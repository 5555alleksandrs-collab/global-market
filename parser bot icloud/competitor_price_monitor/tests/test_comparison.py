import unittest

from competitor_price_monitor.comparison import calculate_price_diff, choose_cheaper_side


class ComparisonTests(unittest.TestCase):
    def test_calculate_price_diff(self):
        self.assertEqual(calculate_price_diff(99990, 104990), -5000)

    def test_choose_cheaper_side_competitor(self):
        cheaper_side, competitor_cheaper = choose_cheaper_side(99990, 104990)
        self.assertEqual(cheaper_side, "competitor")
        self.assertTrue(competitor_cheaper)

    def test_choose_cheaper_side_equal(self):
        cheaper_side, competitor_cheaper = choose_cheaper_side(99990, 99990)
        self.assertEqual(cheaper_side, "equal")
        self.assertFalse(competitor_cheaper)


if __name__ == "__main__":
    unittest.main()
