"""
Парсинг прайс-листов в стиле Telegram: секции «модель @цена$», строки «цвет qty»,
«цвет qty x цена$»; суффикс eSIM/SIM по строке (флаги, Kr/HK/Uk/…), шапке 🇯🇵/🇬🇧
или текстовой строке («SIM» / «eSIM» / «1 SIM» / «есим»).
"""

from __future__ import annotations

import re
from typing import List, Tuple

import config
from column_match import normalize_for_sheet_match
from sim_region import effective_region_for_row


def normalize_spaces(s: str) -> str:
    s = (s or "").replace("\u00a0", " ").strip()
    s = re.sub(r"\s+", " ", s)
    return s


def _strip_line_markdown_wrappers(s: str) -> str:
    """Обёртки *…* / _…_ в строках прайса Telegram."""
    t = (s or "").strip()
    t = re.sub(r"^[*_`]+", "", t)
    t = re.sub(r"[*_`]+$", "", t)
    return t.strip()


def _strip_tail_line_noise(line: str) -> str:
    """Хвост «coming», «sold» и т.п. не даёт распарсить цену."""
    s = line.strip()
    s = re.sub(r"\s+\b(coming|soon|sold|inactive|hold)\b\s*$", "", s, flags=re.I)
    return s.strip()


def _parse_color_qty_tail_price_line(line: str) -> tuple[str, float] | None:
    """
    Строки вида: Orange 50 Kr 🇰🇷 1580, Blue 12 Aus 🇦🇺 $1580, Blue 100+ usa $1172
    (цена последним числом; количество — 12 или 100+).
    """
    line = _strip_tail_line_noise(line)
    if " x " in line.lower() and re.search(r"\d\s*x\s*[\d.]", line):
        return None
    if re.search(r"@\s*[\d.]+\s*\$", line):
        return None
    if "=" in line and re.search(r"\w+\s*=\s*\d", line):
        return None
    # qty: «100+» или «55»
    m_qty = re.match(r"^(.+?)\s+(\d+)\+\s+", line) or re.match(
        r"^(.+?)\s+(\d+)\s+", line
    )
    if not m_qty:
        return None
    color = m_qty.group(1).strip()
    try:
        qty_val = float(m_qty.group(2))
    except ValueError:
        return None
    nums = re.findall(r"[\d.]+", line)
    if len(nums) < 2:
        return None
    try:
        price = float(nums[-1])
    except ValueError:
        return None
    if price < 50:
        return None
    if price <= qty_val:
        return None
    if re.search(r"\b(GB|TB)\b", color, re.I) or re.search(
        r"\b\d+\s*(GB|TB)\b", line, re.I
    ):
        return None
    return _canonical_color_token(color), price


# Частые опечатки цветов в «грязных» прайсах Telegram
_COLOR_TYPO_TO_CANONICAL = {
    "glod": "gold",
    "balck": "black",
    "levander": "lavender",
    "sliver": "silver",
    "ornge": "orange",
    "ornage": "orange",
}


def _canonical_color_token(color: str) -> str:
    """Первая лексема цвета — подмена опечаток (Glod → Gold)."""
    parts = color.strip().split()
    if not parts:
        return color.strip()
    first = parts[0].lower()
    if first in _COLOR_TYPO_TO_CANONICAL:
        parts[0] = _COLOR_TYPO_TO_CANONICAL[first]
    return " ".join(parts)


def _strip_section_junk_and_price(line: str) -> tuple[str, float | None]:
    """
    Заголовок секции: убрать хвост «$735», фразы «must take mix» и лишние пробелы.
    """
    s = normalize_spaces(line)
    s = re.sub(r"\bmust\s+take\s+mix\b", "", s, flags=re.I)
    s = re.sub(r"\bready\s+stock\b", "", s, flags=re.I)
    s = normalize_spaces(s)
    price: float | None = None
    # хвост «… $735» — цена после $, не ([\d.]+) слева (иначе ловится «17» в IPHONE 17 …)
    m = re.search(r"\s*\$([\d.]+)\s*$", s)
    if m:
        try:
            price = float(m.group(1))
        except ValueError:
            price = None
        s = s[: m.start()].strip()
        s = normalize_spaces(s)
    return s, price


