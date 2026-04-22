from __future__ import annotations

import argparse
import csv
import logging
import re
import socket
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import suppress
from dataclasses import dataclass
from functools import lru_cache
from html import unescape
from pathlib import Path
from threading import Lock
from typing import Callable, Dict, Iterable, List, Optional, Sequence, Tuple
from urllib.error import HTTPError, URLError
from urllib.parse import quote_plus, urljoin, urlparse
from urllib.request import Request, urlopen


logger = logging.getLogger(__name__)

USER_AGENT = "Mozilla/5.0"
HTML_FETCH_TIMEOUT_SECONDS = 10
HATIKO_NAVIGATION_TIMEOUT_MS = 10000
HATIKO_SELECTOR_TIMEOUT_MS = 4000
HATIKO_BODY_TIMEOUT_MS = 3000
HATIKO_CONTENT_WAIT_TIMEOUT_MS = 6000
HATIKO_PLAYWRIGHT_LOCK = Lock()
ILAB_CSV = Path(__file__).resolve().parent / "config" / "products.ilab_template.csv"
ILITE_CATEGORY_BY_MODEL: Dict[Tuple[str, Optional[bool]], str] = {
    ("13", False): "https://i-lite.ru/category/_products/iphone/iphone-13/",
    ("15", False): "https://i-lite.ru/category/_products/iphone/iphone-15/",
    ("16", False): "https://i-lite.ru/category/_products/iphone/iphone-16/",
    ("16 plus", False): "https://i-lite.ru/category/_products/iphone/iphone-16-plus/",
    ("16e", False): "https://i-lite.ru/category/_products/iphone/iphone-16e/",
    ("16 pro max", False): "https://i-lite.ru/category/_products/iphone/iphone-16-pro-max/",
    ("16 pro max", True): "https://i-lite.ru/category/_products/iphone/iphone-16-pro-max-esim-esim/",
    ("17", False): "https://i-lite.ru/category/_products/iphone/iphone-17/",
    ("17", True): "https://i-lite.ru/category/_products/iphone/iphone-17-esim-esim/",
    ("17 air", False): "https://i-lite.ru/category/_products/iphone/iphone-air/",
    ("17e", False): "https://i-lite.ru/category/_products/iphone/iphone-17e/",
    ("17e", True): "https://i-lite.ru/category/_products/iphone/iphone-17e-esim-esim/",
    ("17 pro", False): "https://i-lite.ru/category/_products/iphone/iphone-17-pro/",
    ("17 pro", True): "https://i-lite.ru/category/_products/iphone/iphone-17-pro-esim-esim/",
    ("17 pro max", False): "https://i-lite.ru/category/_products/iphone/iphone-17-pro-max/",
    ("17 pro max", True): "https://i-lite.ru/category/_products/iphone/iphone-17-pro-max-esim-esim/",
}
HATIKO_CATEGORY_BY_MODEL: Dict[str, str] = {
    "13": "https://hatiko.ru/category/iphone_13/",
    "14": "https://hatiko.ru/category/iphone-14/",
    "14 plus": "https://hatiko.ru/category/iphone-14-plus/",
    "15": "https://hatiko.ru/category/iphone-15/",
    "15 plus": "https://hatiko.ru/category/iphone-15-plus/",
    "16": "https://hatiko.ru/category/iphone-16/",
    "16 plus": "https://hatiko.ru/category/iphone-16-plus/",
    "16e": "https://hatiko.ru/category/iphone-16e/",
    "16 pro": "https://hatiko.ru/category/iphone-16-pro/",
    "16 pro max": "https://hatiko.ru/category/iphone-16-pro-max/",
    "17": "https://hatiko.ru/category/iphone-17-ms2/",
    "17 air": "https://hatiko.ru/category/iphone-17-air-ms2/",
    "17e": "https://hatiko.ru/category/iphone-17e/",
    "17 pro": "https://hatiko.ru/category/iphone-17-pro-ms1/",
    "17 pro max": "https://hatiko.ru/category/iphone-17-pro-max-ms2/",
}
KINGSTORE_CATEGORY_BY_MODEL: Dict[str, str] = {
    "13": "https://saratov.kingstore.io/catalog/iphone/iphone-13/",
    "14": "https://saratov.kingstore.io/catalog/iphone/iphone-14/",
    "15": "https://saratov.kingstore.io/catalog/iphone/iphone-15/",
    "15 plus": "https://saratov.kingstore.io/catalog/iphone/iphone-15-plus/",
    "16": "https://saratov.kingstore.io/catalog/iphone/iphone-16/",
    "16 plus": "https://saratov.kingstore.io/catalog/iphone/iphone-16-plus/",
    "16e": "https://saratov.kingstore.io/catalog/iphone/iphone-16e/",
    "16 pro": "https://saratov.kingstore.io/catalog/iphone/iphone-16-pro/",
    "16 pro max": "https://saratov.kingstore.io/catalog/iphone/iphone-16-pro-max/",
    "17": "https://saratov.kingstore.io/catalog/iphone/iphone-17/",
    "17 air": "https://saratov.kingstore.io/catalog/iphone/iphone-air/",
    "17e": "https://saratov.kingstore.io/catalog/iphone/iphone-17e/",
    "17 pro": "https://saratov.kingstore.io/catalog/iphone/iphone-17-pro/",
    "17 pro max": "https://saratov.kingstore.io/catalog/iphone/iphone-17-pro-max/",
}
JOBSCALLING_MODEL_SLUGS = {
    "13": "13",
    "14": "14",
    "15": "15",
    "15 plus": "15-plus",
    "16": "16",
    "16 plus": "16-plus",
    "16e": "16e",
    "16 pro": "16-pro",
    "16 pro max": "16-pro-max",
    "17": "17",
    "17 air": "17-air",
    "17e": "17e",
    "17 pro": "17-pro",
    "17 pro max": "17-pro-max",
}
DIRECT_URL_HOSTS_BY_STORE_NAME: Dict[str, Tuple[str, ...]] = {
    "iLab": ("ilabstore.ru",),
    "I LITE": ("i-lite.ru",),
    "KingStore Saratov": ("saratov.kingstore.io",),
    "RE:premium": ("stores-apple.com", "repremium.ru"),
    "SOTOViK": ("sotovik.shop",),
    "Хатико": ("hatiko.ru",),
}
NOBEL_CATEGORY_BY_MODEL: Dict[str, str] = {
    "13": "https://xn--80aag1ciek.xn--90aisff1g.xn--p1ai/catalog/smartfony/apple/iphone-13/",
    "15": "https://xn--80aag1ciek.xn--90aisff1g.xn--p1ai/catalog/smartfony/apple/iphone-15/",
    "15 plus": "https://xn--80aag1ciek.xn--90aisff1g.xn--p1ai/catalog/smartfony/apple/iphone-15-plus/",
    "16": "https://xn--80aag1ciek.xn--90aisff1g.xn--p1ai/catalog/smartfony/apple/iphone-16/",
    "16 plus": "https://xn--80aag1ciek.xn--90aisff1g.xn--p1ai/catalog/smartfony/apple/iphone-16-plus/",
    "16e": "https://xn--80aag1ciek.xn--90aisff1g.xn--p1ai/catalog/smartfony/apple/iphone-16e/",
    "16 pro": "https://xn--80aag1ciek.xn--90aisff1g.xn--p1ai/catalog/smartfony/apple/iphone-16-pro/",
    "16 pro max": "https://xn--80aag1ciek.xn--90aisff1g.xn--p1ai/catalog/smartfony/apple/iphone-16-pro-max-2sim/",
    "17": "https://xn--80aag1ciek.xn--90aisff1g.xn--p1ai/catalog/smartfony/apple/iphone-17/",
    "17 air": "https://xn--80aag1ciek.xn--90aisff1g.xn--p1ai/catalog/smartfony/apple/iphone-air/",
    "17 pro": "https://xn--80aag1ciek.xn--90aisff1g.xn--p1ai/catalog/smartfony/apple/iphone-17-pro/",
    "17 pro max": "https://xn--80aag1ciek.xn--90aisff1g.xn--p1ai/catalog/smartfony/apple/iphone-17-pro-max/",
}
COLOR_ALIASES = {
    "cosmic orange": "orange",
    "soft pink": "pink",
    "natural titanium": "natural",
    "desert titanium": "desert",
    "black titanium": "black",
    "white titanium": "white",
    "синий": "blue",
    "голубой": "blue",
    "серый": "gray",
    "серый космос": "space gray",
    "серый космический": "space gray",
    "космический серый": "space gray",
    "светло-серый": "light gray",
    "светло серый": "light gray",
    "светлый серый": "light gray",
    "зеленый": "green",
    "зелёный": "green",
    "оливковый": "olive",
    "олива": "olive",
    "мятный": "mint",
    "мята": "mint",
    "розовый": "pink",
    "черный": "black",
    "чёрный": "black",
    "белый": "white",
    "серебристый": "silver",
    "серебряный": "silver",
    "серебряная тень": "silver shadow",
    "графит": "graphite",
    "графитовый": "graphite",
    "оранжевый": "orange",
    "фиолетовый": "purple",
    "фиолет": "purple",
    "лавандовый": "lavender",
    "шалфейный": "sage",
    "бирюзовый": "teal",
    "ультрамарин": "ultramarine",
    "ультрамариновый": "ultramarine",
    "ледяной синий": "ice blue",
    "ледяной голубой": "ice blue",
    "айс блю": "ice blue",
    "небесный голубой": "sky blue",
    "небесный синий": "sky blue",
    "кобальтовый фиолетовый": "cobalt violet",
    "натуральный титан": "natural",
    "натуральный": "natural",
    "песочный титан": "desert",
    "пустынный титан": "desert",
    "пустынный": "desert",
    "темная ночь": "midnight",
    "тёмная ночь": "midnight",
    "сияющая звезда": "starlight",
    "небесно голубой": "sky blue",
    "небесно-голубой": "sky blue",
    "светлое золото": "light gold",
    "облачный белый": "cloud white",
    "космический черный": "space black",
    "космический чёрный": "space black",
    "глубокий синий": "deep blue",
    "темно-синий": "dark blue",
    "тёмно-синий": "dark blue",
    "светло-голубой": "light blue",
    "светлоголубой": "light blue",
    "полуночный": "midnight",
    "звездный свет": "starlight",
    "звёздный свет": "starlight",
    "золотой": "gold",
    "желтый": "yellow",
    "жёлтый": "yellow",
    "мягкий розовый": "soft pink",
}
MULTI_WORD_COLORS = (
    "deep blue",
    "dark blue",
    "mist blue",
    "light blue",
    "sky blue",
    "light gold",
    "cloud white",
    "space black",
    "soft pink",
    "cosmic orange",
    "natural titanium",
    "desert titanium",
    "black titanium",
    "white titanium",
)
SIMPLE_COLORS = {
    "black",
    "white",
    "blue",
    "green",
    "pink",
    "silver",
    "orange",
    "lavender",
    "sage",
    "teal",
    "ultramarine",
    "midnight",
    "starlight",
    "natural",
    "desert",
    "red",
    "yellow",
    "purple",
    "gold",
}
MODEL_COLOR_CANONICAL_MAP: Dict[str, Dict[str, str]] = {
    "17": {
        "green": "sage",
        "purple": "lavender",
        "light blue": "mist blue",
        "blue": "mist blue",
    },
    "17 air": {
        "blue": "sky blue",
        "white": "cloud white",
        "black": "space black",
        "gold": "light gold",
        "yellow": "light gold",
    },
    "17e": {
        "pink": "soft pink",
    },
    "17 pro": {
        "white": "silver",
        "dark blue": "deep blue",
        "blue": "deep blue",
    },
    "17 pro max": {
        "white": "silver",
        "dark blue": "deep blue",
        "blue": "deep blue",
    },
}
JOBSCALLING_COLOR_SLUGS = {
    "black": ["black", "chernyy-black", "chernyy"],
    "white": ["white", "belyy-white", "belyy"],
    "blue": ["blue", "siniy-blue", "siniy", "goluboy-blue", "goluboy"],
    "green": ["green", "zelenyy-green", "zelenyy"],
    "pink": ["pink", "soft-pink", "rozovyy-pink", "rozovyy"],
    "silver": ["silver"],
    "orange": ["orange", "cosmic-orange"],
    "lavender": ["lavender"],
    "sage": ["sage"],
    "mist blue": ["mist-blue"],
    "deep blue": ["deep-blue"],
    "sky blue": ["sky-blue"],
    "light gold": ["light-gold"],
    "cloud white": ["cloud-white"],
    "space black": ["space-black"],
    "teal": ["teal", "biryuzovyy-teal", "biryuzovyy"],
    "ultramarine": ["ultramarine", "ultramarin-ultramarine", "ultramarin"],
    "midnight": ["midnight", "temnaya-noch-midnight", "tyomnaya-noch-midnight"],
    "starlight": ["starlight", "siyayushchaya-zvezda-starlight", "siyayushchaya-zvezda"],
    "natural": ["natural", "natural-titanium", "naturalnyy-natural", "naturalnyy"],
    "desert": ["desert", "desert-titanium", "pustynnyy-desert", "pustynnyy"],
}
JOBSCALLING_PREFIX_PATTERNS = (
    "smartfon-apple-iphone-{model}-{storage}-{color}-{suffix}/",
    "apple-iphone-{model}-{storage}-{color}-{suffix}/",
    "iphone-{model}-{storage}-{color}-{suffix}/",
)
JOBSCALLING_CONDITION_SUFFIXES = ("novyy",)
STOPWORDS = {
    "сравни",
    "сравнить",
    "сравнение",
    "сайты",
    "сайт",
    "магазины",
    "магазин",
    "техники",
    "техника",
    "саратов",
    "по",
    "ценам",
    "цены",
    "на",
    "и",
    "мне",
    "пришли",
    "пришли-ка",
    "готовый",
    "вариант",
    "iphone",
    "apple",
    "смартфон",
    "гб",
    "tb",
}
GENERIC_STOPWORDS = {
    "смартфон",
    "ноутбук",
    "планшет",
    "apple",
    "sony",
    "samsung",
    "game",
    "console",
    "игровая",
    "игровое",
    "устройство",
    "портативное",
    "купить",
    "новый",
    "new",
    "ram",
    "gb",
    "tb",
    "дюйм",
    "дюйма",
    "inch",
}
GENERIC_TEXT_ALIASES: Sequence[Tuple[str, str]] = (
    ("wi-fi", " wifi "),
    ("wifi", " wifi "),
    ("wi fi", " wifi "),
    ("вай фай", " wifi "),
    ("вай-фай", " wifi "),
    ("cellular", " cellular "),
    ("сотовая связь", " cellular "),
    ("sim free", " "),
    ("iceblue", " ice blue "),
    ("icy blue", " ice blue "),
    ("skyblue", " sky blue "),
    ("blueblack", " blue black "),
    ("pinkgold", " pink gold "),
    ("grey", " gray "),
    ("spacegray", " space gray "),
    ("space grey", " space gray "),
    ("lightgrey", " light gray "),
    ("light grey", " light gray "),
    ("cobaltviolet", " cobalt violet "),
    ("silvershadow", " silver shadow "),
    ("spacegray", " space gray "),
    ("space-grey", " space gray "),
    ("silver-shadow", " silver shadow "),
    ("light-gray", " light gray "),
    ("ice-blue", " ice blue "),
    ("sky-blue", " sky blue "),
    ("cobalt-violet", " cobalt violet "),
    ("play station", " playstation "),
    ("ps5", " playstation 5 "),
    ("с дисководом", " disc "),
    ("с приводом", " disc "),
    ("стандартная версия", " disc "),
    ("standard edition", " disc "),
    ("без дисковода", " digital "),
    ("digital edition", " digital "),
    ("геймпад", " controller "),
    ("контроллер", " controller "),
    ("джойстик", " controller "),
    ("игровая приставка", " playstation "),
    ("портативная приставка", " portal "),
    ("игровой контроллер", " controller "),
    ("dualsense", " dualsense controller playstation 5 "),
    ("портал", " portal "),
)
GENERIC_COLOR_TOKENS = frozenset(
    {
        "black",
        "white",
        "blue",
        "green",
        "pink",
        "silver",
        "shadow",
        "mint",
        "navy",
        "olive",
        "graphite",
        "ice",
        "sky",
        "gray",
        "grey",
        "purple",
        "yellow",
        "starlight",
        "midnight",
        "space",
        "cobalt",
        "violet",
        "light",
        "gold",
        "natural",
        "desert",
        "orange",
        "deep",
        "lavender",
        "sage",
        "mist",
        "cloud",
        "teal",
        "pinkgold",
        "ultramarine",
        "soft",
        "coral",
        "red",
    }
)
GENERIC_VARIANT_GUARD_TOKENS = frozenset(
    {
        "fe",
        "edge",
        "air",
        "mini",
        "plus",
        "pro",
        "max",
        "ultra",
        "slim",
        "digital",
        "disc",
        "portal",
        "cellular",
        "lte",
    }
)
GENERIC_OPTIONAL_SEARCH_TOKENS = frozenset({"5g", "4g", "wifi", "cellular"})
GENERIC_REQUIRED_HINTS = {
    "macbook",
    "ipad",
    "galaxy",
    "playstation",
    "portal",
    "dualsense",
    "controller",
    "wifi",
    "air",
    "mini",
    "slim",
    "digital",
    "disc",
    "ultra",
}
GENERIC_STORE_CATEGORY_SUPPORT: Dict[str, frozenset[str]] = {
    "ilabstore": frozenset({"ipad", "macbook"}),
    "ilite": frozenset({"ipad", "macbook", "playstation", "samsung"}),
    "kingstore_saratov": frozenset({"ipad", "macbook", "playstation", "samsung"}),
    "jobscalling": frozenset({"ipad", "macbook", "playstation", "samsung"}),
    "sotovik_saratov": frozenset({"ipad", "macbook", "playstation", "samsung"}),
    "hatiko": frozenset({"ipad", "macbook", "playstation"}),
    "nobel_saratov": frozenset({"ipad", "macbook"}),
}
SOTOVIK_SEARCH_MAX_PAGES = 3
GENERIC_SOTOVIK_MAX_PAGES = 1
COMPARED_STORE_NAMES = (
    "iLab",
    "I LITE",
    "KingStore Saratov",
    "Хатико",
)
MAX_COMPARE_WORKERS = 4


