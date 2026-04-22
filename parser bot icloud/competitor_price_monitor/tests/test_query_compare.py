import unittest
from unittest.mock import patch

from competitor_price_monitor.query_compare import (
    GenericQuery,
    ModelQuery,
    build_generic_search_phrases,
    build_jobscalling_candidate_urls,
    detect_generic_category,
    fetch_store_match_by_url,
    filter_catalog_urls_for_generic_category,
    parse_generic_query,
    parse_model_query,
    score_generic_candidate,
    store_supports_generic_query,
    GENERIC_STORE_SOURCES,
    fetch_hatiko_product,
    fetch_kingstore_product,
    fetch_repremium_product,
    url_matches_store_domain,
)


class QueryCompareTests(unittest.TestCase):
    def test_parse_text_query_with_sim(self):
        query = parse_model_query("сравни сайты саратов по ценам на 17 pro 256 silver 1sim")
        self.assertEqual(
            query,
            ModelQuery(model="17 pro", storage="256gb", color="silver", esim=False),
        )

    def test_parse_text_query_with_esim(self):
        query = parse_model_query("17 pro max 512 deep blue esim")
        self.assertEqual(
            query,
            ModelQuery(model="17 pro max", storage="512gb", color="deep blue", esim=True),
        )

    def test_parse_ilab_label(self):
        query = parse_model_query("iPhone 17 Pro 256GB Silver")
        self.assertEqual(
            query,
            ModelQuery(model="17 pro", storage="256gb", color="silver", esim=None),
        )

    def test_parse_kingstore_label_with_esim_plus_sim(self):
        query = parse_model_query("Смартфон Apple iPhone 17 Pro (eSim+Sim) 256gb Silver")
        self.assertEqual(
            query,
            ModelQuery(model="17 pro", storage="256gb", color="silver", esim=False),
        )

    def test_parse_dual_label_with_nano_sim_and_esim(self):
        query = parse_model_query(
            "Смартфон Apple iPhone 17 Pro 256GB Silver nano SIM + eSIM (Без RuStore)"
        )
        self.assertEqual(
            query,
            ModelQuery(model="17 pro", storage="256gb", color="silver", esim=False),
        )

    def test_parse_russian_color_label_from_ilite(self):
        query = parse_model_query("Apple iPhone 13, 128 ГБ, синий")
        self.assertEqual(
            query,
            ModelQuery(model="13", storage="128gb", color="blue", esim=None),
        )

    def test_parse_pro_model_is_not_downgraded_to_base_model(self):
        query = parse_model_query("Смартфон Apple iPhone 15 Pro 128GB black titanium")
        self.assertEqual(
            query,
            ModelQuery(model="15 pro", storage="128gb", color="black", esim=None),
        )

    def test_parse_hatiko_silver_title_keeps_marketing_color(self):
        query = parse_model_query("Смартфон Apple iPhone 17 Pro 256GB Белый (Silver) nano SIM + eSIM")
        self.assertEqual(
            query,
            ModelQuery(model="17 pro", storage="256gb", color="silver", esim=False),
        )

    def test_parse_hatiko_lavender_title_maps_from_purple(self):
        query = parse_model_query("Смартфон Apple iPhone 17 256GB Фиолетовый (Lavender) eSim")
        self.assertEqual(
            query,
            ModelQuery(model="17", storage="256gb", color="lavender", esim=True),
        )

    def test_parse_hatiko_dualsim_title_marks_sim_variant(self):
        query = parse_model_query("Смартфон Apple iPhone 17 Pro Max 256GB Silver DualSim")
        self.assertEqual(
            query,
            ModelQuery(model="17 pro max", storage="256gb", color="silver", esim=False),
        )

    def test_jobscalling_candidates_include_russian_color_slug(self):
        query = ModelQuery(model="15", storage="128gb", color="black", esim=None)
        urls = build_jobscalling_candidate_urls(query)
        self.assertIn(
            "https://jobscalling.store/smartfony/apple-iphone-15-128gb-chernyy-black-novyy/",
            urls,
        )

    def test_parse_generic_query_for_macbook(self):
        query = parse_generic_query("Apple MacBook Air 13 M4 16/256GB")
        self.assertEqual(
            query,
            GenericQuery(
                raw_text="Apple MacBook Air 13 M4 16/256GB",
                normalized_text="apple macbook air 13 m4 16gb 256gb",
                tokens=("macbook", "air", "13", "m4", "16gb", "256gb"),
            ),
        )

    def test_score_generic_candidate_matches_macbook_variant(self):
        query = parse_generic_query("Apple MacBook Air 13 M4 16/256GB")
        score = score_generic_candidate(query, "MacBook Air 13 M4 16Gb RAM 256Gb Midnight 2025")
        self.assertGreaterEqual(score, 1.0)

    def test_parse_generic_query_normalizes_iceblue_color(self):
        query = parse_generic_query("Samsung Galaxy S25 12/256GB IceBlue")
        self.assertEqual(
            query,
            GenericQuery(
                raw_text="Samsung Galaxy S25 12/256GB IceBlue",
                normalized_text="samsung galaxy s25 12gb 256gb ice blue",
                tokens=("galaxy", "s25", "12gb", "256gb", "ice", "blue"),
            ),
        )

    def test_score_generic_candidate_does_not_require_year_token(self):
        query = parse_generic_query("Apple iPad 11 2025 128GB Wi-Fi Pink")
        score = score_generic_candidate(query, "Apple iPad 11 128GB Wi-Fi Pink")
        self.assertGreaterEqual(score, 0.8)

    def test_score_generic_candidate_understands_russian_color_title(self):
        query = parse_generic_query("Samsung Galaxy A56 5G 8/128GB Light Grey")
        score = score_generic_candidate(query, "Смартфон Samsung Galaxy A56 8/128 ГБ Светло-серый")
        self.assertGreaterEqual(score, 0.8)

    def test_score_generic_candidate_for_samsung_allows_missing_ram_token(self):
        query = parse_generic_query("Samsung Galaxy S25 12/256GB IceBlue")
        score = score_generic_candidate(query, "Смартфон Samsung Galaxy S25 256 ГБ Icy Blue")
        self.assertGreaterEqual(score, 0.7)

    def test_build_generic_search_phrases_includes_normalized_portal_query(self):
        query = parse_generic_query("PlayStation Portal черный")
        phrases = build_generic_search_phrases(query)
        self.assertIn("playstation portal black", phrases)
        self.assertIn("playstation portal", phrases)

    def test_build_generic_search_phrases_keep_brand_for_samsung(self):
        query = parse_generic_query("Samsung Galaxy S25 12/256GB IceBlue")
        phrases = build_generic_search_phrases(query)
        self.assertIn("samsung galaxy s25 256 ice blue", phrases)
        self.assertIn("samsung galaxy s25 256", phrases)

    def test_build_generic_search_phrases_drop_optional_network_token(self):
        query = parse_generic_query("Samsung Galaxy A56 5G 8/128GB Light Grey")
        phrases = build_generic_search_phrases(query)
        self.assertIn("samsung galaxy a56 128", phrases)

    def test_build_generic_search_phrases_drop_secondary_storage_token_for_macbook(self):
        query = parse_generic_query("Apple MacBook Air 13 M4 16/256GB Sky Blue")
        phrases = build_generic_search_phrases(query)
        self.assertIn("apple macbook air 13 m4 256gb sky blue", phrases)
        self.assertIn("apple macbook air 13 m4 256gb", phrases)

    def test_build_generic_search_phrases_for_controller_adds_dualsense(self):
        query = parse_generic_query("Джойстик Sony PlayStation 5 White")
        phrases = build_generic_search_phrases(query)
        self.assertIn("dualsense playstation 5 white", phrases)

    def test_score_generic_candidate_rejects_extra_model_variant(self):
        query = parse_generic_query("Samsung Galaxy S25 12/256GB IceBlue")
        score = score_generic_candidate(query, "Смартфон Samsung Galaxy S25 FE 256 ГБ Icy Blue")
        self.assertEqual(score, 0.0)

    def test_detect_generic_category_for_playstation(self):
        query = parse_generic_query("PlayStation PS5 1TB с дисководом SLIM")
        self.assertEqual(detect_generic_category(query), "playstation")

    def test_store_supports_generic_query_skips_ilab_for_samsung(self):
        source = next(item for item in GENERIC_STORE_SOURCES if item.key == "ilabstore")
        query = parse_generic_query("Samsung Galaxy S25 12/256GB")
        self.assertFalse(store_supports_generic_query(source, query))

    def test_store_supports_generic_query_keeps_ilab_for_macbook(self):
        source = next(item for item in GENERIC_STORE_SOURCES if item.key == "ilabstore")
        query = parse_generic_query("Apple MacBook Air 13 M4 16/256GB")
        self.assertTrue(store_supports_generic_query(source, query))

    def test_filter_catalog_urls_for_generic_category_prefers_ipad_paths(self):
        query = parse_generic_query("Apple iPad Air 11 2025 M3 128GB Wi-Fi Blue")
        urls = [
            "https://ilabstore.ru/catalog/macbook/macbook-air-13-m4-2025/",
            "https://ilabstore.ru/catalog/ipad/ipad-air-11-2025/",
        ]
        self.assertEqual(
            filter_catalog_urls_for_generic_category(urls, query),
            ["https://ilabstore.ru/catalog/ipad/ipad-air-11-2025/"],
        )

    def test_fetch_store_match_by_url_returns_none_on_timeout(self):
        with patch(
            "competitor_price_monitor.query_compare.get_direct_product_fetchers",
            return_value={"I LITE": ("ilite", lambda url: (_ for _ in ()).throw(TimeoutError("boom")))},
        ):
            self.assertIsNone(fetch_store_match_by_url("I LITE", "https://i-lite.ru/item"))

    def test_fetch_store_match_by_url_returns_none_on_domain_mismatch(self):
        with patch(
            "competitor_price_monitor.query_compare.get_direct_product_fetchers",
            return_value={"SOTOViK": ("sotovik_saratov", lambda url: {"price": 43490})},
        ):
            self.assertIsNone(
                fetch_store_match_by_url(
                    "SOTOViK",
                    "https://hatiko.ru/product/smartfon_apple_iphone_13_128gb_siniy/",
                )
            )

    def test_fetch_store_match_by_url_returns_none_when_current_price_missing(self):
        with patch(
            "competitor_price_monitor.query_compare.get_direct_product_fetchers",
            return_value={
                "Хатико": (
                    "hatiko",
                    lambda url: {"name": "iPhone 13", "price": None, "old_price": 52390},
                )
            },
        ):
            self.assertIsNone(fetch_store_match_by_url("Хатико", "https://hatiko.ru/product/item"))

    def test_fetch_kingstore_product_parses_new_price_markup(self):
        html = """
        <html><body>
        <h1>Смартфон Apple iPhone 16 128gb Black</h1>
        <div class="page-product-card-info-price-and-buttons__price">
            59 990 ₽
        </div>
        <a href="#" class="index-products-body-item__button-title product-page-main-info-button-to-basket btn btn-black">Купить</a>
        </body></html>
        """
        with patch("competitor_price_monitor.query_compare.fetch_html", return_value=html):
            details = fetch_kingstore_product("https://saratov.kingstore.io/catalog/test")

        self.assertEqual(details["price"], 59990)
        self.assertEqual(details["availability_status"], "in_stock")

    def test_url_matches_store_domain_accepts_sotovik_subdomains(self):
        self.assertTrue(
            url_matches_store_domain(
                "SOTOViK",
                "https://spb.sotovik.shop/catalog/kompyutery/apple_macbook_1/macbook_air_1/13871/",
            )
        )

    def test_url_matches_store_domain_accepts_repremium_subdomains(self):
        self.assertTrue(
            url_matches_store_domain(
                "RE:premium",
                "https://sar.stores-apple.com/catalog/macbook-air-13-m4-16-256/",
            )
        )

    def test_url_matches_store_domain_accepts_repremium_ru(self):
        self.assertTrue(
            url_matches_store_domain(
                "RE:premium",
                "https://repremium.ru/catalog/smartfon_apple_iphone_17_air_512_gb_belyy/",
            )
        )

    def test_fetch_repremium_product_prefers_regular_price_over_conditional_sale(self):
        html = """
        <html><body>
        <h1 itemprop="name">Ноутбук Apple MacBook Air 13 M4 16/256, Sky Blue</h1>
        <div class="price_matrix_wrapper ">
            <div class="price font-bold font_mxs" data-currency="RUB" data-value="106990">
                <span class="values_wrapper">
                    <div class="list_catalog_price_old"><span class="price_value old">126 990</span><span class="price_currency"> ₽</span></div>
                    <div class="price_value_sale" title="Цена действительна при покупке гарантии"><span>99 990<span class="price_currency"> ₽</span></span></div>
                    <span class="price_value">106 990</span><span class="price_currency"> ₽</span>
                </span>
            </div>
        </div>
        <div itemprop="offers" itemscope itemtype="http://schema.org/Offer">
            <meta itemprop="price" content="106990" />
            <link itemprop="availability" href="http://schema.org/InStock" />
        </div>
        </body></html>
        """
        with patch("competitor_price_monitor.query_compare.fetch_html", return_value=html):
            details = fetch_repremium_product("https://sar.stores-apple.com/catalog/test-item/")

        self.assertEqual(details["price"], 106990)
        self.assertEqual(details["old_price"], 126990)
        self.assertEqual(details["availability_status"], "in_stock")
        self.assertEqual(details["availability_text"], "В наличии")

    def test_fetch_repremium_product_parses_repremium_ru_markup(self):
        html = """
        <html><body>
        <h1>Смартфон Apple iPhone Air 512 ГБ белый</h1>
        <div class="product-price2">
            <div class="product-price2-base">
                <div class="product-price2__value">
                    112 890 ₽
                </div>
            </div>
            <div class="product-price2-old">
                <div class="product-price2__value">
                    119 990 ₽
                </div>
            </div>
        </div>
        <div class="product2-to-cart-container">
            <button class="button button_linear-red product2__to-cart to_cart detail_to_cart" type="button">
                <span class="product2__to-cart-text">Добавить в корзину</span>
            </button>
        </div>
        </body></html>
        """
        with patch("competitor_price_monitor.query_compare.fetch_html", return_value=html):
            details = fetch_repremium_product("https://repremium.ru/catalog/smartfon_apple_iphone_17_air_512_gb_belyy/")

        self.assertEqual(details["price"], 112890)
        self.assertEqual(details["old_price"], 119990)
        self.assertEqual(details["availability_status"], "in_stock")
        self.assertEqual(details["availability_text"], "Добавить в корзину")

    def test_fetch_hatiko_product_can_parse_plain_html_without_playwright(self):
        html = """
        <html><body>
        <h1>Смартфон Apple iPhone 17 Pro 256GB Белый (Silver)</h1>
        <span class="price">114 490</span>
        <span class="price">118 990</span>
        <div>Есть в наличии</div>
        </body></html>
        """
        with patch("competitor_price_monitor.query_compare.try_fetch_html", return_value=html):
            details = fetch_hatiko_product("https://hatiko.ru/product/test-item")

        self.assertEqual(details["price"], 114490)
        self.assertEqual(details["old_price"], 118990)
        self.assertEqual(details["availability_status"], "in_stock")


if __name__ == "__main__":
    unittest.main()
