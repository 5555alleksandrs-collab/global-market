from __future__ import annotations

import csv
import re
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import yaml

from competitor_price_monitor.models import (
    AppConfig,
    CsvOutputConfig,
    DefaultsConfig,
    FieldSelector,
    GoogleSheetsConfig,
    LoggingConfig,
    OutputConfig,
    ProductConfig,
    SiteConfig,
)


class ConfigError(ValueError):
    pass


def load_config(config_path: str) -> AppConfig:
    path = Path(config_path).expanduser().resolve()

    if not path.exists():
        raise ConfigError("Config file not found: {0}".format(path))

    with path.open("r", encoding="utf-8") as handle:
        raw = yaml.safe_load(handle) or {}

    base_dir = path.parent
    defaults = _parse_defaults(raw.get("defaults") or {})
    logging_config = _parse_logging(raw.get("logging") or {}, base_dir)
    output_config = _parse_output(raw.get("output") or {}, base_dir)
    sites = _parse_sites(raw.get("sites") or {}, defaults)
    products = _parse_products(raw.get("products") or [], sites)

    products_file = raw.get("products_file")
    if products_file:
        products.extend(_parse_products_csv(_resolve_path(base_dir, str(products_file)), sites))

    if not products:
        raise ConfigError("At least one product is required in config.")

    return AppConfig(
        defaults=defaults,
        logging=logging_config,
        output=output_config,
        sites=sites,
        products=products,
    )


def resolve_site_key(product: ProductConfig, sites: Dict[str, SiteConfig]) -> str:
    if product.site:
        if product.site not in sites:
            raise ConfigError(
                "Product '{0}' points to unknown site '{1}'.".format(product.key, product.site)
            )
        return product.site

    host = urlparse(product.url).netloc.lower()

    for site_key, site in sites.items():
        for domain in site.domains:
            normalized = domain.lower()
            if host == normalized or host.endswith(".{0}".format(normalized)):
                return site_key

    raise ConfigError(
        "Unable to resolve site for product '{0}'. Add `site:` or `domains:`.".format(product.key)
    )


def _parse_defaults(raw: Dict[str, Any]) -> DefaultsConfig:
    return DefaultsConfig(
        user_agent=str(raw.get("user_agent") or DefaultsConfig.user_agent),
        timeout_sec=int(raw.get("timeout_sec") or DefaultsConfig.timeout_sec),
        use_playwright_on_incomplete=bool(
            raw.get("use_playwright_on_incomplete", DefaultsConfig.use_playwright_on_incomplete)
        ),
    )


def _parse_logging(raw: Dict[str, Any], base_dir: Path) -> LoggingConfig:
    file_path = raw.get("file_path") or LoggingConfig.file_path
    return LoggingConfig(
        level=str(raw.get("level") or LoggingConfig.level).upper(),
        file_path=_resolve_path(base_dir, file_path),
    )


def _parse_output(raw: Dict[str, Any], base_dir: Path) -> OutputConfig:
    csv_raw = raw.get("csv") or {}
    sheets_raw = raw.get("google_sheets") or {}

    csv = CsvOutputConfig(
        enabled=bool(csv_raw.get("enabled", True)),
        report_path=_resolve_path(base_dir, csv_raw.get("report_path") or CsvOutputConfig.report_path),
        history_path=_resolve_optional_path(base_dir, csv_raw.get("history_path", CsvOutputConfig.history_path)),
    )
    sheets = GoogleSheetsConfig(
        enabled=bool(sheets_raw.get("enabled", False)),
        spreadsheet_id=str(sheets_raw.get("spreadsheet_id") or ""),
        worksheet_name=str(sheets_raw.get("worksheet_name") or GoogleSheetsConfig.worksheet_name),
        comparison_worksheet_name=str(
            sheets_raw.get("comparison_worksheet_name") or GoogleSheetsConfig.comparison_worksheet_name
        ),
        catalog_worksheet_name=str(
            sheets_raw.get("catalog_worksheet_name") or GoogleSheetsConfig.catalog_worksheet_name
        ),
        credentials_path=_resolve_optional_path(base_dir, sheets_raw.get("credentials_path") or ""),
    )

    return OutputConfig(
        snapshot_path=_resolve_path(base_dir, raw.get("snapshot_path") or OutputConfig.snapshot_path),
        csv=csv,
        google_sheets=sheets,
    )