@dataclass(frozen=True)
class ModelQuery:
    model: str
    storage: str
    color: str
    esim: Optional[bool]

    def display_name(self) -> str:
        suffix = " eSIM" if self.esim is True else " sim" if self.esim is False else ""
        return "iPhone {0} {1} {2}{3}".format(
            self.model.title(),
            self.storage.upper(),
            self.color.title(),
            suffix,
        )


@dataclass(frozen=True)
class GenericQuery:
    raw_text: str
    normalized_text: str
    tokens: Tuple[str, ...]

    def display_name(self) -> str:
        return self.raw_text


@dataclass
class QueryMatch:
    site_key: str
    site_name: str
    name: str
    url: str
    price: Optional[int]
    old_price: Optional[int]
    availability_text: Optional[str]
    availability_status: str
    note: Optional[str] = None


@dataclass(frozen=True)
class StoreSource:
    key: str
    name: str
    finder: Callable[[ModelQuery], Optional[QueryMatch]]


@dataclass(frozen=True)
class GenericStoreSource:
    key: str
    name: str
    finder: Callable[[GenericQuery], Optional[QueryMatch]]


STORE_SOURCES = (
    StoreSource("ilabstore", "iLab", lambda query: find_ilab_match(query)),
    StoreSource("ilite", "I LITE", lambda query: find_ilite_match(query)),
    StoreSource("kingstore_saratov", "KingStore Saratov", lambda query: find_kingstore_match(query)),
    StoreSource("hatiko", "Хатико", lambda query: find_hatiko_match(query)),
)
GENERIC_STORE_SOURCES = (
    GenericStoreSource("ilabstore", "iLab", lambda query: find_ilab_generic_match(query)),
    GenericStoreSource("ilite", "I LITE", lambda query: find_ilite_generic_match(query)),
    GenericStoreSource("kingstore_saratov", "KingStore Saratov", lambda query: find_kingstore_generic_match(query)),
    GenericStoreSource("hatiko", "Хатико", lambda query: find_hatiko_generic_match(query)),
)


def compare_query_text(text: str) -> Tuple[object, List[QueryMatch]]:
    try:
        query = parse_model_query(text)
        matches = compare_model(query)
        return query, matches
    except ValueError:
        generic_query = parse_generic_query(text)
        matches = compare_generic_query(generic_query)
        return generic_query, matches


def fetch_store_match_by_url(site_name: str, url: str) -> Optional[QueryMatch]:
    raw_site_name = str(site_name or "").strip()
    raw_url = str(url or "").strip()
    if not raw_site_name or not raw_url:
        return None
    if not url_matches_store_domain(raw_site_name, raw_url):
        logger.debug(
            "Ignoring direct URL for %s due to domain mismatch: %s",
            raw_site_name,
            raw_url,
        )
        return None

    fetcher_entry = get_direct_product_fetchers().get(raw_site_name)
    if not fetcher_entry:
        return None

    site_key, fetcher = fetcher_entry
    try:
        details = fetcher(raw_url)
    except Exception as error:  # noqa: BLE001
        logger.debug("Failed to fetch direct URL for %s (%s): %s", raw_site_name, raw_url, error)
        return None
    if not details:
        return None
    price = _coalesce_int(details.get("price"))
    if price is None:
        logger.debug(
            "Direct URL for %s returned no current price, falling back to search: %s",
            raw_site_name,
            raw_url,
        )
        return None

    return QueryMatch(
        site_key=site_key,
        site_name=raw_site_name,
        name=str(details.get("name") or ""),
        url=raw_url,
        price=price,
        old_price=_coalesce_int(details.get("old_price")),
        availability_text=details.get("availability_text"),
        availability_status=str(details.get("availability_status") or "unknown"),
        note="Найдено по ссылке из таблицы",
    )