def _parse_equals_color_price_line(line: str) -> tuple[str, float | None] | None:
    """
    Строки вида: White =60 $865, Blue=82 $860, Orange=100+$1465, Blue=30$2175,
    Balck=100+, Black=19 (только количество — цена с секции).
    """
    s = line.strip()
    if "=" not in s:
        return None
    # не цветовая строка, а заголовок с объёмом
    if re.search(r"\b\d+\s*(GB|TB)\b", s, re.I):
        return None
    # Orange=100+$1465
    m = re.match(
        r"^(.+?)\s*=\s*(\d+)\s*\+\s*\$?\s*([\d.]+)\s*$",
        s,
        re.I,
    )
    if m:
        return _canonical_color_token(m.group(1).strip()), float(m.group(3))
    # Blue=30$2175
    m = re.match(r"^(.+?)\s*=\s*(\d+)\s*\$([\d.]+)\s*$", s, re.I)
    if m:
        return _canonical_color_token(m.group(1).strip()), float(m.group(3))
    # Orange=66 $1575 / White =60 $865 (есть пробел перед $)
    m = re.match(r"^(.+?)\s*=\s*(\d+)\s+\$?\s*([\d.]+)\s*$", s, re.I)
    if m:
        return _canonical_color_token(m.group(1).strip()), float(m.group(3))
    # Balck=100+
    m = re.match(r"^(.+?)\s*=\s*(\d+)\s*\+\s*$", s, re.I)
    if m:
        return _canonical_color_token(m.group(1).strip()), None
    # Black=19, Blue=4
    m = re.match(r"^(.+?)\s*=\s*(\d+)\s*$", s, re.I)
    if m:
        return _canonical_color_token(m.group(1).strip()), None
    return None


def make_product_key(section_model: str, color: str, region: str | None = None) -> str:
    sm = normalize_for_sheet_match(section_model)
    cl = normalize_for_sheet_match(color)
    base = normalize_spaces(f"{sm} {cl}")
    if region:
        r = normalize_for_sheet_match(region.strip())
        return normalize_spaces(f"{base} {r}")
    return base


def _line_looks_like_mac_product(line: str) -> bool:
    """Одна строка = один товар (MacBook / Mac mini / iMac), не секция iPhone."""
    return bool(
        re.search(
            r"(Macbook|MacBook|Mac mini|Mac Pro|Mac Studio|iMac)",
            line,
            re.IGNORECASE,
        )
    )


def _line_looks_like_single_line_storage_product(line: str) -> bool:
    """Одна строка: iPad / iPhone / Mac с объёмом и ценой в конце (частые прайсы)."""
    return bool(
        re.search(
            r"\b(ipad|iphone|macbook|mac mini|imac)\b",
            line,
            re.IGNORECASE,
        )
    )


def _is_flag_only_header_line(line: str) -> bool:
    """Строка из повторяющихся 🇯🇵 / 🇬🇧 без текста прайса."""
    s = line.strip()
    n_flags = s.count("🇯🇵") + s.count("🇬🇧")
    if n_flags < 3:
        return False
    if "$" in s or re.search(r"@\s*\d", s):
        return False
    if re.search(r"\b\d+\s*(GB|TB)\b", s, re.I):
        return False
    if re.search(r"\b\d{3,}\b", s):
        return False
    if re.search(r"[a-z]{4,}", s, re.I):
        return False
    return True


def _region_from_flag_header_line(line: str) -> str | None:
    """Шапка из флагов: 🇯🇵 → eSIM, 🇬🇧 → SIM (значения из .env)."""
    if not _is_flag_only_header_line(line):
        return None
    jp = line.count("🇯🇵")
    gb = line.count("🇬🇧")
    if jp == 0 and gb == 0:
        return None
    if jp > gb:
        return config.REGION_SUFFIX_JP
    if gb > jp:
        return config.REGION_SUFFIX_GB
    return None


