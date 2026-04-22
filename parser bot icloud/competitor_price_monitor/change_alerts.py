from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Sequence

from competitor_price_monitor.device_catalog import SOURCE_CATALOG, load_supported_devices


@dataclass(frozen=True)
class PriceChangeEvent:
    model: str
    store_name: str
    old_price: int
    new_price: int
    diff_rub: int
    my_price: Optional[int]
    cheaper_than_me: bool
    became_cheaper_than_me: bool
    url: str


def load_price_change_events(
    details_path: Path,
    source_path: Path = SOURCE_CATALOG,
) -> List[PriceChangeEvent]:
    if not details_path.exists():
        return []

    devices_by_label = {device.label: device for device in load_supported_devices(source_path)}
    raw_entries = json.loads(details_path.read_text(encoding="utf-8"))
    events: List[PriceChangeEvent] = []

    for entry in raw_entries:
        model = str(entry.get("label") or "").strip()
        if not model:
            continue

        device = devices_by_label.get(model)
        my_price = _coalesce_int(entry.get("my_price"))
        if my_price is None and device:
            my_price = device.my_price

        for match in entry.get("matches") or []:
            store_name = str(match.get("site_name") or "").strip()
            new_price = _coalesce_int(match.get("price"))
            old_price = _coalesce_int(match.get("previous_price"))
            if not store_name or new_price is None or old_price is None or new_price == old_price:
                continue

            cheaper_than_me = my_price is not None and new_price < my_price
            became_cheaper_than_me = (
                my_price is not None
                and old_price >= my_price
                and new_price < my_price
            )
            events.append(
                PriceChangeEvent(
                    model=model,
                    store_name=store_name,
                    old_price=old_price,
                    new_price=new_price,
                    diff_rub=new_price - old_price,
                    my_price=my_price,
                    cheaper_than_me=cheaper_than_me,
                    became_cheaper_than_me=became_cheaper_than_me,
                    url=str(match.get("url") or "").strip(),
                )
            )

    events.sort(
        key=lambda event: (
            not event.became_cheaper_than_me,
            not event.cheaper_than_me,
            abs(event.diff_rub) * -1,
            event.model,
            event.store_name,
        )
    )
    return events


def format_price_change_messages(
    events: Sequence[PriceChangeEvent],
    spreadsheet_url: Optional[str] = None,
    max_lines_per_message: int = 12,
) -> List[str]:
    if not events:
        return []

    messages: List[str] = []
    current_lines: List[str] = []
    header = "Автообновление цен: {0} изменений.".format(len(events))

    for event in events:
        line = _format_event_line(event)
        if len(current_lines) >= max_lines_per_message:
            messages.append(_join_message(header if not messages else "Продолжение автообновления цен:", current_lines))
            current_lines = []
        current_lines.append(line)

    if current_lines:
        messages.append(_join_message(header if not messages else "Продолжение автообновления цен:", current_lines))

    if spreadsheet_url and messages:
        messages[-1] = "{0}\n\nТаблица: {1}".format(messages[-1], spreadsheet_url)

    return messages


def _format_event_line(event: PriceChangeEvent) -> str:
    delta = _format_signed_money(event.diff_rub)
    line = "• {0} | {1}: {2} -> {3} ({4})".format(
        event.model,
        event.store_name,
        _format_money(event.old_price),
        _format_money(event.new_price),
        delta,
    )

    if event.my_price is not None and event.became_cheaper_than_me:
        line += " | стал дешевле вашей на {0}".format(
            _format_money(event.my_price - event.new_price)
        )
    elif event.my_price is not None and event.cheaper_than_me:
        line += " | дешевле вашей на {0}".format(
            _format_money(event.my_price - event.new_price)
        )

    return line


def _join_message(header: str, lines: Sequence[str]) -> str:
    return "{0}\n{1}".format(header, "\n".join(lines))


def _coalesce_int(value) -> Optional[int]:
    if value is None:
        return None
    raw = str(value).strip()
    if not raw:
        return None
    return int(raw)


def _format_money(value: int) -> str:
    return "{0:,}".format(value).replace(",", " ")


def _format_signed_money(value: int) -> str:
    if value == 0:
        return "0"
    sign = "+" if value > 0 else "-"
    return "{0}{1}".format(sign, _format_money(abs(value)))


__all__ = [
    "PriceChangeEvent",
    "format_price_change_messages",
    "load_price_change_events",
]