def get_direct_product_fetchers() -> Dict[str, Tuple[str, Callable[[str], Optional[Dict[str, object]]]]]:
    return {
        "iLab": ("ilabstore", fetch_ilab_product),
        "I LITE": ("ilite", fetch_ilite_product),
        "KingStore Saratov": ("kingstore_saratov", fetch_kingstore_product),
        "RE:premium": ("repremium", fetch_repremium_product),
        "SOTOViK": ("sotovik_saratov", fetch_sotovik_product),
        "Хатико": ("hatiko", fetch_hatiko_product),
    }


def detect_store_name_from_url(url: str) -> Optional[str]:
    raw_url = str(url or "").strip()
    if not raw_url:
        return None
    for site_name in DIRECT_URL_HOSTS_BY_STORE_NAME:
        if url_matches_store_domain(site_name, raw_url):
            return site_name
    return None


def url_matches_store_domain(site_name: str, url: str) -> bool:
    host = urlparse(str(url or "").strip()).netloc.lower()
    if not host:
        return False

    for expected_host in DIRECT_URL_HOSTS_BY_STORE_NAME.get(str(site_name or "").strip(), ()):
        normalized_expected = expected_host.lower()
        if host == normalized_expected or host.endswith("." + normalized_expected):
            return True
    return False


def compare_model(query: ModelQuery) -> List[QueryMatch]:
    matches: List[QueryMatch] = []

    with ThreadPoolExecutor(max_workers=min(MAX_COMPARE_WORKERS, len(STORE_SOURCES))) as executor:
        futures = [executor.submit(find_store_match, source, query) for source in STORE_SOURCES]
        for future in as_completed(futures):
            match = future.result()
            if match:
                matches.append(match)

    matches.sort(key=lambda item: item.price if item.price is not None else 10**12)
    return matches


def parse_generic_query(text: str) -> GenericQuery:
    raw_text = " ".join(str(text or "").split()).strip()
    if not raw_text:
        raise ValueError("Пустой запрос.")

    tokens = tuple(tokenize_generic_text(raw_text))
    if not tokens:
        raise ValueError("Не удалось распознать запрос. Напишите модель товара обычным текстом.")
    return GenericQuery(
        raw_text=raw_text,
        normalized_text=normalize_generic_text(raw_text),
        tokens=tokens,
    )


def compare_generic_query(query: GenericQuery) -> List[QueryMatch]:
    matches: List[QueryMatch] = []
    active_sources = [source for source in GENERIC_STORE_SOURCES if store_supports_generic_query(source, query)]
    if not active_sources:
        return matches

    with ThreadPoolExecutor(max_workers=min(MAX_COMPARE_WORKERS, len(active_sources))) as executor:
        futures = [executor.submit(find_generic_store_match, source, query) for source in active_sources]
        for future in as_completed(futures):
            match = future.result()
            if match:
                matches.append(match)

    matches.sort(key=lambda item: item.price if item.price is not None else 10**12)
    return matches


def find_store_match(source: StoreSource, query: ModelQuery) -> Optional[QueryMatch]:
    try:
        return source.finder(query)
    except Exception:  # noqa: BLE001
        logger.exception("Failed to compare store %s for query %s", source.key, query.display_name())
        return None


def find_generic_store_match(source: GenericStoreSource, query: GenericQuery) -> Optional[QueryMatch]:
    try:
        return source.finder(query)
    except Exception:  # noqa: BLE001
        logger.exception("Failed to compare store %s for generic query %s", source.key, query.display_name())
        return None


def detect_generic_category(query: GenericQuery) -> str:
    token_set = set(query.tokens)
    if {"playstation", "portal", "controller", "dualsense", "disc", "digital", "slim"} & token_set:
        return "playstation"
    if "macbook" in token_set:
        return "macbook"
    if "ipad" in token_set:
        return "ipad"
    if "galaxy" in token_set:
        return "samsung"
    return "generic"


def store_supports_generic_query(source: GenericStoreSource, query: GenericQuery) -> bool:
    category = detect_generic_category(query)
    if category == "generic":
        return True
    supported_categories = GENERIC_STORE_CATEGORY_SUPPORT.get(source.key)
    if not supported_categories:
        return True
    return category in supported_categories


def parse_model_query(text: str) -> ModelQuery:
    normalized = normalize_free_text(text)
    esim = detect_esim_variant(normalized)
    storage = extract_storage(normalized)
    model = extract_model(normalized)
    color = extract_color(normalized)

    if not model or not storage or not color:
        raise ValueError(
            "Не удалось распознать модель. Пример запроса: `сравни 17 pro 256 silver sim`."
        )

    return ModelQuery(model=model, storage=storage, color=canonicalize_color(model, color), esim=esim)


def find_ilab_match(query: ModelQuery) -> Optional[QueryMatch]:
    with ILAB_CSV.open("r", encoding="utf-8", newline="") as handle:
        rows = csv.DictReader(handle)
        for row in rows:
            url = (row.get("url") or "").strip()
            if not url:
                continue

            label_query = parse_ilab_catalog_query(row.get("label", ""), url)
            if not queries_match(label_query, query):
                continue

            details = fetch_ilab_product(url)
            if not details:
                continue
            return QueryMatch(
                site_key="ilabstore",
                site_name="iLab",
                name=details.get("name") or row.get("label", ""),
                url=url,
                price=details.get("price"),
                old_price=details.get("old_price"),
                availability_text=details.get("availability_text"),
                availability_status=details.get("availability_status", "unknown"),
            )

    return None


def find_ilite_match(query: ModelQuery) -> Optional[QueryMatch]:
    category_url = choose_ilite_category(query)
    if not category_url:
        return None

    html = try_fetch_html(category_url)
    if not html:
        return None
    for entry in parse_ilite_category_entries(html):
        try:
            entry_query = parse_model_query(entry["name"])
        except ValueError:
            continue

        if not queries_match(entry_query, query):
            continue

        details = fetch_ilite_product(entry["url"]) or {}
        return QueryMatch(
            site_key="ilite",
            site_name="I LITE",
            name=details.get("name") or entry["name"],
            url=entry["url"],
            price=details.get("price") or entry.get("price"),
            old_price=details.get("old_price"),
            availability_text=details.get("availability_text"),
            availability_status=details.get("availability_status", "unknown"),
            note="Найдено через категорию {0}".format(category_url),
        )

    return None


def find_kingstore_match(query: ModelQuery) -> Optional[QueryMatch]:
    category_url = KINGSTORE_CATEGORY_BY_MODEL.get(query.model)
    if not category_url:
        return None

    html = try_fetch_html(category_url)
    if not html:
        return None
    for entry in parse_kingstore_category_entries(html):
        try:
            entry_query = parse_model_query(entry["name"])
        except ValueError:
            continue

        if not queries_match(entry_query, query):
            continue

        details = fetch_kingstore_product(entry["url"]) or {}
        return QueryMatch(
            site_key="kingstore_saratov",
            site_name="KingStore Saratov",
            name=details.get("name") or entry["name"],
            url=entry["url"],
            price=details.get("price") or entry.get("price"),
            old_price=details.get("old_price"),
            availability_text=details.get("availability_text") or entry.get("availability_text"),
            availability_status=details.get("availability_status") or entry.get("availability_status", "unknown"),
            note="Найдено через категорию {0}".format(category_url),
        )

    return None


def find_jobscalling_match(query: ModelQuery) -> Optional[QueryMatch]:
    for url in build_jobscalling_candidate_urls(query):
        details = fetch_jobscalling_product(url)
        if not details or not details.get("name"):
            continue

        try:
            details_query = parse_model_query(details["name"])
        except ValueError:
            continue

        if not queries_match(details_query, query, allow_unspecified_esim=True):
            continue

        notes = ["Найдено по прямой карточке"]
        if query.esim is not None and details_query.esim is None:
            notes.append("сайт не указывает вариант SIM/eSIM")

        return QueryMatch(
            site_key="jobscalling",
            site_name="Jobscalling",
            name=details["name"],
            url=url,
            price=details.get("price"),
            old_price=details.get("old_price"),
            availability_text=details.get("availability_text"),
            availability_status=details.get("availability_status", "unknown"),
            note="; ".join(notes),
        )

    return None


def find_sotovik_match(query: ModelQuery) -> Optional[QueryMatch]:
    seen_urls = set()

    for search_phrase in build_sotovik_search_phrases(query):
        for page_number in range(1, SOTOVIK_SEARCH_MAX_PAGES + 1):
            search_url = "https://srt.sotovik.shop/catalog/?q={0}".format(quote_plus(search_phrase))
            if page_number > 1:
                search_url += "&PAGEN_3={0}".format(page_number)

            html = try_fetch_html(search_url)
            if not html:
                continue
            for entry in parse_sotovik_search_results(html):
                if entry["url"] in seen_urls:
                    continue
                seen_urls.add(entry["url"])

                try:
                    entry_query = parse_model_query(entry["name"])
                except ValueError:
                    continue

                if not queries_match(entry_query, query):
                    continue

                note = "Найдено через поиск SOTOViK: {0}".format(search_phrase)
                if page_number > 1:
                    note += ", страница {0}".format(page_number)

                return QueryMatch(
                    site_key="sotovik_saratov",
                    site_name="SOTOViK",
                    name=entry["name"],
                    url=entry["url"],
                    price=entry.get("price"),
                    old_price=None,
                    availability_text=entry.get("availability_text"),
                    availability_status=entry.get("availability_status", "unknown"),
                    note=note,
                )

    return None


def find_hatiko_match(query: ModelQuery) -> Optional[QueryMatch]:
    category_url = HATIKO_CATEGORY_BY_MODEL.get(query.model)
    if category_url:
        for entry in fetch_hatiko_category_entries(category_url):
            try:
                entry_query = parse_model_query(entry["name"])
            except ValueError:
                continue

            if not queries_match(entry_query, query):
                continue

            return QueryMatch(
                site_key="hatiko",
                site_name="Хатико",
                name=entry["name"],
                url=entry["url"],
                price=entry.get("price"),
                old_price=entry.get("old_price"),
                availability_text=entry.get("availability_text"),
                availability_status=entry.get("availability_status", "unknown"),
                note="Найдено через категорию Хатико {0}".format(category_url),
            )

    for search_phrase in build_hatiko_search_phrases(query):
        search_url = "https://hatiko.ru/search/?query={0}".format(quote_plus(search_phrase))
        for candidate in search_hatiko_candidates(search_url):
            try:
                candidate_query = parse_model_query(candidate["name"])
            except ValueError:
                continue

            if not queries_match(candidate_query, query):
                continue

            details = fetch_hatiko_product(candidate["url"])
            if not details or not details.get("name"):
                continue

            return QueryMatch(
                site_key="hatiko",
                site_name="Хатико",
                name=details["name"],
                url=candidate["url"],
                price=details.get("price"),
                old_price=details.get("old_price"),
                availability_text=details.get("availability_text"),
                availability_status=details.get("availability_status", "unknown"),
                note="Найдено через поиск Хатико: {0}".format(search_phrase),
            )

    return None


