import unittest

from competitor_price_monitor.extractor import extract_product
from competitor_price_monitor.models import FieldSelector, SiteConfig


HTML = """
<html>
  <body>
    <h1>iPhone 17 256GB Black</h1>
    <div class="price">109 990 ₽</div>
    <div class="old-price">114 990 ₽</div>
    <div class="availability">В наличии</div>
  </body>
</html>
"""


class ExtractorTests(unittest.TestCase):
    def test_extract_product_details(self):
        site = SiteConfig(
            key="demo",
            selectors={
                "title": FieldSelector(selectors=["h1"], required=True),
                "price": FieldSelector(selectors=[".price"], required=True),
                "original_price": FieldSelector(selectors=[".old-price"]),
                "availability": FieldSelector(selectors=[".availability"]),
            },
            in_stock_patterns=["в наличии"],
            out_of_stock_patterns=["нет в наличии"],
        )

        result = extract_product(HTML, site)

        self.assertEqual(result.title, "iPhone 17 256GB Black")
        self.assertEqual(result.price, 109990)
        self.assertEqual(result.original_price, 114990)
        self.assertEqual(result.availability_status, "in_stock")
        self.assertEqual(result.missing_required_fields, [])

    def test_marks_missing_required_price(self):
        site = SiteConfig(
            key="demo",
            selectors={
                "title": FieldSelector(selectors=["h1"], required=True),
                "price": FieldSelector(selectors=[".missing"], required=True),
            },
        )

        result = extract_product("<h1>AirTag</h1>", site)

        self.assertIn("price", result.missing_required_fields)

    def test_optional_fields_do_not_mark_record_incomplete(self):
        site = SiteConfig(
            key="demo",
            selectors={
                "title": FieldSelector(selectors=["h1"], required=False),
                "price": FieldSelector(selectors=[".missing"], required=False),
            },
        )

        result = extract_product("<h1>AirTag</h1>", site)

        self.assertEqual(result.title, "AirTag")
        self.assertEqual(result.missing_required_fields, [])
        self.assertTrue(result.is_complete())

    def test_availability_patterns_are_case_insensitive(self):
        site = SiteConfig(
            key="demo",
            selectors={
                "title": FieldSelector(selectors=["h1"], required=True),
                "price": FieldSelector(selectors=[".price"], required=True),
                "availability": FieldSelector(selectors=[".availability"]),
            },
            in_stock_patterns=["В НАЛИЧИИ"],
            out_of_stock_patterns=["НЕТ В НАЛИЧИИ"],
        )

        result = extract_product(
            "<h1>AirTag</h1><div class='price'>9990</div><div class='availability'>в наличии</div>",
            site,
        )

        self.assertEqual(result.availability_status, "in_stock")


if __name__ == "__main__":
    unittest.main()
