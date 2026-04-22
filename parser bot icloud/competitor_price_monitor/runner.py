import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from competitor_price_monitor.comparison import calculate_price_diff, choose_cheaper_side
from competitor_price_monitor.config_loader import resolve_site_key
from competitor_price_monitor.extractor import extract_product
from competitor_price_monitor.fetchers import FetchResult, PageFetcher
from competitor_price_monitor.models import AppConfig, ExtractionResult, ProductConfig, ProductRecord
from competitor_price_monitor.sinks import append_csv_history, write_csv_report, write_google_sheet
from competitor_price_monitor.snapshots import load_snapshot, save_snapshot

logger = logging.getLogger(__name__)


def run_monitor(config: AppConfig, dry_run: bool = False, disable_sheets: bool = False) -> List[ProductRecord]:
    previous_snapshot = load_snapshot(config.output.snapshot_path)
    checked_at = _current_timestamp()
    records: List[ProductRecord] = []
    snapshot_payload: Dict[str, ProductRecord] = {}
    fetcher = PageFetcher(config.defaults)

    try:
        for product in config.products:
            record = _process_product(
                product=product,
                app_config=config,
                fetcher=fetcher,
                previous_snapshot=previous_snapshot,
                checked_at=checked_at,
            )
            records.append(record)
            snapshot_payload[product.key] = record
    finally:
        fetcher.close()

    if not dry_run:
        if config.output.csv.enabled:
            write_csv_report(config.output.csv.report_path, records)
            if config.output.csv.history_path:
                append_csv_history(config.output.csv.history_path, records)

        if config.output.google_sheets.enabled and not disable_sheets:
            write_google_sheet(config.output.google_sheets, records)

        save_snapshot(config.output.snapshot_path, snapshot_payload)

    return records


def _process_product(
    product: ProductConfig,
    app_config: AppConfig,
    fetcher: PageFetcher,
    previous_snapshot: Dict[str, object],
    checked_at: str,
) -> ProductRecord:
    site_key = resolve_site_key(product, app_config.sites)
    site = app_config.sites[site_key]
    logger.info("Checking %s (%s)", product.label, product.url)

    extraction, fetch_result, error = _scrape_with_fallback(fetcher, product, site, app_config.defaults.use_playwright_on_incomplete)
    previous = previous_snapshot.get(product.key)

    price_diff_rub = calculate_price_diff(extraction.price, product.my_price)
    cheaper_side, competitor_cheaper = choose_cheaper_side(extraction.price, product.my_price)
    previous_price = getattr(previous, "competitor_price", None)
    price_changed = previous_price is not None and extraction.price is not None and previous_price != extraction.price

    status = "ok"
    message = None
    if error:
        status = "error"
        message = error
    elif not extraction.is_complete():
        status = "warning"
        message = "Missing required fields: {0}".format(", ".join(extraction.missing_required_fields))

    record = ProductRecord(
        product_key=product.key,
        product_label=product.label,
        site_key=site_key,
        url=fetch_result.final_url if fetch_result else product.url,
        checked_at=checked_at,
        scraped_name=extraction.title,
        competitor_price=extraction.price,
        competitor_old_price=extraction.original_price,
        previous_competitor_price=previous_price,
        price_changed=price_changed,
        my_price=product.my_price,
        price_diff_rub=price_diff_rub,
        cheaper_side=cheaper_side,
        competitor_cheaper=competitor_cheaper,
        availability_status=extraction.availability_status,
        availability_text=extraction.availability_text,
        renderer_used=fetch_result.renderer if fetch_result else None,
        status=status,
        error=message,
    )

    if competitor_cheaper:
        logger.warning(
            "Competitor is cheaper for %s: competitor=%s, my_price=%s",
            product.label,
            extraction.price,
            product.my_price,
        )
    elif price_changed:
        logger.info(
            "Price changed for %s: %s -> %s",
            product.label,
            previous_price,
            extraction.price,
        )

    if status == "error":
        logger.error("Failed to process %s: %s", product.label, message)

    return record


def _scrape_with_fallback(
    fetcher: PageFetcher,
    product: ProductConfig,
    site,
    use_playwright_on_incomplete: bool,
) -> Tuple[ExtractionResult, Optional[FetchResult], Optional[str]]:
    last_error = None
    fetch_result = None
    extraction = ExtractionResult()
    attempts = []

    if site.engine == "playwright":
        attempts = ["playwright"]
    elif site.engine == "http":
        attempts = ["http"]
    else:
        attempts = ["http", "playwright"] if use_playwright_on_incomplete else ["http"]

    for renderer in attempts:
        try:
            fetch_result = (
                fetcher.fetch_http(product.url, site)
                if renderer == "http"
                else fetcher.fetch_playwright(product.url, site)
            )
            extraction = extract_product(fetch_result.html, site)

            if extraction.is_complete() or renderer == attempts[-1]:
                return extraction, fetch_result, None

            logger.info(
                "Incomplete HTML parse for %s with %s, trying next renderer. Missing: %s",
                product.label,
                renderer,
                ", ".join(extraction.missing_required_fields),
            )
        except Exception as error:  # noqa: BLE001
            last_error = "{0}: {1}".format(type(error).__name__, error)
            logger.warning("Renderer %s failed for %s: %s", renderer, product.label, last_error)
            if renderer == attempts[-1]:
                break

    return extraction, fetch_result, last_error or "Unknown scraping error"


def _current_timestamp() -> str:
    return datetime.now().astimezone().replace(microsecond=0).isoformat()