def find_nobel_match(query: ModelQuery) -> Optional[QueryMatch]:
    category_url = NOBEL_CATEGORY_BY_MODEL.get(query.model)
    if not category_url:
        return None

    html = try_fetch_html(category_url)
    if not html:
        return None
    model_name = (
        regex_first(html, r"'TITLE':'([^']+)'")
        or regex_first(html, r"<h1[^>]*>\s*(.*?)\s*</h1>")
        or "iPhone {0}".format(query.model.title())
    )
    normalized_model_name = html_strip(model_name)

    for offer in parse_nobel_offers(html):
        try:
            offer_query = parse_model_query("{0} {1}".format(normalized_model_name, offer["sku"]))
        except ValueError:
            continue

        if not queries_match(offer_query, query):
            continue

        availability_text = "В наличии" if offer["availability"].lower() == "instock" else offer["availability"]

        return QueryMatch(
            site_key="nobel_saratov",
            site_name="НОБЕЛЬ.РФ",
            name="{0}, {1}".format(normalized_model_name, offer["sku"]),
            url=category_url,
            price=offer["price"],
            old_price=None,
            availability_text=availability_text,
            availability_status=normalize_availability(
                offer["availability"],
                in_stock_patterns=("instock",),
                out_of_stock_patterns=("outofstock", "preorder", "backorder"),
            ),
            note="Найдено по SKU-вариациям на карточке {0}".format(category_url),
        )

    return None


def find_ilab_generic_match(query: GenericQuery) -> Optional[QueryMatch]:
    search_url = "https://ilabstore.ru/?s={0}&post_type=product".format(quote_plus(query.raw_text))
    html = try_fetch_html(search_url)
    if not html:
        return None

    entries = list(parse_ilab_collection_entries(html))
    direct_match = build_generic_query_match("ilabstore", "iLab", query, entries)
    if direct_match:
        direct_match.note = "Найдено через поиск iLab"
        return direct_match

    for url in filter_catalog_urls_for_generic_category(
        rank_catalog_urls_for_query(
            extract_internal_catalog_urls("https://ilabstore.ru", html),
            query,
        ),
        query,
    )[:1]:
        candidate_html = try_fetch_html(url)
        if not candidate_html:
            continue
        collection_entries = parse_ilab_collection_entries(candidate_html)
        if collection_entries:
            entries.extend(collection_entries)
            continue

        details = fetch_ilab_product(url)
        if details and details.get("name"):
            entries.append(
                {
                    "name": details.get("name"),
                    "url": url,
                    "price": details.get("price"),
                    "old_price": details.get("old_price"),
                    "availability_text": details.get("availability_text"),
                    "availability_status": details.get("availability_status", "unknown"),
                }
            )

    match = build_generic_query_match("ilabstore", "iLab", query, entries)
    if match:
        match.note = "Найдено через iLab"
    return match


def find_ilite_generic_match(query: GenericQuery) -> Optional[QueryMatch]:
    entry = None
    for search_phrase in build_generic_search_phrases(query):
        search_url = "https://i-lite.ru/?s={0}".format(quote_plus(search_phrase))
        html = try_fetch_html(search_url)
        if not html:
            continue
        entry = select_best_generic_entry(parse_ilite_category_entries(html), query)
        if entry:
            break
    if not entry:
        return None

    details = fetch_ilite_product(str(entry["url"])) or {}
    return QueryMatch(
        site_key="ilite",
        site_name="I LITE",
        name=str(details.get("name") or entry.get("name") or ""),
        url=str(entry["url"]),
        price=details.get("price") or _coalesce_int(entry.get("price")),
        old_price=details.get("old_price"),
        availability_text=details.get("availability_text"),
        availability_status=str(details.get("availability_status") or "unknown"),
        note="Найдено через поиск I LITE",
    )


def find_kingstore_generic_match(query: GenericQuery) -> Optional[QueryMatch]:
    entry = None
    for search_phrase in build_generic_search_phrases(query):
        search_url = "https://saratov.kingstore.io/search?q={0}".format(quote_plus(search_phrase))
        html = try_fetch_html(search_url)
        if not html:
            continue
        entry = select_best_generic_entry(parse_kingstore_category_entries(html), query)
        if entry:
            break
    if not entry:
        return None

    details = fetch_kingstore_product(str(entry["url"])) or {}
    return QueryMatch(
        site_key="kingstore_saratov",
        site_name="KingStore Saratov",
        name=str(details.get("name") or entry.get("name") or ""),
        url=str(entry["url"]),
        price=details.get("price") or _coalesce_int(entry.get("price")),
        old_price=details.get("old_price"),
        availability_text=details.get("availability_text") or entry.get("availability_text"),
        availability_status=str(details.get("availability_status") or entry.get("availability_status") or "unknown"),
        note="Найдено через поиск KingStore",
    )


def find_jobscalling_generic_match(query: GenericQuery) -> Optional[QueryMatch]:
    entry = None
    for search_phrase in build_generic_search_phrases(query):
        search_url = "https://jobscalling.store/search/?q={0}".format(quote_plus(search_phrase))
        html = try_fetch_html(search_url)
        if not html:
            continue
        entry = select_best_generic_entry(parse_jobscalling_search_results(html), query)
        if entry:
            break
    if not entry:
        return None

    details = fetch_jobscalling_product(str(entry["url"])) or {}
    return QueryMatch(
        site_key="jobscalling",
        site_name="Jobscalling",
        name=str(details.get("name") or entry.get("name") or ""),
        url=str(entry["url"]),
        price=_coalesce_int(details.get("price")) or _coalesce_int(entry.get("price")),
        old_price=_coalesce_int(details.get("old_price")) or _coalesce_int(entry.get("old_price")),
        availability_text=details.get("availability_text") or entry.get("availability_text"),
        availability_status=str(details.get("availability_status") or entry.get("availability_status") or "unknown"),
        note="Найдено через поиск Jobscalling",
    )


def find_sotovik_generic_match(query: GenericQuery) -> Optional[QueryMatch]:
    seen_urls = set()
    entries: List[Dict[str, object]] = []

    for search_phrase in build_generic_search_phrases(query):
        if not search_phrase:
            continue
        for page_number in range(1, GENERIC_SOTOVIK_MAX_PAGES + 1):
            search_url = "https://srt.sotovik.shop/catalog/?q={0}".format(quote_plus(search_phrase))
            if page_number > 1:
                search_url += "&PAGEN_3={0}".format(page_number)
            html = try_fetch_html(search_url)
            if not html:
                continue
            for entry in parse_sotovik_search_results(html):
                if entry["url"] in seen_urls:
                    continue
                seen_urls.add(str(entry["url"]))
                entries.append(entry)

    match = build_generic_query_match("sotovik_saratov", "SOTOViK", query, entries)
    if match:
        match.note = "Найдено через поиск SOTOViK"
    return match


def find_hatiko_generic_match(query: GenericQuery) -> Optional[QueryMatch]:
    search_url = "https://hatiko.ru/search/?query={0}".format(quote_plus(query.raw_text))
    entries = search_hatiko_candidates(search_url)
    entry = select_best_generic_entry(entries, query)
    if not entry:
        return None

    details = fetch_hatiko_product(str(entry["url"]))
    if not details or not details.get("name"):
        return None

    return QueryMatch(
        site_key="hatiko",
        site_name="Хатико",
        name=str(details["name"]),
        url=str(entry["url"]),
        price=_coalesce_int(details.get("price")),
        old_price=_coalesce_int(details.get("old_price")),
        availability_text=details.get("availability_text"),
        availability_status=str(details.get("availability_status") or "unknown"),
        note="Найдено через поиск Хатико",
    )


def find_nobel_generic_match(query: GenericQuery) -> Optional[QueryMatch]:
    search_url = "https://xn--80aag1ciek.xn--90aisff1g.xn--p1ai/search/?q={0}".format(quote_plus(query.raw_text))
    html = try_fetch_html(search_url)
    if not html:
        return None

    entries: List[Dict[str, object]] = []
    for url in rank_catalog_urls_for_query(
        extract_internal_catalog_urls("https://xn--80aag1ciek.xn--90aisff1g.xn--p1ai", html),
        query,
    )[:4]:
        candidate_html = try_fetch_html(url)
        if not candidate_html:
            continue
        entries.extend(parse_nobel_offer_entries(url, candidate_html))

    match = build_generic_query_match("nobel_saratov", "НОБЕЛЬ.РФ", query, entries)
    if match:
        match.note = "Найдено через поиск НОБЕЛЬ.РФ"
    return match


def choose_ilite_category(query: ModelQuery) -> Optional[str]:
    model_key = query.model
    if (model_key, query.esim) in ILITE_CATEGORY_BY_MODEL:
        return ILITE_CATEGORY_BY_MODEL[(model_key, query.esim)]
    if (model_key, False) in ILITE_CATEGORY_BY_MODEL and query.esim is None:
        return ILITE_CATEGORY_BY_MODEL[(model_key, False)]
    return None


def build_jobscalling_candidate_urls(query: ModelQuery) -> List[str]:
    model_slug = JOBSCALLING_MODEL_SLUGS.get(query.model)
    if not model_slug:
        return []

    color_slugs = JOBSCALLING_COLOR_SLUGS.get(query.color, [query.color.replace(" ", "-")])
    urls: List[str] = []

    for color_slug in color_slugs:
        for suffix in JOBSCALLING_CONDITION_SUFFIXES:
            for pattern in JOBSCALLING_PREFIX_PATTERNS:
                slug = pattern.format(
                    model=model_slug,
                    storage=query.storage.lower(),
                    color=color_slug,
                    suffix=suffix,
                )
                urls.append(urljoin("https://jobscalling.store/smartfony/", slug))

    return dedupe(urls)


def build_search_phrase(query: ModelQuery) -> str:
    parts = ["iphone", query.model, query.storage, query.color]
    if query.esim is True:
        parts.append("esim")
    elif query.esim is False:
        parts.append("sim")
    return " ".join(parts)


def build_sotovik_search_phrases(query: ModelQuery) -> List[str]:
    return dedupe(
        [
            "iphone {0} {1}".format(query.model, query.storage),
            "iphone {0}".format(query.model),
        ]
    )


def build_hatiko_search_phrases(query: ModelQuery) -> List[str]:
    return dedupe(
        [
            build_search_phrase(query),
            "iphone {0} {1}".format(query.model, query.storage),
            "iphone {0}".format(query.model),
        ]
    )