def _line_looks_like_plain_sim_esim_banner(line: str) -> bool:
    """
    Строка-курсор секции (без модели/объёма/цены): «ниже ESIM», «1 SIM», «--- SIM ---».
    Не путать с «Black 45», «Orange=60», строками с GB/TB.
    """
    s = normalize_spaces(line)
    if len(s) > 120:
        return False
    if re.search(r"\b\d+\s*(GB|TB)\b", s, re.I):
        return False
    if re.search(r"@\s*[\d.]+\s*\$", s):
        return False
    if re.search(r"=\s*\d+", s):
        return False
    if re.search(r"\b\d+\s*x\s*[\d.]+\s*\$", s, re.I):
        return False
    # «Black 45» — цвет + остаток, не шапка; но «SIM 1» / «ESIM 2» — это шапка секции
    m_qty = re.match(r"^(.+?)\s+(\d+)\s*$", s)
    if m_qty and not re.search(r"\b(GB|TB)\b", s, re.I):
        left = m_qty.group(1).strip().lower()
        if left not in ("sim", "esim"):
            return False
    return True


def _region_from_text_section_header(line: str) -> str | None:
    """
    Текстовая шапка: «далее eSIM», «SIM», «1 SIM nano», «ЕСИМ» — без флагов в строке.
    eSIM проверяем раньше, чем отдельное слово «sim» (часть «esim»).

    Важно: не считать шапкой строки с моделью/товаром (Orange 5 SIM, 17 Pro …).
    """
    if not _line_looks_like_plain_sim_esim_banner(line):
        return None
    s = normalize_spaces(line)
    s_low = s.lower()

    # Строка позиции «цвет + qty + SIM/eSIM» — не шапка секции
    if re.match(r"^(.+?)\s+(\d+)\s+(sim|esim)\s*$", s_low):
        return None

    # Описание товара, не курсор секции
    if re.search(r"\bsim\b", s_low) and re.search(r"\bfree\b", s_low):
        return None
    if re.search(r"\b(iphone|ipad)\b", s_low) and re.search(
        r"\b(physical|nano)\s+sim\b", s_low
    ):
        return None
    # Строка с моделью — не отдельная шапка «SIM»
    if re.search(r"\b(iphone|ipad|macbook|imac)\b", s_low):
        return None
    if re.search(r"^\d+\s+(pro|max|air|pro\s*max|e)\b", s_low):
        return None

    # «JAPAN ,USA E - SIM» / «E-SIM» — eSIM; иначе «… sim» даёт физическую SIM.
    # «UK , KR , HK 1-SIM» — физическая SIM (1-SIM).
    if re.search(r"\be\s*[-\u2013]?\s*sim\b", s_low):
        return config.REGION_SUFFIX_JP
    if re.search(r"\b1\s*[-\u2013]?\s*sim\b", s_low):
        return config.REGION_SUFFIX_GB

    # Уже покрыто отдельными ветками, но дубли не мешают
    if re.search(r"esim\s*\+\s*esim", s_low):
        return config.REGION_SUFFIX_JP
    if re.search(r"1\s*sim\s*nano|nano\s*\+\s*esim|1\s*sim\s*\+", s_low):
        return config.REGION_SUFFIX_GB

    # Рус.: «далее есим» / одно слово
    if re.search(r"\b(далее|ниже|только)\s+есим\b", s_low):
        return config.REGION_SUFFIX_JP
    if re.search(r"\b(далее|ниже|только)\s+сим\b", s_low) and "есим" not in s_low:
        return config.REGION_SUFFIX_GB
    if re.match(r"^[\s\-=*.#]*есим\s*$", s_low):
        return config.REGION_SUFFIX_JP
    if re.match(r"^[\s\-=*.#]*сим\s*$", s_low):
        return config.REGION_SUFFIX_GB

    # Латиница: фразы «next esim» / одна строка — только esim/sim
    if re.search(r"\b(далее|ниже|только|next|below)\s+esim\b", s_low):
        return config.REGION_SUFFIX_JP
    if re.search(r"\b(далее|ниже|только|next|below)\s+sim\b", s_low):
        return config.REGION_SUFFIX_GB
    if re.match(r"^[\s\-=*.#]*(?:e-?sim|esim)\s*[\s\-=*.#]*$", s_low):
        return config.REGION_SUFFIX_JP

    s_no_esim = re.sub(r"\besim\b", " ", s_low)
    if re.match(r"^[\s\-=*.#]*sim\s*[\s\-=*.#]*$", s_no_esim):
        return config.REGION_SUFFIX_GB
    if re.search(r"\b(1|2|dual|physical|nano)\s*sim\b", s_no_esim):
        return config.REGION_SUFFIX_GB
    # Короткая строка с sim/esim без лишних слов (не «… long text … sim …»)
    if re.search(r"\besim\b", s_low) and len(s) <= 56:
        return config.REGION_SUFFIX_JP
    if re.search(r"\bsim\b", s_no_esim) and len(s) <= 56:
        return config.REGION_SUFFIX_GB

    return None