def _parse_sites(raw: Dict[str, Any], defaults: DefaultsConfig) -> Dict[str, SiteConfig]:
    sites = {}

    if not raw:
        raise ConfigError("`sites` section cannot be empty.")

    for site_key, site_raw in raw.items():
        selectors_raw = site_raw.get("selectors") or {}
        availability = site_raw.get("availability") or {}
        selectors = {
            field_name: _parse_selector(field_value)
            for field_name, field_value in selectors_raw.items()
        }
        sites[site_key] = SiteConfig(
            key=site_key,
            engine=str(site_raw.get("engine") or "auto").lower(),
            domains=[str(item).lower() for item in site_raw.get("domains") or []],
            wait_for=site_raw.get("wait_for"),
            timeout_sec=int(site_raw.get("timeout_sec") or defaults.timeout_sec),
            playwright_timeout_sec=int(
                site_raw.get("playwright_timeout_sec") or site_raw.get("timeout_sec") or defaults.timeout_sec
            ),
            headers={str(key): str(value) for key, value in (site_raw.get("headers") or {}).items()},
            selectors=selectors,
            in_stock_patterns=[str(item).lower() for item in availability.get("in_stock_patterns") or []],
            out_of_stock_patterns=[str(item).lower() for item in availability.get("out_of_stock_patterns") or []],
        )

        if sites[site_key].engine not in ("auto", "http", "playwright"):
            raise ConfigError(
                "Site '{0}' has unsupported engine '{1}'.".format(
                    site_key,
                    sites[site_key].engine,
                )
            )

        if "title" not in selectors or "price" not in selectors:
            raise ConfigError("Site '{0}' must define `title` and `price` selectors.".format(site_key))

    return sites


def _parse_products(raw: List[Dict[str, Any]], sites: Dict[str, SiteConfig]) -> List[ProductConfig]:
    products = []

    for index, item in enumerate(raw):
        if not _parse_bool(item.get("enabled"), default=True):
            continue
        products.append(_build_product(item, sites, "Product at index {0}".format(index)))

    return products


def _parse_products_csv(csv_path: str, sites: Dict[str, SiteConfig]) -> List[ProductConfig]:
    path = Path(csv_path)
    if not path.exists():
        raise ConfigError("Products CSV file not found: {0}".format(path))

    products = []
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            raise ConfigError("Products CSV file is empty: {0}".format(path))

        for row_number, row in enumerate(reader, start=2):
            if not _parse_bool(row.get("enabled"), default=True):
                continue
            products.append(_build_product(row, sites, "Products CSV row {0}".format(row_number)))

    return products


def _build_product(item: Dict[str, Any], sites: Dict[str, SiteConfig], source_name: str) -> ProductConfig:
    label = str(item.get("label") or "").strip()
    key = str(item.get("key") or "").strip() or _slugify_label(label)
    url = str(item.get("url") or "").strip()

    if not label:
        raise ConfigError("{0} is missing `label`.".format(source_name))
    if not key:
        raise ConfigError("{0} is missing `key` and it could not be generated.".format(source_name))
    if not url:
        raise ConfigError("Product '{0}' is missing `url`.".format(key))

    my_price = _parse_optional_int(item.get("my_price"))
    site_key = str(item.get("site")).strip() if item.get("site") else None
    if site_key and site_key not in sites:
        raise ConfigError("Product '{0}' points to unknown site '{1}'.".format(key, site_key))

    return ProductConfig(
        key=key,
        label=label,
        url=url,
        my_price=my_price,
        site=site_key,
    )


def _parse_selector(raw: Any) -> FieldSelector:
    if isinstance(raw, str):
        selectors = [raw]
        return FieldSelector(selectors=selectors)

    if isinstance(raw, list):
        selectors = [str(item) for item in raw if str(item).strip()]
        if not selectors:
            raise ConfigError("Selector list cannot be empty.")
        return FieldSelector(selectors=selectors)

    if isinstance(raw, dict):
        selectors_raw = raw.get("selectors")
        if selectors_raw is None and raw.get("selector"):
            selectors_raw = [raw.get("selector")]

        if isinstance(selectors_raw, str):
            selectors = [selectors_raw]
        else:
            selectors = [str(item) for item in selectors_raw or [] if str(item).strip()]

        if not selectors:
            raise ConfigError("Selector config must contain `selector` or `selectors`.")

        return FieldSelector(
            selectors=selectors,
            attribute=str(raw.get("attribute") or "text"),
            regex=str(raw.get("regex")) if raw.get("regex") else None,
            required=bool(raw.get("required", False)),
            join_with=str(raw.get("join_with") or " "),
        )

    raise ConfigError("Unsupported selector config: {0!r}".format(raw))


def _resolve_path(base_dir: Path, raw_path: str) -> str:
    return str((base_dir / raw_path).expanduser().resolve())


def _resolve_optional_path(base_dir: Path, raw_path: Optional[str]) -> Optional[str]:
    if not raw_path:
        return None
    return _resolve_path(base_dir, raw_path)


def _parse_optional_int(raw: Any) -> Optional[int]:
    if raw is None:
        return None
    value = str(raw).strip()
    if not value:
        return None
    return int(value)


def _parse_bool(raw: Any, default: bool) -> bool:
    if raw is None:
        return default

    if isinstance(raw, bool):
        return raw

    value = str(raw).strip().lower()
    if not value:
        return default
    if value in ("1", "true", "yes", "y", "on"):
        return True
    if value in ("0", "false", "no", "n", "off"):
        return False

    raise ConfigError("Unable to parse boolean value: {0!r}".format(raw))


def _slugify_label(label: str) -> str:
    if not label:
        return ""

    value = label.lower()
    value = value.replace("ё", "e")
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-")