def parse_ilite_category_entries(html: str) -> List[Dict[str, object]]:
    pattern = re.compile(
        r'<div class="product-item mb-3"[^>]*data-price="(?P<price>\d+)"[\s\S]*?'
        r'<span class="name">(?P<name>.*?)</span>[\s\S]*?'
        r'<a href="(?P<url>https://i-lite\.ru/[^"]+)" class="absolute-href"></a>',
        re.IGNORECASE,
    )
    entries = []
    for match in pattern.finditer(html):
        entries.append(
            {
                "name": html_strip(match.group("name")),
                "url": match.group("url"),
                "price": int(match.group("price")),
            }
        )
    return entries


def parse_sotovik_search_results(html: str) -> List[Dict[str, object]]:
    entries = []
    name_pattern = re.compile(
        r'<a href="(?P<url>/catalog/smartfony/apple_iphone_1/[^"]+/)" class="dark_link js-notice-block__title"><span>(?P<name>.*?)</span></a>',
        re.IGNORECASE,
    )
    for match in name_pattern.finditer(html):
        snippet = html[match.start() : match.start() + 15000]
        price = regex_first(snippet, r'<div class="price" data-currency="RUB" data-value="(\d+)">')
        button_text = regex_first(
            snippet,
            r'data-value="\d+"[^>]*class="small to-cart[^"]*"[^>]*><i></i><span>(.*?)</span></span>',
        )

        if not price or not button_text:
            continue

        cleaned_button_text = html_strip(button_text)
        entries.append(
            {
                "name": html_strip(match.group("name")),
                "url": urljoin("https://srt.sotovik.shop", match.group("url")),
                "price": int(price),
                "availability_text": cleaned_button_text,
                "availability_status": normalize_availability(
                    cleaned_button_text,
                    in_stock_patterns=("в корзину", "купить"),
                    out_of_stock_patterns=("нет в наличии", "предзаказ"),
                ),
            }
        )
    return entries


def parse_kingstore_category_entries(html: str) -> List[Dict[str, object]]:
    pattern = re.compile(
        r'<a href="(?P<url>/catalog/[^"]+)" class="index-products-body-item__title">\s*(?P<name>.*?)\s*</a>[\s\S]*?'
        r'<div class="index-products-body-item__button-price">\s*(?P<price>[\d\s]+)\s*(?:₽|руб\.)\s*</div>[\s\S]*?'
        r'<div class="index-products-body-item__button-title[^"]*">\s*(?P<button>.*?)\s*</div>',
        re.IGNORECASE,
    )
    entries = []
    for match in pattern.finditer(html):
        button_text = html_strip(match.group("button"))
        entries.append(
            {
                "name": html_strip(match.group("name")),
                "url": urljoin("https://saratov.kingstore.io", match.group("url")),
                "price": extract_price(match.group("price")),
                "availability_text": button_text,
                "availability_status": normalize_availability(
                    button_text,
                    in_stock_patterns=("купить", "в корзину"),
                    out_of_stock_patterns=("предзаказ", "нет в наличии"),
                ),
            }
        )
    return entries


def parse_jobscalling_search_results(html: str) -> List[Dict[str, object]]:
    pattern = re.compile(
        r'<div class="product-card[^"]*"[\s\S]*?'
        r'<a href="(?P<url>/[^"]+/)" class="product-card__(?:ava|title)"[^>]*?(?:title="(?P<title>[^"]+)")?[^>]*>\s*(?P<name>.*?)\s*</a>[\s\S]*?'
        r'<div class="product-card__price">\s*(?P<price>[\d\s]+)\s*руб\.\s*</div>'
        r'(?:[\s\S]*?<div class="product-card_old_price">\s*(?P<old_price>[\d\s]+)\s*руб\.\s*</div>)?[\s\S]*?'
        r'<a href="#" class="btn btn-black\s+add-to-basket">\s*(?P<button>.*?)\s*</a>',
        re.IGNORECASE,
    )
    entries = []
    seen_urls = set()

    for match in pattern.finditer(html):
        url = urljoin("https://jobscalling.store", match.group("url"))
        if url in seen_urls:
            continue
        seen_urls.add(url)

        raw_name = html_strip(match.group("title") or match.group("name") or "")
        availability_text = html_strip(match.group("button"))
        entries.append(
            {
                "name": raw_name,
                "url": url,
                "price": extract_price(match.group("price")),
                "old_price": extract_price(match.group("old_price")),
                "availability_text": availability_text,
                "availability_status": normalize_availability(
                    availability_text,
                    in_stock_patterns=("в корзину", "купить"),
                    out_of_stock_patterns=("предзаказ", "нет в наличии"),
                ),
            }
        )

    return entries


def parse_ilab_collection_entries(html: str) -> List[Dict[str, object]]:
    pattern = re.compile(
        r'<a href="(?P<url>https://ilabstore\.ru/catalog/[^"]+)" class="product_link">[\s\S]*?'
        r'<span class="product_name">(?P<name>.*?)</span>[\s\S]*?'
        r'<div class="product_avail">[\s\S]*?(?:<div class="avail">(?P<avail>.*?)</div>)?[\s\S]*?</div>[\s\S]*?'
        r'<div class="product_price">[\s\S]*?<bdi>(?P<price>[\d\s]+)<span',
        re.IGNORECASE,
    )
    entries = []
    seen_urls = set()
    for match in pattern.finditer(html):
        url = match.group("url")
        if url in seen_urls:
            continue
        seen_urls.add(url)
        availability_text = html_strip(match.group("avail") or "")
        entries.append(
            {
                "name": html_strip(match.group("name")),
                "url": url,
                "price": extract_price(match.group("price")),
                "old_price": None,
                "availability_text": availability_text or None,
                "availability_status": normalize_availability(
                    availability_text,
                    in_stock_patterns=("в наличии", "доставим"),
                    out_of_stock_patterns=("нет в наличии", "предзаказ", "распродано"),
                ),
            }
        )
    return entries


def parse_nobel_offers(html: str) -> List[Dict[str, object]]:
    pattern = re.compile(
        r'<meta itemprop="sku" content="(?P<sku>[^"]+)" />\s*'
        r'<meta itemprop="price" content="(?P<price>\d+)" />\s*'
        r'<meta itemprop="priceCurrency" content="RUB" />\s*'
        r'<link itemprop="availability" href="http://schema\.org/(?P<availability>[^"]+)" />',
        re.IGNORECASE,
    )
    offers = []
    for match in pattern.finditer(html):
        offers.append(
            {
                "sku": html_strip(match.group("sku")),
                "price": int(match.group("price")),
                "availability": match.group("availability"),
            }
        )
    return offers


def parse_nobel_offer_entries(url: str, html: str) -> List[Dict[str, object]]:
    title = (
        regex_first(html, r"'TITLE':'([^']+)'")
        or regex_first(html, r"<h1[^>]*>\s*(.*?)\s*</h1>")
        or ""
    )
    base_name = html_strip(title)
    offers = parse_nobel_offers(html)
    if offers:
        entries = []
        for offer in offers:
            availability_text = "В наличии" if str(offer["availability"]).lower() == "instock" else str(offer["availability"])
            entries.append(
                {
                    "name": "{0} {1}".format(base_name, offer["sku"]).strip(),
                    "url": url,
                    "price": offer["price"],
                    "old_price": None,
                    "availability_text": availability_text,
                    "availability_status": normalize_availability(
                        availability_text,
                        in_stock_patterns=("в наличии", "instock"),
                        out_of_stock_patterns=("нет в наличии", "outofstock", "preorder", "backorder"),
                    ),
                }
            )
        return entries

    price = extract_price(regex_first(html, r'<meta itemprop="price" content="(\d+)"'))
    if price is None:
        price = extract_price(regex_first(html, r'class="price[^"]*"[^>]*>\s*([\d\s]+)'))
    if not base_name or price is None:
        return []

    return [
        {
            "name": base_name,
            "url": url,
            "price": price,
            "old_price": None,
            "availability_text": None,
            "availability_status": "unknown",
        }
    ]


def fetch_ilab_product(url: str) -> Optional[Dict[str, object]]:
    html = try_fetch_html(url)
    if not html:
        return None
    name = regex_first(html, r'<h1 class="yellow">\s*(.*?)\s*</h1>')
    availability_text = regex_first(html, r'<div class="avail">\s*(.*?)\s*</div>')
    price = extract_price(regex_first(html, r'<div class="price">[\s\S]*?<bdi>(.*?)<span'))
    old_price = extract_price(regex_first(html, r'<div class="old_price">\s*(.*?)\s*</div>'))
    return {
        "name": html_strip(name) if name else None,
        "price": price,
        "old_price": old_price,
        "availability_text": html_strip(availability_text) if availability_text else None,
        "availability_status": normalize_availability(
            availability_text,
            in_stock_patterns=("в наличии", "доставим"),
            out_of_stock_patterns=("нет в наличии", "предзаказ", "распродано"),
        ),
    }


def fetch_ilite_product(url: str) -> Optional[Dict[str, object]]:
    html = try_fetch_html(url)
    if not html:
        return None
    name = regex_first(html, r'<h1[^>]*class="name"[^>]*>\s*(.*?)\s*</h1>')
    price = extract_price(regex_first(html, r'<meta itemprop="price" content="(\d+)"'))
    if price is None:
        price = extract_price(regex_first(html, r'<span class="price">\s*(.*?)\s*<meta itemprop="price"'))
    old_price = extract_price(regex_first(html, r'class="old-price"[^>]*>\s*(.*?)\s*</'))
    availability_href = regex_first(html, r'<link itemprop="availability" href="http://schema\.org/([^"]+)"')
    availability_text = availability_href or ""
    return {
        "name": html_strip(name) if name else None,
        "price": price,
        "old_price": old_price,
        "availability_text": availability_text,
        "availability_status": normalize_availability(
            availability_text,
            in_stock_patterns=("instock",),
            out_of_stock_patterns=("outofstock", "preorder", "backorder"),
        ),
    }


def run_hatiko_with_playwright(task_label: str, default_value, runner):
    with HATIKO_PLAYWRIGHT_LOCK:
        sync_playwright = get_sync_playwright()
        try:
            playwright_manager = sync_playwright()
        except Exception as error:  # noqa: BLE001
            logger.debug("Hatiko Playwright factory failed during %s: %s", task_label, error)
            return default_value

        try:
            with playwright_manager as playwright:
                return runner(playwright)
        except Exception as error:  # noqa: BLE001
            logger.debug("Hatiko Playwright session failed during %s: %s", task_label, error)
            return default_value


