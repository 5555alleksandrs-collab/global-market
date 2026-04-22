"""
Суффикс ключа товара (eSIM / SIM) по флагам и буквенным кодам стран в строке прайса.

Япония (🇯🇵 / Jp) — суффикс eSIM (REGION_SUFFIX_JP), как в вашей колонке A.
Корея, UK, HK, AU и др. — суффикс SIM (REGION_SUFFIX_GB), если не переопределено в .env.
"""

from __future__ import annotations

import re
from typing import Iterator

import config


def _iter_flag_emojis(s: str) -> Iterator[str]:
    """Пары Regional Indicator (флаги Unicode) в порядке слева направо."""
    i = 0
    while i < len(s) - 1:
        a, b = ord(s[i]), ord(s[i + 1])
        if 0x1F1E6 <= a <= 0x1F1FF and 0x1F1E6 <= b <= 0x1F1FF:
            yield s[i : i + 2]
            i += 2
        else:
            i += 1


# Флаг → «ведро»: esim | sim (далее маппится в REGION_SUFFIX_* из .env)
_FLAG_BUCKET: dict[str, str] = {
    # eSIM (US, CA/MX, Япония — как в колонке A)
    "🇺🇸": "esim",
    "🇯🇵": "esim",
    "🇨🇦": "esim",
    "🇲🇽": "esim",
    "🇰🇷": "sim",
    # Физическая SIM / dual SIM / классическая EU-UK-ME поставка
    "🇬🇧": "sim",
    "🇭🇰": "sim",
    "🇲🇴": "sim",
    "🇨🇳": "sim",
    "🇦🇺": "sim",
    "🇳🇿": "sim",
    "🇸🇬": "sim",
    "🇲🇾": "sim",
    "🇹🇭": "sim",
    "🇻🇳": "sim",
    "🇵🇭": "sim",
    "🇮🇩": "sim",
    "🇮🇳": "sim",
    "🇧🇿": "sim",
    "🇦🇪": "sim",
    "🇪🇺": "sim",
    "🇩🇪": "sim",
    "🇫🇷": "sim",
    "🇮🇹": "sim",
    "🇪🇸": "sim",
    "🇵🇱": "sim",
    "🇷🇺": "sim",
    "🇺🇦": "sim",
    "🇹🇷": "sim",
}

# Текстовые коды (как в прайсах: Kr, Uk, HK, Aus, US, …)
_TOKEN_BUCKET: dict[str, str] = {
    "us": "esim",
    "usa": "esim",
    "jp": "esim",
    "jpn": "esim",
    "kr": "sim",
    "kor": "sim",
    "ca": "esim",
    "can": "esim",
    "mx": "esim",
    "uk": "sim",
    "gb": "sim",
    "hk": "sim",
    "hkg": "sim",
    "aus": "sim",
    "au": "sim",
    "eu": "sim",
    "ru": "sim",
    "uae": "sim",
    "ae": "sim",
    "me": "sim",
    "bz": "sim",
    "nz": "sim",
    "de": "sim",
    "fr": "sim",
    "it": "sim",
    "es": "sim",
    "pl": "sim",
    "india": "sim",
}

_TOKEN_RE = re.compile(
    r"\b(US|USA|JP|JPN|KR|KOR|UK|GB|HK|HKG|AUS|AU|EU|RU|AE|UAE|ME|CA|CAN|MX|BZ|"
    r"Kr|Uk|Jp|Aus|Hk|Us|Nz|India)\b",
    re.I,
)


def _bucket_to_suffix(bucket: str) -> str:
    if bucket == "esim":
        return (config.REGION_SUFFIX_JP or "eSIM").strip()
    return (config.REGION_SUFFIX_GB or "SIM").strip()


def infer_suffix_from_pricelist_line(line: str) -> str | None:
    """
    Определяет суффикс только по содержимому строки (флаги и коды).
    Если неизвестно — None (тогда используется секция из строки-шапки 🇯🇵/🇬🇧).

    Символ Apple (U+F8FF) и 🍎 в прайсах часто означают US-spec / eSIM — приоритет
    над текстовым Aus/Uk, если флага страны нет.
    """
    if not (line or "").strip():
        return None
    if "\uf8ff" in line or "🍎" in line:
        return _bucket_to_suffix("esim")
    for flag in _iter_flag_emojis(line):
        b = _FLAG_BUCKET.get(flag)
        if b:
            return _bucket_to_suffix(b)
    for m in _TOKEN_RE.finditer(line):
        tok = m.group(1).lower()
        b = _TOKEN_BUCKET.get(tok)
        if b:
            return _bucket_to_suffix(b)
    return None


def _section_is_iphone_air_esim_only(section_model: str | None) -> bool:
    """iPhone 17 Air в практике только eSIM (без переключения на SIM по стране)."""
    if not section_model:
        return False
    sm = section_model.lower()
    if "ipad" in sm or "mac" in sm:
        return False
    return "air" in sm and "17" in sm


def effective_region_for_row(
    line: str,
    header_fallback: str | None,
    section_model: str | None,
) -> str | None:
    """
    Итоговый суффикс для ключа: сначала явные маркеры в строке, иначе шапка секции,
    с учётом исключения для 17 Air.
    """
    if _section_is_iphone_air_esim_only(section_model):
        return (config.REGION_SUFFIX_JP or "eSIM").strip()
    per_line = infer_suffix_from_pricelist_line(line)
    if per_line is not None:
        return per_line
    return header_fallback
