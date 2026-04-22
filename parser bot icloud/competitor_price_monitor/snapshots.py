import json
from pathlib import Path
from typing import Dict

from competitor_price_monitor.models import ProductRecord, SnapshotRecord


def load_snapshot(path: str) -> Dict[str, SnapshotRecord]:
    snapshot_path = Path(path)
    if not snapshot_path.exists():
        return {}

    with snapshot_path.open("r", encoding="utf-8") as handle:
        raw = json.load(handle)

    result = {}
    for product_key, item in raw.items():
        result[product_key] = SnapshotRecord(
            competitor_price=item.get("competitor_price"),
            checked_at=item.get("checked_at"),
        )
    return result


def save_snapshot(path: str, records: Dict[str, ProductRecord]) -> None:
    snapshot_path = Path(path)
    snapshot_path.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        key: {
            "competitor_price": record.competitor_price,
            "checked_at": record.checked_at,
        }
        for key, record in records.items()
    }

    with snapshot_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