def search_hatiko_candidates(search_url: str) -> List[Dict[str, str]]:
    def _runner(playwright):
        browser = None
        try:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page(user_agent=USER_AGENT)
            page.goto(search_url, wait_until="domcontentloaded", timeout=HATIKO_NAVIGATION_TIMEOUT_MS)
            try:
                page.wait_for_selector('a[href*="/product/"]', timeout=HATIKO_SELECTOR_TIMEOUT_MS)
            except Exception:  # noqa: BLE001
                return []

            entries: List[Dict[str, str]] = []
            for link in page.locator('a[href*="/product/"]').all():
                text = (link.inner_text() or "").strip()
                href = (link.get_attribute("href") or "").strip()
                if not text or not href or href.startswith("#"):
                    continue

                entries.append(
                    {
                        "name": " ".join(text.split()),
                        "url": urljoin("https://hatiko.ru", href),
                    }
                )

            deduped = []
            seen = set()
            for entry in entries:
                if entry["url"] in seen:
                    continue
                seen.add(entry["url"])
                deduped.append(entry)
            return deduped
        except Exception as error:  # noqa: BLE001
            logger.debug("Hatiko search candidates failed for %s: %s", search_url, error)
            return []
        finally:
            if browser is not None:
                with suppress(Exception):
                    browser.close()

    return run_hatiko_with_playwright("Hatiko search candidates", [], _runner)


@lru_cache(maxsize=32)
def fetch_hatiko_category_entries(category_url: str) -> Tuple[Dict[str, object], ...]:
    def _runner(playwright):
        browser = None
        try:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page(user_agent=USER_AGENT)
            page.goto(category_url, wait_until="domcontentloaded", timeout=HATIKO_NAVIGATION_TIMEOUT_MS)
            page.wait_for_selector('a.s-product-header[href*="/product/"]', timeout=HATIKO_SELECTOR_TIMEOUT_MS)

            entries: List[Dict[str, object]] = []
            for link in page.locator('a.s-product-header[href*="/product/"]').all():
                text = (link.inner_text() or "").strip()
                href = (link.get_attribute("href") or "").strip()
                if "Смартфон Apple iPhone" not in text or not href:
                    continue

                card_html = link.evaluate("node => node.parentElement.parentElement.outerHTML")
                prices = re.findall(r'<span class="price">\s*([\d\s]+)\s*</span>', card_html)
                availability_text = regex_first(
                    card_html,
                    r'<span class="spinner-text text-nowrap">\s*(.*?)\s*</span>',
                )

                entries.append(
                    {
                        "name": " ".join(text.split()),
                        "url": urljoin("https://hatiko.ru", href),
                        "price": extract_price(prices[0]) if prices else None,
                        "old_price": extract_price(prices[1]) if len(prices) > 1 else None,
                        "availability_text": html_strip(availability_text) if availability_text else None,
                        "availability_status": normalize_availability(
                            availability_text,
                            in_stock_patterns=("в корзину", "купить"),
                            out_of_stock_patterns=("нет в наличии", "под заказ"),
                        ),
                    }
                )

            deduped = []
            seen = set()
            for entry in entries:
                if entry["url"] in seen:
                    continue
                seen.add(entry["url"])
                deduped.append(entry)
            return tuple(deduped)
        except Exception as error:  # noqa: BLE001
            logger.debug("Hatiko category parsing failed for %s: %s", category_url, error)
            return tuple()
        finally:
            if browser is not None:
                with suppress(Exception):
                    browser.close()

    return run_hatiko_with_playwright("Hatiko category fetch", tuple(), _runner)


def fetch_hatiko_product(url: str) -> Optional[Dict[str, object]]:
    html = try_fetch_html(url)
    if html:
        name = html_strip(regex_first(html, r"<h1[^>]*>\s*(.*?)\s*</h1>") or "")
        if not name:
            name = html_strip(regex_first(html, r"<title>\s*(.*?)\s*</title>") or "")
        html_prices = re.findall(r'<span class="price">\s*([\d\s]+)\s*(?:₽)?\s*</span>', html)
        price_values = dedupe_ints_preserving_order(extract_price(price) for price in html_prices)
        if not price_values:
            meta_price = extract_price(regex_first(html, r'<meta[^>]+itemprop="price"[^>]+content="(\d+)"'))
            if meta_price is not None:
                price_values = [meta_price]
        availability_match = re.search(r"(Есть в наличии|Нет в наличии|Под заказ)", html, re.IGNORECASE)
        if name and price_values:
            availability_text = availability_match.group(1) if availability_match else None
            return {
                "name": name,
                "price": price_values[0],
                "old_price": price_values[1] if len(price_values) > 1 else None,
                "availability_text": availability_text,
                "availability_status": normalize_availability(
                    availability_text,
                    in_stock_patterns=("есть в наличии",),
                    out_of_stock_patterns=("нет в наличии", "под заказ"),
                ),
            }

    def _runner(playwright):
        browser = None
        try:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page(user_agent=USER_AGENT)
            for attempt in range(2):
                try:
                    page.goto(url, wait_until="domcontentloaded", timeout=HATIKO_NAVIGATION_TIMEOUT_MS)
                    break
                except Exception as error:  # noqa: BLE001
                    if attempt == 1:
                        raise
                    logger.debug("Retrying Hatiko direct product after navigation error: %s", error)
                    page.wait_for_timeout(1200)

            try:
                page.wait_for_selector("h1", timeout=HATIKO_SELECTOR_TIMEOUT_MS)
            except Exception:  # noqa: BLE001
                logger.debug("Hatiko product page did not expose h1 in time: %s", url)
            try:
                page.wait_for_function(
                    r"() => document.body && /\d[\d\s]*\s?₽/.test(document.body.innerText)",
                    timeout=HATIKO_CONTENT_WAIT_TIMEOUT_MS,
                )
            except Exception:  # noqa: BLE001
                page.wait_for_timeout(1500)

            title = page.title().split(" купить в ", 1)[0].strip()
            body_text = page.locator("body").inner_text(timeout=HATIKO_BODY_TIMEOUT_MS)
            snippet = body_text.split("Обзор", 1)[0]
            price_values = extract_unique_price_values(snippet)
            if not price_values:
                html = page.content()
                html_prices = re.findall(r'<span class="price">\s*([\d\s]+)\s*₽\s*</span>', html)
                price_values = dedupe_ints_preserving_order(extract_price(price) for price in html_prices)
            availability_match = re.search(r"(Есть в наличии|Нет в наличии|Под заказ)", snippet, re.IGNORECASE)
            h1_text = ""
            try:
                if page.locator("h1").count():
                    h1_text = " ".join((page.locator("h1").first.inner_text() or "").split())
            except Exception:  # noqa: BLE001
                h1_text = ""

            return {
                "name": h1_text or title,
                "price": price_values[0] if price_values else None,
                "old_price": price_values[1] if len(price_values) > 1 else None,
                "availability_text": availability_match.group(1) if availability_match else None,
                "availability_status": normalize_availability(
                    availability_match.group(1) if availability_match else None,
                    in_stock_patterns=("есть в наличии",),
                    out_of_stock_patterns=("нет в наличии", "под заказ"),
                ),
            }
        except Exception as error:  # noqa: BLE001
            logger.debug("Hatiko direct product fetch failed for %s: %s", url, error)
            return None
        finally:
            if browser is not None:
                with suppress(Exception):
                    browser.close()

    return run_hatiko_with_playwright("Hatiko direct product", None, _runner)


def fetch_kingstore_product(url: str) -> Optional[Dict[str, object]]:
    html = try_fetch_html(url)
    if not html:
        return None
    name = regex_first(html, r"<h1[^>]*>\s*(.*?)\s*</h1>")
    price = extract_price(
        regex_first(html, r'page-product-card-info-price-and-buttons__price[^>]*>\s*([\d\s]+)\s*₽')
        or regex_first(html, r'product-page-main-info-price[^>]*>\s*([\d\s]+)\s*₽')
    )
    old_price = extract_price(
        regex_first(html, r'page-product-card-info-price-and-buttons__old-price[^>]*>\s*([\d\s]+)\s*₽')
        or regex_first(html, r'product-page-main-info-old-price[^>]*>\s*([\d\s]+)\s*₽')
    )
    availability_text = (
        regex_first(html, r'product-page-main-info-button-to-basket[^>]*>\s*(.*?)\s*</a>')
        or regex_first(html, r'class="[^"]*pre_zakaz[^"]*"[^>]*>\s*(.*?)\s*</a>')
    )
    return {
        "name": html_strip(name) if name else None,
        "price": price,
        "old_price": old_price,
        "availability_text": html_strip(availability_text) if availability_text else None,
        "availability_status": normalize_availability(
            availability_text,
            in_stock_patterns=("купить", "в корзину"),
            out_of_stock_patterns=("предзаказ", "нет в наличии"),
        ),
    }


def fetch_repremium_product(url: str) -> Optional[Dict[str, object]]:
    html = try_fetch_html(url)
    if not html:
        return None

    name = (
        regex_first(html, r'<h1[^>]*itemprop="name"[^>]*>\s*(.*?)\s*</h1>')
        or regex_first(html, r"<h1[^>]*>\s*(.*?)\s*</h1>")
        or regex_first(html, r"<title>\s*(.*?)\s+купить\s+по\s+цене",)
    )
    price = extract_price(
        regex_first(
            html,
            r'<div class="product-price2-base"[^>]*>[\s\S]*?<div class="product-price2__value"[^>]*>\s*([\d\s]+)\s*₽',
        )
        or
        regex_first(
            html,
            r'<div class="price_matrix_wrapper[\s\S]*?<span class="price_value">\s*([\d\s]+)\s*</span>',
        )
        or regex_first(html, r'<meta itemprop="price" content="(\d+)"')
        or regex_first(html, r'<div class="price[^"]*"[^>]*data-value="(\d+)"')
    )
    old_price = extract_price(
        regex_first(
            html,
            r'<div class="product-price2-old"[^>]*>[\s\S]*?<div class="product-price2__value"[^>]*>\s*([\d\s]+)\s*₽',
        )
        or
        regex_first(
            html,
            r'<div class="price_matrix_wrapper[\s\S]*?<span class="price_value old">\s*([\d\s]+)\s*</span>',
        )
        or regex_first(html, r'<span class="price_value old">\s*([\d\s]+)\s*</span>')
    )
    availability_schema = regex_first(
        html,
        r'<link itemprop="availability" href="http://schema\.org/([^"]+)"',
    )
    availability_text = {
        "InStock": "В наличии",
        "OutOfStock": "Нет в наличии",
        "PreOrder": "Предзаказ",
    }.get(str(availability_schema or "").strip(), availability_schema)
    if not availability_text:
        availability_text = (
            regex_first(html, r'<span class="product2__to-cart-text">\s*(.*?)\s*</span>')
            or regex_first(html, r'class="button[^"]*product2__quick[^"]*"[^>]*>\s*(.*?)\s*</a>')
            or regex_first(html, r'class="button[^"]*product2__notification[^"]*"[^>]*>\s*(.*?)\s*</')
        )
    return {
        "name": unescape(html_strip(name)) if name else None,
        "price": price,
        "old_price": old_price,
        "availability_text": html_strip(availability_text) if availability_text else None,
        "availability_status": normalize_availability(
            availability_text or availability_schema,
            in_stock_patterns=("в наличии", "instock", "добавить в корзину", "купить сейчас", "купить"),
            out_of_stock_patterns=("нет в наличии", "outofstock", "preorder", "сообщить о поступлении"),
        ),
    }


