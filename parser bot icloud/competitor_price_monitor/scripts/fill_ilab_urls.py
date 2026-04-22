#!/usr/bin/env python3

from __future__ import annotations

import argparse
import csv
import re
from collections import deque
from html.parser import HTMLParser
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

BASE_URL = "https://ilabstore.ru/catalog/iphone/"
USER_AGENT = "Mozilla/5.0"


class LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: List[Tuple[str, str]] = []
        self._href: Optional[str] = None
        self._text_parts: List[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag != "a":
            return
        attributes = dict(attrs)
        self._href = attributes.get("href")
        self._text_parts = []

    def handle_data(self, data: str) -> None:
        if self._href is None:
            return
        self._text_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag != "a" or self._href is None:
            return
        text = " ".join("".join(self._text_parts).split())
        self.links.append((self._href, text))
        self._href = None
        self._text_parts = []


def fetch(url: str) -> str:
    request = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(request, timeout=20) as response:
        return response.read().decode("utf-8", "ignore")


def is_under_iphone(url: str) -> bool:
    return url.startswith(BASE_URL)


def path_depth(url: str) -> int:
    parts = [part for part in urlparse(url).path.split("/") if part]
    return len(parts)


def crawl_ilab_products() -> Dict[Tuple[str, str, str, bool], str]:
    queue = deque([BASE_URL])
    visited: Set[str] = set()
    products: Dict[Tuple[str, str, str, bool], str] = {}

    while queue:
        current_url = queue.popleft()
        if current_url in visited:
            continue

        visited.add(current_url)
        html = fetch(current_url)
        parser = LinkParser()
        parser.feed(html)

        for href, text in parser.links:
            if not href:
                continue

            absolute_url = urljoin(current_url, href).split("#", 1)[0]
            if not is_under_iphone(absolute_url):
                continue

            if "/page/" in absolute_url or path_depth(absolute_url) == 3:
                if absolute_url not in visited:
                    queue.append(absolute_url)
                continue

            if path_depth(absolute_url) < 4 or not text:
                continue

            parsed = parse_product_label(text)
            if not parsed:
                continue

            products[parsed] = absolute_url

    return products


def parse_product_label(label: str) -> Optional[Tuple[str, str, str, bool]]:
    text = label.lower()
    text = text.replace("ё", "e").replace("е", "e")
    text = text.replace("cosmic orange", "orange")
    text = text.replace("soft pink", "pink")
    text = text.replace("natural titanium", "natural")
    text = text.replace("desert titanium", "desert")
    text = text.replace("black titanium", "black")
    text = text.replace("white titanium", "white")
    text = text.replace("titanium", " ")
    text = text.replace("(sim + esim)", " ")
    text = text.replace("(sim+esim)", " ")
    text = text.replace("(esim)", " esim ")
    text = text.replace("(e-sim)", " esim ")
    text = text.replace("e-sim", "esim")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    tokens = [token for token in text.split() if token != "iphone"]

    if not tokens:
        return None

    esim = "esim" in tokens
    tokens = [token for token in tokens if token not in {"sim", "esim"}]
    if not tokens:
        return None

    model_parts = [tokens.pop(0)]
    while tokens and tokens[0] in {"plus", "pro", "max", "air"}:
        model_parts.append(tokens.pop(0))

    if model_parts == ["17", "air"]:
        model_parts = ["air"]

    if not tokens:
        return None

    storage_token = tokens.pop(0)
    if re.fullmatch(r"\d+", storage_token):
        storage = "{0}gb".format(storage_token)
    elif re.fullmatch(r"\d+(gb|tb)", storage_token):
        storage = storage_token
    else:
        return None

    color = " ".join(tokens).strip()
    if not color:
        return None

    model = " ".join(model_parts)
    return model, storage, color, esim


def fill_csv(csv_path: Path, products: Dict[Tuple[str, str, str, bool], str]) -> Tuple[int, List[str]]:
    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = reader.fieldnames or []
        rows = list(reader)

    unmatched: List[str] = []
    updated = 0

    for row in rows:
        parsed = parse_product_label(row.get("label", ""))
        if not parsed:
            unmatched.append(row.get("label", ""))
            continue

        url = products.get(parsed)
        if not url:
            unmatched.append(row.get("label", ""))
            continue

        if row.get("url") != url:
            row["url"] = url
            updated += 1

    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    return updated, unmatched


def main() -> int:
    parser = argparse.ArgumentParser(description="Fill direct iLab product URLs into a CSV file.")
    parser.add_argument(
        "--csv",
        default="competitor_price_monitor/config/products.ilab_template.csv",
        help="Path to products CSV.",
    )
    args = parser.parse_args()

    csv_path = Path(args.csv).expanduser().resolve()
    products = crawl_ilab_products()
    updated, unmatched = fill_csv(csv_path, products)

    print("matched_urls={0}".format(updated))
    print("unmatched={0}".format(len(unmatched)))
    for label in unmatched:
        print("UNMATCHED {0}".format(label))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
