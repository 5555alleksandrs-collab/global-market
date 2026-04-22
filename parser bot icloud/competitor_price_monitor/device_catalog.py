from __future__ import annotations

import csv
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

from competitor_price_monitor.query_compare import ModelQuery, parse_ilab_catalog_query, parse_model_query


SOURCE_CATALOG = Path(__file__).resolve().parent / "config" / "products.ilab_template.csv"
DEFAULT_EXPORT_PATH = Path(__file__).resolve().parent / "data" / "supported_devices.csv"


@dataclass(frozen=True)
class SupportedDevice:
    key: str
    label: str
    query: str
    my_price: Optional[int]
    model: str
    storage: str
    color: str
    sim_variant: str
    url: str
    site: str
    enabled: str
    store_urls: Dict[str, str]


def load_supported_devices(source_path: Path = SOURCE_CATALOG) -> List[SupportedDevice]:
    devices: List[SupportedDevice] = []

    with source_path.open("r", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            label = (row.get("label") or "").strip()
            if not label:
                continue

            url = (row.get("url") or "").strip()
            query = build_device_query(label, url)
            parsed = try_parse_device_query(label, url)
            devices.append(
                SupportedDevice(
                    key=(row.get("key") or "").strip() or slugify_device_key(label),
                    label=label,
                    query=query,
                    my_price=parse_optional_int(row.get("my_price")),
                    model=parsed.model if parsed else "",
                    storage=parsed.storage if parsed else "",
                    color=parsed.color if parsed else "",
                    sim_variant=format_sim_variant(parsed.esim) if parsed else "not_specified",
                    url=url,
                    site=(row.get("site") or "").strip(),
                    enabled=(row.get("enabled") or "").strip(),
                    store_urls=parse_store_urls_json(row.get("store_urls_json")),
                )
            )

    return devices


def export_supported_devices_csv(
    export_path: Path = DEFAULT_EXPORT_PATH,
    source_path: Path = SOURCE_CATALOG,
) -> Path:
    devices = load_supported_devices(source_path)
    export_path.parent.mkdir(parents=True, exist_ok=True)

    with export_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "key",
                "label",
                "query",
                "model",
                "storage",
                "color",
                "sim_variant",
                "my_price",
                "site",
                "url",
                "enabled",
                "store_urls_json",
            ],
        )
        writer.writeheader()
        for device in devices:
            writer.writerow(
                {
                    "key": device.key,
                    "label": device.label,
                    "query": device.query,
                    "model": device.model,
                    "storage": device.storage,
                    "color": device.color,
                    "sim_variant": device.sim_variant,
                    "my_price": device.my_price if device.my_price is not None else "",
                    "site": device.site,
                    "url": device.url,
                    "enabled": device.enabled,
                    "store_urls_json": json.dumps(device.store_urls, ensure_ascii=False, sort_keys=True)
                    if device.store_urls
                    else "",
                }
            )

    return export_path


def parse_device_query(label: str, url: str) -> ModelQuery:
    if url:
        return parse_ilab_catalog_query(label, url)
    return parse_model_query(label)


def try_parse_device_query(label: str, url: str) -> Optional[ModelQuery]:
    try:
        return parse_device_query(label, url)
    except ValueError:
        return None


def build_device_query(label: str, url: str) -> str:
    parsed = try_parse_device_query(label, url)
    if parsed is None:
        return label.strip()
    parts = [parsed.model, parsed.storage.replace("gb", "").replace("tb", "tb"), parsed.color]
    if parsed.esim is True:
        parts.append("esim")
    elif parsed.esim is False:
        parts.append("sim")
    return " ".join(parts)


def format_sim_variant(esim: Optional[bool]) -> str:
    if esim is True:
        return "eSIM"
    if esim is False:
        return "SIM + eSIM"
    return "not_specified"


def parse_optional_int(value: Optional[str]) -> Optional[int]:
    if value is None:
        return None
    raw = str(value).strip()
    if not raw:
        return None
    normalized = raw.replace("\xa0", "").replace(" ", "")
    return int(normalized)


def slugify_device_key(label: str) -> str:
    normalized = label.lower().replace("ё", "е")
    normalized = re.sub(r"[^a-z0-9а-я]+", "-", normalized)
    normalized = re.sub(r"-{2,}", "-", normalized).strip("-")
    return normalized or "device"


def parse_store_urls_json(raw_value: Optional[str]) -> Dict[str, str]:
    raw = str(raw_value or "").strip()
    if not raw:
        return {}
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    if not isinstance(value, dict):
        return {}
    return {
        str(store_name).strip(): str(url).strip()
        for store_name, url in value.items()
        if str(store_name).strip() and str(url).strip()
    }