def fetch_sotovik_product(url: str) -> Optional[Dict[str, object]]:
    html = try_fetch_html(url)
    if not html:
        return None

    name = (
        regex_first(html, r"<h1[^>]*>\s*(.*?)\s*</h1>")
        or regex_first(html, r"<title>\s*(.*?)\s+в\s+Саратове")
    )
    price = extract_price(regex_first(html, r'<div class="price" data-currency="RUB" data-value="(\d+)">'))
    old_price = extract_price(regex_first(html, r'class="old-price[^"]*"[^>]*>\s*([\d\s]+)\s*</'))
    availability_text = regex_first(
        html,
        r'class="small to-cart[^"]*"[^>]*><i></i><span>(.*?)</span></span>',
    )
    return {
        "name": html_strip(name) if name else None,
        "price": price,
        "old_price": old_price,
        "availability_text": html_strip(availability_text) if availability_text else None,
        "availability_status": normalize_availability(
            availability_text,
            in_stock_patterns=("в корзину", "купить"),
            out_of_stock_patterns=("нет в наличии", "предзаказ"),
        ),
    }


def extract_unique_price_values(text: str) -> List[int]:
    return dedupe_ints_preserving_order(
        extract_price(match)
        for match in re.findall(r"\d[\d\s]* ₽", str(text or ""))
    )


def dedupe_ints_preserving_order(values: Iterable[Optional[int]]) -> List[int]:
    result: List[int] = []
    seen: set[int] = set()
    for value in values:
        if value is None or value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def fetch_jobscalling_product(url: str) -> Optional[Dict[str, object]]:
    html = try_fetch_html(url)
    if not html:
        return None

    name = regex_first(html, r'<h1 class="block_title">\s*(.*?)\s*</h1>')
    price = extract_price(
        regex_first(html, r'page-product-card-info-price-and-buttons__price">\s*([\d\s]+)\s*₽')
    )
    old_price = extract_price(
        regex_first(html, r'page-product-card-info-price-and-buttons__old_price">\s*([\d\s]+)\s*₽')
    )
    availability_text = regex_first(html, r'<a href="#" class="btn btn-black\s+add-to-basket">\s*(.*?)\s*</a>')
    return {
        "name": html_strip(name) if name else None,
        "price": price,
        "old_price": old_price,
        "availability_text": html_strip(availability_text) if availability_text else None,
        "availability_status": normalize_availability(
            availability_text,
            in_stock_patterns=("в корзину", "купить"),
            out_of_stock_patterns=("предзаказ", "нет в наличии"),
        ),
    }


@lru_cache(maxsize=512)
def fetch_html(url: str) -> str:
    request = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(request, timeout=HTML_FETCH_TIMEOUT_SECONDS) as response:
        return response.read().decode("utf-8", "ignore")


def try_fetch_html(url: str) -> Optional[str]:
    try:
        return fetch_html(url)
    except HTTPError as error:
        if error.code in {403, 404, 429, 503}:
            logger.debug("Skipping %s due to HTTP %s", url, error.code)
            return None
        raise
    except URLError as error:
        logger.debug("Failed to fetch %s: %s", url, error)
        return None
    except (socket.timeout, TimeoutError) as error:
        logger.debug("Timed out fetching %s: %s", url, error)
        return None


def normalize_generic_text(text: str) -> str:
    value = str(text or "").lower().replace("ё", "е")
    value = value.replace("«", " ").replace("»", " ")
    value = value.replace("–", "-").replace("—", "-")
    value = value.replace("гб", "gb").replace("тб", "tb")
    value = re.sub(r"(\d+)\s*(gb|tb)\b", r"\1\2", value)
    value = re.sub(r"(\d+)\s*/\s*(\d+)\s*gb", r"\1gb \2gb", value)
    value = re.sub(r"(\d+)\s*/\s*(\d+)\b", r"\1gb \2gb", value)

    for source, target in GENERIC_TEXT_ALIASES:
        value = value.replace(source, target)
    for source, target in COLOR_ALIASES.items():
        value = value.replace(source, target)

    value = re.sub(r"[^a-z0-9а-я]+", " ", value)
    return " ".join(value.split())


def tokenize_generic_text(text: str) -> List[str]:
    normalized = normalize_generic_text(text)
    tokens = []
    for token in normalized.split():
        if token in GENERIC_STOPWORDS:
            continue
        tokens.append(token)
    return tokens


def is_year_token(token: str) -> bool:
    return token.isdigit() and len(token) == 4 and token.startswith("20")


def storage_token_sort_key(token: str) -> Tuple[int, int, str]:
    match = re.fullmatch(r"(\d+)(gb|tb)", token)
    if not match:
        return (0, 0, token)
    amount = int(match.group(1))
    multiplier = 1024 if match.group(2) == "tb" else 1
    return (amount * multiplier, len(token), token)


def choose_primary_storage_token(tokens: Iterable[str]) -> Optional[str]:
    storage_tokens = [token for token in tokens if token.endswith(("gb", "tb"))]
    if not storage_tokens:
        return None
    return max(storage_tokens, key=storage_token_sort_key)


def build_generic_search_phrases(query: GenericQuery) -> List[str]:
    phrases: List[str] = []
    category = detect_generic_category(query)
    normalized_phrase = " ".join(query.tokens)
    normalized_parts = query.normalized_text.split()
    primary_storage = choose_primary_storage_token(query.tokens)

    def add_phrase(parts: Iterable[str] | str) -> None:
        if isinstance(parts, str):
            phrase = " ".join(parts.split()).strip()
        else:
            phrase = " ".join(part for part in parts if part).strip()
        if phrase and phrase not in phrases:
            phrases.append(phrase)

    add_phrase(query.raw_text)
    add_phrase(query.normalized_text)
    add_phrase(normalized_phrase)

    base_tokens: List[str] = []
    for token in query.tokens:
        if is_year_token(token):
            continue
        if category == "samsung" and token.endswith(("gb", "tb")) and token != primary_storage:
            continue
        base_tokens.append(token)

    add_phrase(base_tokens)
    add_phrase(token for token in base_tokens if token not in GENERIC_COLOR_TOKENS)

    branded_tokens: List[str] = []
    for token in normalized_parts:
        if is_year_token(token):
            continue
        if category == "samsung" and token.endswith(("gb", "tb")) and primary_storage and token != primary_storage:
            continue
        branded_tokens.append(token)

    add_phrase(branded_tokens)
    add_phrase(token for token in branded_tokens if token not in GENERIC_COLOR_TOKENS)
    relaxed_branded_tokens = [
        token
        for token in branded_tokens
        if token not in GENERIC_COLOR_TOKENS and token not in GENERIC_OPTIONAL_SEARCH_TOKENS
    ]
    add_phrase(relaxed_branded_tokens)

    if primary_storage:
        storage_number = re.sub(r"(gb|tb)$", "", primary_storage)
        if storage_number:
            primary_only_tokens = [
                token
                for token in branded_tokens
                if not (token.endswith(("gb", "tb")) and token != primary_storage)
            ]
            primary_only_relaxed_tokens = [
                token
                for token in relaxed_branded_tokens
                if not (token.endswith(("gb", "tb")) and token != primary_storage)
            ]
            add_phrase(
                storage_number if token == primary_storage else token
                for token in branded_tokens
            )
            add_phrase(
                storage_number if token == primary_storage else token
                for token in branded_tokens
                if token not in GENERIC_COLOR_TOKENS
            )
            add_phrase(
                storage_number if token == primary_storage else token
                for token in relaxed_branded_tokens
            )
            add_phrase(primary_only_tokens)
            add_phrase(primary_only_relaxed_tokens)
            add_phrase(
                storage_number if token == primary_storage else token
                for token in primary_only_tokens
            )
            add_phrase(
                storage_number if token == primary_storage else token
                for token in primary_only_relaxed_tokens
            )

    if category == "playstation":
        if "controller" in base_tokens and "dualsense" not in base_tokens:
            playstation_tokens = [token for token in base_tokens if token != "controller"]
            add_phrase(["dualsense", *playstation_tokens])
        add_phrase(token for token in base_tokens if token not in {"black", "white", "blue", "pink"})

    return phrases


def build_required_generic_tokens(tokens: Iterable[str], category: str = "generic") -> set[str]:
    token_list = list(tokens)
    result = set()
    primary_storage = choose_primary_storage_token(token_list)
    for token in token_list:
        if is_year_token(token):
            continue
        if token.endswith(("gb", "tb")):
            if category == "samsung" and primary_storage and token != primary_storage:
                continue
            result.add(token)
            continue
        if re.fullmatch(r"[a-zа-я]+\d+[a-zа-я]*", token):
            result.add(token)
            continue
        if token in GENERIC_REQUIRED_HINTS:
            result.add(token)
            continue
        if token.isdigit() and (len(token) >= 2 or ("playstation" in token_list and token == "5")):
            result.add(token)
    return result


def build_scoring_generic_tokens(tokens: Iterable[str], category: str = "generic") -> set[str]:
    token_list = list(tokens)
    primary_storage = choose_primary_storage_token(token_list)
    result = set()
    for token in token_list:
        if is_year_token(token):
            continue
        if token in GENERIC_OPTIONAL_SEARCH_TOKENS:
            continue
        if category == "samsung" and token.endswith(("gb", "tb")) and primary_storage and token != primary_storage:
            continue
        result.add(token)
    return result


def score_generic_candidate(query: GenericQuery, candidate_name: str) -> float:
    candidate_tokens = set(tokenize_generic_text(candidate_name))
    if not candidate_tokens:
        return 0.0

    category = detect_generic_category(query)
    required_tokens = build_required_generic_tokens(query.tokens, category)
    if any(token not in candidate_tokens for token in required_tokens):
        return 0.0

    query_token_set = set(query.tokens)
    extra_variant_tokens = (candidate_tokens & GENERIC_VARIANT_GUARD_TOKENS) - query_token_set
    if extra_variant_tokens:
        return 0.0

    scoring_query_tokens = build_scoring_generic_tokens(query.tokens, category)
    matched = len(scoring_query_tokens & candidate_tokens)
    score = matched / max(len(scoring_query_tokens), 1)

    normalized_candidate = normalize_generic_text(candidate_name)
    if query.normalized_text and query.normalized_text in normalized_candidate:
        score += 0.25

    return score


def select_best_generic_entry(
    entries: Iterable[Dict[str, object]],
    query: GenericQuery,
    minimum_score: float = 0.55,
) -> Optional[Dict[str, object]]:
    best_entry: Optional[Dict[str, object]] = None
    best_score = 0.0
    best_price = 10**12

    for entry in entries:
        name = str(entry.get("name") or "").strip()
        if not name:
            continue
        score = score_generic_candidate(query, name)
        if score < minimum_score:
            continue

        price = _coalesce_int(entry.get("price"))
        sort_price = price if price is not None else 10**12
        if score > best_score or (score == best_score and sort_price < best_price):
            best_entry = entry
            best_score = score
            best_price = sort_price

    return best_entry


