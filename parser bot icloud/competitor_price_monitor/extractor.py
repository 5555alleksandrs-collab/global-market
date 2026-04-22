import logging
import re
from typing import Iterable, Optional

from bs4 import BeautifulSoup

from competitor_price_monitor.models import ExtractionResult, FieldSelector, SiteConfig

logger = logging.getLogger(__name__)


def extract_product(html: str, site: SiteConfig) -> ExtractionResult:
    soup = BeautifulSoup(html, "html.parser")
    result = ExtractionResult()

    title = _extract_text(soup, site.selectors.get("title"))
    price_text = _extract_text(soup, site.selectors.get("price"))
    original_price_text = _extract_text(soup, site.selectors.get("original_price"))
    availability_text = _extract_text(soup, site.selectors.get("availability"))

    result.title = title
    result.price = _extract_price(price_text)
    result.original_price = _extract_price(original_price_text)
    result.availability_text = availability_text
    result.availability_status = _normalize_availability(availability_text, site)

    title_selector = site.selectors.get("title")
    if title_selector and title_selector.required and not result.title:
        result.missing_required_fields.append("title")

    price_selector = site.selectors.get("price")
    if price_selector and price_selector.required and result.price is None:
        result.missing_required_fields.append("price")

    return result


def _extract_text(soup: BeautifulSoup, selector: Optional[FieldSelector]) -> Optional[str]:
    if not selector:
        return None

    for css_selector in selector.selectors:
        nodes = soup.select(css_selector)
        if not nodes:
            continue

        value = _collect_node_values(nodes, selector)
        if not value:
            continue

        if selector.regex:
            match = re.search(selector.regex, value, flags=re.IGNORECASE | re.DOTALL)
            if not match:
                continue
            value = match.group(1) if match.groups() else match.group(0)

        normalized = " ".join(value.split())
        if normalized:
            return normalized

    return None


def _collect_node_values(nodes: Iterable, selector: FieldSelector) -> str:
    values = []

    for node in nodes:
        if selector.attribute == "text":
            values.append(node.get_text(" ", strip=True))
            continue

        attribute_value = node.get(selector.attribute)
        if attribute_value:
            values.append(str(attribute_value).strip())

    return selector.join_with.join(item for item in values if item)


def _extract_price(value: Optional[str]) -> Optional[int]:
    if not value:
        return None

    normalized = value.replace("\xa0", " ").strip()
    match = re.search(r"(\d[\d\s.,]*)", normalized)
    if not match:
        return None

    number = match.group(1).replace(" ", "")
    decimal_match = re.fullmatch(r"(\d+)([.,]\d{1,2})", number)
    if decimal_match:
        return int(decimal_match.group(1))

    digits = re.findall(r"\d+", number)
    if not digits:
        return None

    return int("".join(digits))


def _normalize_availability(value: Optional[str], site: SiteConfig) -> str:
    if not value:
        return "unknown"

    normalized = value.lower()
    out_patterns = [str(pattern).lower() for pattern in site.out_of_stock_patterns]
    in_patterns = [str(pattern).lower() for pattern in site.in_stock_patterns]
    if any(pattern in normalized for pattern in out_patterns):
        return "out_of_stock"
    if any(pattern in normalized for pattern in in_patterns):
        return "in_stock"

    logger.debug("Availability text did not match configured patterns: %s", value)
    return "unknown"