def parse_telegram_pricelist(text: str) -> List[Tuple[str, float]]:
    """
    Возвращает список (ключ товара для колонки A, цена в $).

    Ключ: «секция + цвет» + суффикс eSIM/SIM: по строке (флаг Kr/HK/UK/US/…)
    или по шапке секции 🇯🇵/🇬🇧; для iPhone 17 Air — всегда eSIM.
    """
    out: List[Tuple[str, float]] = []
    section_model: str | None = None
    base_price: float | None = None
    region_suffix: str | None = None

    for raw in (text or "").splitlines():
        line = _strip_line_markdown_wrappers(raw.strip())
        if not line:
            continue

        reg = _region_from_flag_header_line(line)
        if reg is not None:
            region_suffix = reg
            continue

        reg_text = _region_from_text_section_header(line)
        if reg_text is not None:
            region_suffix = reg_text
            continue

        # только эмодзи / разделители без букв и цен
        if not re.search(r"[A-Za-z0-9А-Яа-я@$]", line):
            continue
        if re.search(r"ready\s*stock", line, re.I) and not re.search(
            r"\b\d+\s*(GB|TB)\b", line, re.I
        ):
            continue

        # 1) MD3Y4 - Silver ✔️ 5 x 316$ — до общего «цвет qty x цена», иначе спутывается с Orange 60 x
        m_sku = re.match(
            r"^([A-Z0-9]{4,})\s*[-–]\s*(.+?)\s+(\d+)\s*x\s*([\d.]+)\s*\$\s*$",
            line,
            re.IGNORECASE,
        )
        if m_sku:
            sku = m_sku.group(1).strip()
            color_part = re.sub(r"[\s🔸✔️]+$", "", m_sku.group(2).strip())
            price = float(m_sku.group(4))
            tail = f"{sku} {color_part}".strip()
            if section_model:
                out.append(
                    (
                        make_product_key(
                            section_model,
                            tail,
                            effective_region_for_row(line, region_suffix, section_model),
                        ),
                        price,
                    )
                )
            else:
                out.append(
                    (
                        make_product_key(
                            tail,
                            "",
                            effective_region_for_row(line, region_suffix, None),
                        ),
                        price,
                    )
                )
            continue

        # 2) Orange 60 x 1175$
        m = re.match(r"^(.+?)\s+(\d+)\s*x\s*([\d.]+)\s*\$\s*$", line, re.IGNORECASE)
        if m:
            color = m.group(1).strip()
            price = float(m.group(3))
            if section_model:
                out.append(
                    (
                        make_product_key(
                            section_model,
                            color,
                            effective_region_for_row(line, region_suffix, section_model),
                        ),
                        price,
                    )
                )
            continue

        # 2b) Orange 50 Kr 🇰🇷 1580 / Blue 12 Aus 🇦🇺 $1580 — без «x», цена в конце
        if section_model:
            tail_p = _parse_color_qty_tail_price_line(line)
            if tail_p is not None:
                color, price = tail_p
                out.append(
                    (
                        make_product_key(
                            section_model,
                            color,
                            effective_region_for_row(line, region_suffix, section_model),
                        ),
                        price,
                    )
                )
                continue

        # 4) White (4 x 775$)
        m = re.match(
            r"^(.+?)\s*\(\s*(\d+)\s*x\s*([\d.]+)\s*\$\s*\)\s*$",
            line,
            re.IGNORECASE,
        )
        if m:
            color = m.group(1).strip()
            price = float(m.group(3))
            if section_model:
                out.append(
                    (
                        make_product_key(
                            section_model,
                            color,
                            effective_region_for_row(line, region_suffix, section_model),
                        ),
                        price,
                    )
                )
            continue

        # 5a) MacBook … @2 x 1485$
        m = re.match(r"^(.+?)\s*@\s*(\d+)\s*x\s*([\d.]+)\s*\$\s*$", line, re.IGNORECASE)
        if m:
            section_model = normalize_for_sheet_match(m.group(1))
            base_price = float(m.group(3))
            if _line_looks_like_mac_product(line):
                out.append(
                    (
                        make_product_key(
                            section_model,
                            "",
                            effective_region_for_row(line, region_suffix, section_model),
                        ),
                        base_price,
                    )
                )
            continue

        # 3b) @2 x 1485$
        m = re.match(r"^@\s*(\d+)\s*x\s*([\d.]+)\s*\$\s*$", line, re.IGNORECASE)
        if m and section_model:
            qty = int(m.group(1))
            price = float(m.group(2))
            base_price = price
            out.append(
                (
                    make_product_key(
                        section_model,
                        f"@{qty}x",
                        effective_region_for_row(line, region_suffix, section_model),
                    ),
                    price,
                )
            )
            continue

        # 3c) iPhone 17e 256GB @573$
        m = re.match(r"^(.+?)\s*@\s*([\d.]+)\s*\$\s*$", line)
        if m:
            section_model = normalize_for_sheet_match(m.group(1))
            base_price = float(m.group(2))
            if _line_looks_like_mac_product(line):
                out.append(
                    (
                        make_product_key(
                            section_model,
                            "",
                            effective_region_for_row(line, region_suffix, section_model),
                        ),
                        base_price,
                    )
                )
            continue

        # 3d) Одна строка: … 128GB 🔸 495$ / Macbook … 24GB 2590$ (цена в конце без @)
        if (
            _line_looks_like_single_line_storage_product(line)
            and " x " not in line.lower()
        ):
            m_end = re.search(r"([\d.]+)\s*\$\s*(?:\s*\w{0,16})?\s*$", line.strip())
            if m_end and not re.search(r"@\s*[\d.]+\s*\$", line):
                price = float(m_end.group(1))
                head = line[: m_end.start()].strip()
                head = re.sub(r"[\s🔸✔️]+$", "", head)
                head = normalize_for_sheet_match(head)
                if len(head) >= 8 and re.search(r"\b\d+\s*(GB|TB)\b", line, re.I):
                    section_model = head
                    base_price = None
                    out.append(
                        (
                            make_product_key(
                                head,
                                "",
                                effective_region_for_row(line, region_suffix, section_model),
                            ),
                            price,
                        )
                    )
                    continue

        # 3e) только цена на строке: 🔸 580$ — к последней известной секции
        m_only = re.match(r"^[\s🔸✔️]*([\d.]+)\s*\$\s*$", line)
        if m_only and section_model:
            out.append(
                (
                    make_product_key(
                        section_model,
                        "",
                        effective_region_for_row(line, region_suffix, section_model),
                    ),
                    float(m_only.group(1)),
                )
            )
            continue

        # 4a) Заголовок «iPad … 11"» без GB и без цены — дальше SKU и строка только с $
        if re.search(r"\bipad\b", line, re.I) and not re.search(
            r"([\d.]+)\s*\$\s*(?:\s*\w{0,12})?\s*$", line.strip()
        ):
            if not re.search(r"\b\d+\s*(GB|TB)\b", line, re.I):
                section_model = normalize_for_sheet_match(line)
                base_price = None
                continue

        # 4) секция без @: 17 Pro 256GB / IPHONE 17 256GB $785 / 17 air … must take mix
        if re.search(r"\b\d+\s*(GB|TB)\b", line, re.I):
            if " x " in line.lower() and "$" in line:
                pass
            elif re.search(r"@\s*[\d.]+\s*\$", line):
                pass
            else:
                head, hdr_price = _strip_section_junk_and_price(line)
                section_model = normalize_for_sheet_match(head)
                base_price = hdr_price
                continue

        # 4b) White=60 $865 / Black=19 (цена с строки или с заголовка секции base_price)
        if section_model:
            eq = _parse_equals_color_price_line(line)
            if eq is not None:
                color, p = eq
                if not re.search(r"\b(GB|TB)\b", color, re.I):
                    use = p if p is not None else base_price
                    if use is not None:
                        out.append(
                            (
                                make_product_key(
                                    section_model,
                                    color,
                                    effective_region_for_row(
                                        line, region_suffix, section_model
                                    ),
                                ),
                                float(use),
                            )
                        )
                continue

        # 5) Black 45 — только при заданной базе @
        m = re.match(r"^(.+?)\s+(\d+)\s*$", line)
        if m and base_price is not None and section_model:
            color = m.group(1).strip()
            if not re.search(r"\b(GB|TB)\b", color, re.I):
                out.append(
                    (
                        make_product_key(
                            section_model,
                            color,
                            effective_region_for_row(line, region_suffix, section_model),
                        ),
                        base_price,
                    )
                )
            continue

    return _dedupe_product_prices_last_wins(out)