def build_generic_query_match(
    site_key: str,
    site_name: str,
    query: GenericQuery,
    entries: Iterable[Dict[str, object]],
) -> Optional[QueryMatch]:
    entry = select_best_generic_entry(entries, query)
    if not entry:
        return None

    return QueryMatch(
        site_key=site_key,
        site_name=site_name,
        name=str(entry.get("name") or ""),
        url=str(entry.get("url") or ""),
        price=_coalesce_int(entry.get("price")),
        old_price=_coalesce_int(entry.get("old_price")),
        availability_text=entry.get("availability_text"),
        availability_status=str(entry.get("availability_status") or "unknown"),
    )


def extract_internal_catalog_urls(base_url: str, html: str) -> List[str]:
    urls = []
    for path in re.findall(r'href="(/catalog/[^"]+)"', html, re.IGNORECASE):
        full_url = urljoin(base_url, path)
        if any(token in full_url for token in ("/catalog/?q=", "/catalog/compare/", "/catalog/#")):
            continue
        if full_url.rstrip("/").endswith("/catalog"):
            continue
        urls.append(full_url)
    for full_url in re.findall(r'href="(https?://[^"]+/catalog/[^"]+)"', html, re.IGNORECASE):
        if any(token in full_url for token in ("/catalog/?q=", "/catalog/compare/", "/catalog/#")):
            continue
        if full_url.rstrip("/").endswith("/catalog"):
            continue
        urls.append(full_url)
    return dedupe(urls)


def filter_catalog_urls_for_generic_category(urls: Iterable[str], query: GenericQuery) -> List[str]:
    category = detect_generic_category(query)
    if category == "generic":
        return list(urls)

    category_hints = {
        "ipad": ("/catalog/ipad/",),
        "macbook": ("/catalog/macbook/",),
        "playstation": ("/catalog/playstation/", "/catalog/sony-playstation/", "/catalog/igrovye-pristavki/"),
        "samsung": ("/catalog/samsung/", "/catalog/smartfony-samsung/", "/catalog/telefony-samsung/"),
    }
    hints = category_hints.get(category, ())
    if not hints:
        return list(urls)

    preferred = [url for url in urls if any(hint in url for hint in hints)]
    if preferred:
        return preferred
    return list(urls)


def rank_catalog_urls_for_query(urls: Iterable[str], query: GenericQuery) -> List[str]:
    scored_urls = []
    for url in urls:
        path_text = url.replace("-", " ").replace("/", " ")
        score = score_generic_candidate(query, path_text)
        scored_urls.append((score, url))
    scored_urls.sort(key=lambda item: (-item[0], item[1]))
    return [url for _, url in scored_urls]


def _coalesce_int(value) -> Optional[int]:
    if value is None:
        return None
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    raw = str(value).strip().replace("\xa0", "").replace(" ", "")
    if not raw:
        return None
    return int(raw)


def get_sync_playwright():
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as error:
        raise RuntimeError("Playwright is not installed. Run run_telegram_bot.sh or install requirements.") from error

    return sync_playwright


def normalize_free_text(text: str) -> str:
    value = text.lower()
    value = value.replace("«", " ").replace("»", " ")
    value = value.replace("гб", "gb")
    value = value.replace("тб", "tb")
    value = value.replace("1 sim", " sim ")
    value = value.replace("1sim", " sim ")
    value = value.replace("esim+sim", " sim ")
    value = value.replace("sim+esim", " sim ")
    value = value.replace("sim esim", " sim ")
    value = value.replace("e-sim", " esim ")
    value = value.replace("nano sim", " sim ")
    value = value.replace("nano-sim", " sim ")
    value = value.replace("nanosim", " sim ")
    value = value.replace("dualsim", " sim ")
    value = value.replace("dual sim", " sim ")
    value = value.replace("2 sim", " sim ")
    value = value.replace("2sim", " sim ")
    value = value.replace("256 gb", "256gb")
    value = value.replace("512 gb", "512gb")
    value = value.replace("128 gb", "128gb")
    value = value.replace("1 tb", "1tb")
    value = value.replace("2 tb", "2tb")
    value = re.sub(r"\b16е\b", "16e", value)
    value = re.sub(r"\b17е\b", "17e", value)

    for source, target in COLOR_ALIASES.items():
        value = value.replace(source, target)

    for phrase in MULTI_WORD_COLORS:
        value = value.replace(phrase, phrase.replace(" ", "_"))

    value = re.sub(r"[^a-z0-9_+]+", " ", value)
    tokens = []
    for token in value.split():
        token = token.replace("_", " ")
        if token in STOPWORDS:
            continue
        tokens.append(token)

    return " ".join(tokens)


def detect_esim_variant(text: str) -> Optional[bool]:
    tokens = text.split()
    if "sim" in tokens and "esim" in tokens:
        return False
    if "esim" in tokens:
        return True
    if "sim" in tokens:
        return False
    return None


def extract_storage(text: str) -> Optional[str]:
    match = re.search(r"\b(\d+)(gb|tb)\b", text)
    if match:
        return "{0}{1}".format(match.group(1), match.group(2))

    match = re.search(r"\b(128|256|512)\b", text)
    if match:
        return "{0}gb".format(match.group(1))

    return None


def extract_model(text: str) -> Optional[str]:
    tokens = text.split()
    joined = " ".join(tokens)

    if "17e" in tokens:
        return "17e"
    if "16e" in tokens:
        return "16e"
    if "17" in tokens and "air" in tokens:
        return "17 air"
    if "air" in tokens and "17" not in tokens:
        return "17 air"
    if "17" in tokens and "pro" in tokens and "max" in tokens:
        return "17 pro max"
    if "17" in tokens and "pro" in tokens:
        return "17 pro"
    if "17" in tokens:
        return "17"
    if "16" in tokens and "pro" in tokens and "max" in tokens:
        return "16 pro max"
    if "16" in tokens and "pro" in tokens:
        return "16 pro"
    if "16" in tokens and "plus" in tokens:
        return "16 plus"
    if "16" in tokens:
        return "16"
    if "15" in tokens and "plus" in tokens:
        return "15 plus"
    if "15" in tokens and "pro" in tokens and "max" in tokens:
        return "15 pro max"
    if "15" in tokens and "pro" in tokens:
        return "15 pro"
    if "15" in tokens:
        return "15"
    if "14" in tokens and "plus" in tokens:
        return "14 plus"
    if "14" in tokens and "pro" in tokens and "max" in tokens:
        return "14 pro max"
    if "14" in tokens and "pro" in tokens:
        return "14 pro"
    if "14" in tokens:
        return "14"
    if "13" in tokens:
        return "13"
    if "iphone air" in joined:
        return "17 air"

    return None


def extract_color(text: str) -> Optional[str]:
    for phrase in MULTI_WORD_COLORS:
        if phrase in text:
            return phrase

    for token in reversed(text.split()):
        if token in SIMPLE_COLORS:
            return token

    return None


def canonicalize_color(model: str, color: str) -> str:
    return MODEL_COLOR_CANONICAL_MAP.get(model, {}).get(color, color)


def normalize_availability(
    value: Optional[str],
    in_stock_patterns: Tuple[str, ...],
    out_of_stock_patterns: Tuple[str, ...],
) -> str:
    if not value:
        return "unknown"

    normalized = value.lower()
    for pattern in out_of_stock_patterns:
        if pattern in normalized:
            return "out_of_stock"
    for pattern in in_stock_patterns:
        if pattern in normalized:
            return "in_stock"
    return "unknown"


def extract_price(value: Optional[str]) -> Optional[int]:
    if not value:
        return None
    match = re.search(r"(\d[\d\s]*)", value)
    if not match:
        return None
    return int(match.group(1).replace(" ", ""))


def regex_first(html: str, pattern: str) -> Optional[str]:
    match = re.search(pattern, html, re.IGNORECASE | re.DOTALL)
    if not match:
        return None
    return match.group(1)


def html_strip(value: str) -> str:
    cleaned = re.sub(r"<[^>]+>", " ", value)
    return " ".join(cleaned.split())


def parse_ilab_catalog_query(label: str, url: str) -> ModelQuery:
    base_query = parse_model_query(label)
    esim = None
    lower_url = url.lower()
    if (
        "/iphone-17/" in lower_url
        or "/iphone-17e-esim/" in lower_url
        or "/iphone-17-pro/" in lower_url
        or "/iphone-17-pro-max/" in lower_url
    ):
        esim = True
    elif "sim-esim" in lower_url or "simesim" in lower_url:
        esim = False
    return ModelQuery(
        model=base_query.model,
        storage=base_query.storage,
        color=base_query.color,
        esim=esim,
    )


def queries_match(
    candidate: ModelQuery,
    target: ModelQuery,
    allow_unspecified_esim: bool = False,
) -> bool:
    if candidate.model != target.model:
        return False
    if candidate.storage != target.storage:
        return False
    if candidate.color != target.color:
        return False
    if target.esim is None:
        return True
    if candidate.esim == target.esim:
        return True
    if allow_unspecified_esim and candidate.esim is None:
        return True
    return False


def dedupe(values: List[str]) -> List[str]:
    seen = set()
    result = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def render_compare_report(query: object, matches: List[QueryMatch]) -> str:
    checked_sites = ", ".join(COMPARED_STORE_NAMES)
    query_name = query.display_name() if hasattr(query, "display_name") else str(query)

    if not matches:
        return "По запросу `{0}` ничего не найдено.\nПроверяем магазины: {1}".format(
            query_name,
            checked_sites,
        )

    lines = [
        "Запрос: {0}".format(query_name),
        "Магазины: {0}".format(checked_sites),
        "",
    ]
    cheapest_price = min(match.price for match in matches if match.price is not None)

    for index, match in enumerate(matches, start=1):
        cheaper_marker = "cheapest" if match.price == cheapest_price else ""
        price_text = format_money(match.price)
        old_price_text = " / без скидки {0}".format(format_money(match.old_price)) if match.old_price else ""
        availability = match.availability_text or match.availability_status
        lines.append(
            "{0}. {1}: {2}{3}".format(index, match.site_name, price_text, old_price_text)
        )
        lines.append("   {0}".format(match.name))
        lines.append("   наличие: {0}".format(availability))
        if cheaper_marker:
            lines.append("   статус: дешевле всех")
        lines.append("   ссылка: {0}".format(match.url))
        if match.note:
            lines.append("   примечание: {0}".format(match.note))
        lines.append("")

    if len(matches) > 1 and matches[0].price is not None and matches[1].price is not None:
        diff = matches[1].price - matches[0].price
        lines.append(
            "Разница между первым и вторым местом: {0}".format(format_money(diff))
        )

    return "\n".join(lines).strip()


def format_money(value: Optional[int]) -> str:
    if value is None:
        return "нет цены"
    return "{0:,} ₽".format(value).replace(",", " ")


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare Saratov store prices by a text model query.")
    parser.add_argument("--query", required=True, help='Example: "17 pro 256 silver sim"')
    args = parser.parse_args()

    query, matches = compare_query_text(args.query)
    print(render_compare_report(query, matches))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
