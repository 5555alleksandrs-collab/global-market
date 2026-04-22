import argparse
import logging
from pathlib import Path

from competitor_price_monitor.config_loader import ConfigError, load_config
from competitor_price_monitor.logging_setup import setup_logging
from competitor_price_monitor.runner import run_monitor


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Bot for monitoring competitor prices on Apple devices and accessories."
    )
    parser.add_argument(
        "--config",
        default=str(Path(__file__).resolve().parent / "config" / "settings.yaml"),
        help="Path to YAML config.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run scraping and comparison without saving CSV / Google Sheets / snapshot.",
    )
    parser.add_argument(
        "--no-sheets",
        action="store_true",
        help="Disable Google Sheets export for this run.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable debug logs.",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    try:
        config = load_config(args.config)
    except ConfigError as error:
        parser.error(str(error))
        return 2

    setup_logging(config.logging, verbose=args.verbose)
    logger = logging.getLogger(__name__)

    try:
        records = run_monitor(config, dry_run=args.dry_run, disable_sheets=args.no_sheets)
    except Exception as error:  # noqa: BLE001
        logger.exception("Monitoring run failed: %s", error)
        return 1

    total = len(records)
    cheaper = sum(1 for record in records if record.competitor_cheaper)
    changed = sum(1 for record in records if record.price_changed)
    failed = sum(1 for record in records if record.status == "error")

    logger.info(
        "Done. Checked=%s, competitor_cheaper=%s, price_changed=%s, failed=%s",
        total,
        cheaper,
        changed,
        failed,
    )
    return 0