def _dedupe_product_prices_last_wins(
    pairs: List[Tuple[str, float]],
) -> List[Tuple[str, float]]:
    """Один ключ в одном сообщении — последняя цена побеждает (дубли строки в прайсе)."""
    if not pairs:
        return pairs
    seen: dict[str, float] = {}
    for k, p in pairs:
        seen[str(k)] = float(p)
    return list(seen.items())


def _line_has_storage_gbtb(line: str) -> bool:
    """256GB / 1 TB — не «\\bGB\\b» (между цифрой и G нет границы слова)."""
    return bool(re.search(r"\b\d+\s*(GB|TB)\b", line, re.I))


def looks_like_telegram_pricelist(text: str) -> bool:
    """Эвристика: пересланный прайс с @, x $, GB/TB или iPad/Mac с ценой в $."""
    t = text or ""
    if re.search(r"@\s*[\d.]+\s*\$", t):
        return True
    if re.search(r"\d+\s*x\s*[\d.]+\s*\$", t, re.I):
        return True
    # стиль «цвет = qty $» / «=100+$»
    if re.search(r"\b(iphone|ipad|17\s|air\s|pro\s|max)\b", t, re.I) and re.search(
        r"=\s*\d+\s*[\$\+]", t, re.I
    ):
        return True
    if re.search(r"\b(ipad|iphone|macbook)\b", t, re.I) and re.search(
        r"\$\s*[\d.]+|[\d.]+\s*\$", t
    ):
        return True
    lines = [ln for ln in t.splitlines() if ln.strip()]
    if len(lines) >= 4:
        gb = sum(1 for ln in lines if _line_has_storage_gbtb(ln))
        if gb >= 2:
            return True
    if len(lines) >= 2 and _line_has_storage_gbtb(t):
        if re.search(r"\$\s*[\d.]+|[\d.]+\s*\$", t):
            return True
    # Цвет qty … 1580 в конце без $ (Kr 🇰🇷 и т.п.)
    if _line_has_storage_gbtb(t):
        tail_price_lines = [
            ln
            for ln in lines
            if re.search(r"\d{3,}\s*\$?\s*$", ln.strip())
            and re.match(r"^[A-Za-zА-Яа-яЁё]", ln.strip())
        ]
        if len(tail_price_lines) >= 2:
            return True
    # Шапки SIM/eSIM + типичный прайс (GB/TB или Orange=60 / коды стран)
    if (
        re.search(r"(?m)^\s*(SIM|ESIM|eSIM|сим|есим)\s*$", t, re.I)
        or re.search(r"(?m)^\s*(SIM|ESIM|eSIM)\s+\d+\s*$", t, re.I)
    ) and (
        _line_has_storage_gbtb(t)
        or re.search(r"=\s*\d+", t)
        or re.search(r"\b(Kr|HK|US|Uk|Aus|Jp|JPN)\b", t, re.I)
    ):
        return True
    return False
