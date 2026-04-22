"""
Поиск строки/колонки по названию: нечёткое сопоставление с учётом GB/Tb, цветов (Blue ≈ Deep Blue).
"""

from __future__ import annotations

import re
from difflib import SequenceMatcher

# Модификаторы цвета в конце названия (двухсловные)
_COLOR_MODIFIERS = frozenset(
    {
        "deep",
        "sky",
        "light",
        "cosmic",
        "mist",
        "soft",
        "space",
        "cloud",
        "jet",
    }
)

# Распознаваемые «хвосты» цвета (нижний регистр)
_COLOR_WORDS = frozenset(
    {
        "black",
        "white",
        "pink",
        "lavender",
        "blue",
        "silver",
        "orange",
        "gold",
        "yellow",
        "green",
        "purple",
        "red",
        "titanium",
        "natural",
        "desert",
        "space",
        "gray",
        "grey",
        "graphite",
        "midnight",
        "starlight",
        "coral",
        "sierra",
        "ultramarine",
        "bronze",
        "teal",
        "magenta",
        "rose",
        "sage",
        "navy",
        "mint",
        "ice",
        "violet",
        "cream",
        "brown",
        "copper",
        "tan",
        "plum",
        "blush",
        "citrus",
        "indigo",
        "nickel",
        "strawberry",
        "ceramic",
        "jasper",
        "prussian",
        "velvet",
    }
)


def normalize_label(s: str) -> str:
    """Базовая нормализация."""
    s = (s or "").strip().lower().replace("\u00a0", " ")
    s = re.sub(r"\s+", " ", s)
    return s


def _strip_leading_emoji_and_bullets(s: str) -> str:
    """Убирает 🔹 и прочие символы в начале строки из прайса."""
    s = s.strip()
    while s:
        c0 = s[0]
        o = ord(c0)
        if c0 in "•●▪▫⭐":
            s = s[1:].lstrip()
            continue
        if o in (0xFE0F, 0x200D):
            s = s[1:].lstrip()
            continue
        if 0x1F000 <= o <= 0x1FAFF or 0x2600 <= o <= 0x27BF:
            s = s[1:].lstrip()
            continue
        break
    return s


def normalize_for_sheet_match(s: str) -> str:
    """
    Единая нормализация для сравнения прайса и колонки A:
    эмодзи, кавычки/дюймы, GB/TB, дефисы в CPU-GPU, Pro14 → Pro 14, GPC→GPU.
    """
    if not s:
        return ""
    s = _strip_leading_emoji_and_bullets(str(s))
    s = normalize_label(s)
    # кириллическая «е» в «16е», «17е» и т.п. → латинская e
    s = s.replace("\u0435", "e").replace("\u0451", "e")
    s = s.replace("\u2014", "-").replace("\u2013", "-")
    s = s.replace("\u2022", " ").replace("\u2023", " ")
    s = re.sub(r"\bmarshal\b", "marshall", s)
    s = re.sub(r"\binsta\s*360\s*x\s*4\b", "insta360 x4", s)
    s = re.sub(r"\blighting\b", "lightning", s)
    s = re.sub(r"12\s*,\s*9\s*nch", "12.9-inch", s, flags=re.I)
    s = re.sub(r"\)(type-c)", r") \1", s, flags=re.I)
    s = re.sub(r"\bgpc\b", "gpu", s, flags=re.I)
    s = s.replace('"', "'").replace('"', "'").replace('"', "'")
    s = re.sub(r"(\d+)\s*''", r"\1'", s)
    s = re.sub(r"(\d+)\s*\"", r"\1'", s)
    s = re.sub(r"-\s+", "-", s)
    s = re.sub(r"\s+-", "-", s)
    s = re.sub(r"\bpro\s*(\d)", r"pro \1", s, flags=re.I)
    s = re.sub(r"\bair\s*(\d)", r"air \1", s, flags=re.I)
    s = re.sub(r"\bmax\s*(\d)", r"max \1", s, flags=re.I)
    s = re.sub(r"^iphone\s+", "", s)
    s = re.sub(r"\)\s*(\d)", r") \1", s)
    s = re.sub(r"\(\s*(\d+)\s*gb\s*\)", r"(\1gb)", s, flags=re.I)
    s = re.sub(r"(\d+)\s*gb\b", r"\1gb", s, flags=re.I)
    s = re.sub(r"(\d+)\s*tb\b", r"\1tb", s, flags=re.I)
    s = re.sub(r"\bpro\s+max\b", "pro max", s)
    # «17 e 256gb» / «17 E 256» → 17e (как 17е в таблице)
    s = re.sub(r"\b17\s+e\s+(\d)", r"17e \1", s, flags=re.I)
    # Заголовок секции «Air 256gb» без «17» → как в колонке A «17 Air …»
    if re.match(r"^air\s+\d", s) and not re.search(r"\b17\b", s):
        s = "17 " + s
    s = _iphone17_air_marketing_colors(s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _iphone17_air_marketing_colors(s: str) -> str:
    """
    В прайсах: blue / gold / white / black; в колонке A: Sky Blue, Light Gold, Cloud White, Space Black.
    Только для «17 Air … GB», не для MacBook Air / iPad Air.
    """
    if not re.search(r"\b17\s+air\b", s):
        return s
    if re.search(r"\b(sky|deep|mist|light)\s+blue\b", s):
        pass
    elif re.search(r"\bblue\b", s):
        s = re.sub(r"\bblue\b", "sky blue", s, count=1)
    if re.search(r"\bgold\b", s) and "light" not in s:
        s = re.sub(r"\bgold\b", "light gold", s, count=1)
    if re.search(r"\bwhite\b", s) and "cloud" not in s:
        s = re.sub(r"\bwhite\b", "cloud white", s, count=1)
    if re.search(r"\bblack\b", s) and "space" not in s:
        s = re.sub(r"\bblack\b", "space black", s, count=1)
    return s


def normalize_product_name(s: str) -> str:
    """Алиас: то же, что normalize_for_sheet_match (прайс ↔ таблица)."""
    return normalize_for_sheet_match(s)


def _looks_like_order_code(token: str) -> bool:
    """Типичный хвост артикула Apple (буквы+цифры), не трогаем чисто числовые хвосты."""
    t = (token or "").strip().upper().split("/")[0]
    if len(t) < 4 or len(t) > 8:
        return False
    if not re.match(r"^[A-Z0-9]+$", t):
        return False
    has_d = any(c.isdigit() for c in t)
    has_a = any(c.isalpha() for c in t)
    return has_d and has_a


def strip_trailing_order_codes(s: str) -> str:
    """
    Убирает артикулы в конце (— MW0Y3, - MXP63, starlight-mw0y3) — сравнение без привязки к коду.
    """
    s = (s or "").strip()
    if not s:
        return ""
    for _ in range(10):
        changed = False
        m = re.search(r"(\s*[-—]\s*)((?:[A-Z0-9]{4,8})(?:/[A-Z]+)?)\s*$", s, re.I)
        if m and _looks_like_order_code(m.group(2)):
            s = s[: m.start()].strip()
            changed = True
        if not changed:
            m2 = re.search(r"(?<=[a-z0-9])-((?:[A-Z0-9]{4,8})(?:/[A-Z]+)?)\s*$", s, re.I)
            if m2 and _looks_like_order_code(m2.group(1)):
                s = s[: m2.start()].strip()
                changed = True
        if not changed:
            break
        s = re.sub(r"\s+", " ", s).strip()
    return s


def normalize_for_match_key(s: str) -> str:
    """
    Ключ для сопоставления «позиция без артикула»: то же имя товара, что в таблице,
    но без — MD… / MXP… в конце и без уточнения (USB-C) в середине.
    """
    n = normalize_for_sheet_match(s)
    n = re.sub(r"\(usb-c\)", "", n, flags=re.I)
    n = re.sub(r"\s+", " ", n).strip()
    n = strip_trailing_order_codes(n)
    return n


def _extract_color_hint(q: str) -> str | None:
    """Последнее слово-цвет или пара «deep blue» / «sky blue» (суффикс eSIM/SIM не считается цветом)."""
    parts = q.split()
    while len(parts) >= 2 and parts[-1].lower() in ("esim", "sim"):
        parts = parts[:-1]
    if len(parts) >= 2 and parts[-2] in _COLOR_MODIFIERS and parts[-1] in _COLOR_WORDS:
        return f"{parts[-2]} {parts[-1]}"
    if parts and parts[-1] in _COLOR_WORDS:
        return parts[-1]
    return None


def sim_suffix_from_normalized_name(q: str) -> str | None:
    """Последний токен esim/sim у запроса (после normalize)."""
    parts = q.split()
    if not parts:
        return None
    last = parts[-1].lower()
    if last in ("esim", "sim"):
        return last
    return None


def _suffix_token_from_row(hn: str) -> str | None:
    parts = hn.split()
    if not parts:
        return None
    last = parts[-1].lower()
    if last in ("esim", "sim"):
        return last
    return None


def _filter_indexed_by_model_family(
    indexed: list[tuple[int, str, str, str]], q: str
) -> list[tuple[int, str, str, str]]:
    """Отсекаем Pro Max / Pro / Air по запросу, чтобы не путать линейки."""
    if not indexed:
        return indexed
    ql = q.lower()
    out = indexed
    if re.search(r"pro\s*max", ql):
        out = [t for t in out if re.search(r"pro\s*max", t[2].lower())]
    elif re.search(r"\bair\b", ql) and not re.search(r"\bpro\b", ql):
        out = [t for t in out if re.search(r"\bair\b", t[2].lower())]
    elif re.search(r"\bpro\b", ql) and not re.search(r"\bair\b", ql):
        out = [
            t
            for t in out
            if re.search(r"\bpro\b", t[2].lower())
            and not re.search(r"\bair\b", t[2].lower())
        ]
        # «17 pro 256» без max — не подмешивать Pro Max
        if not re.search(r"pro\s*max", ql):
            nm = [t for t in out if not re.search(r"pro\s*max", t[2].lower())]
            if nm:
                out = nm
    return out if out else indexed


def _filter_indexed_by_storage(
    indexed: list[tuple[int, str, str, str]], q: str
) -> list[tuple[int, str, str, str]]:
    """
    Не смешивать линейки по объёму: 17 Air 512 GB blue vs 17 Air 1 TB blue — разные строки A.
    """
    if not indexed:
        return indexed
    m = re.search(r"\b(\d+)\s*(gb|tb)\b", q, re.I)
    if not m:
        return indexed
    num, unit = m.group(1), m.group(2).lower()
    pat = re.compile(rf"\b{re.escape(num)}\s*{re.escape(unit)}\b", re.I)
    out = [t for t in indexed if pat.search(t[2])]
    # Не откатываться к «любой Air» — иначе 1 TB попадает в строку 512 GB.
    if not out:
        return []
    return out


def _filter_indexed_by_sim_suffix(
    indexed: list[tuple[int, str, str, str]], q: str
) -> list[tuple[int, str, str, str]]:
    """Если в запросе явно esim или sim — не подставлять строку с другим типом."""
    suf = sim_suffix_from_normalized_name(q)
    if not suf:
        return indexed
    return [t for t in indexed if _suffix_token_from_row(t[2]) == suf]


def _color_matches_row(hn: str, hint: str | None) -> bool:
    """
    Строка из таблицы подходит под цвет из запроса.
    «blue» в прайсе сопоставляем с «deep blue», «sky blue» в таблице (слово blue).
    """
    if not hint:
        return True
    if " " in hint:
        return re.search(re.escape(hint), hn) is not None
    # одно слово — границы слова, чтобы red не ловил shared
    if re.search(rf"\b{re.escape(hint)}\b", hn):
        return True
    return False


IndexedHeaderRow = tuple[int, str, str, str]  # 1-based col, raw, hn, hk


def build_column_index_cache(headers: list[str]) -> list[IndexedHeaderRow]:
    """
    Один раз нормализует все строки колонки A. При десятках позиций в одном прайсе
    иначе find_column_index вызывается N раз × M строк → долгий «зависший» бот.
    """
    indexed: list[IndexedHeaderRow] = []
    for j, raw in enumerate(headers):
        if raw is None or str(raw).strip() == "":
            continue
        h = str(raw).strip()
        hn = normalize_product_name(h)
        if not hn:
            continue
        hk = normalize_for_match_key(h)
        if not hk:
            hk = hn
        indexed.append((j + 1, h, hn, hk))
    return indexed


def find_column_index(
    headers: list[str],
    user_model: str,
    *,
    min_similarity: float = 0.82,
    _indexed_cache: list[IndexedHeaderRow] | None = None,
) -> tuple[int, str]:
    """
    Ищет 1-based индекс по списку строк (шапка или колонка A).

    Приоритет:
    1) точное совпадение после normalize_product_name;
    2) одно вхождение подстроки (короткое в длинном);
    3) лучший SequenceMatcher с фильтром по цвету и автоприёмом похожего варианта.

    _indexed_cache: результат build_column_index_cache(headers) — переиспользовать в пакетной записи.
    """
    q = normalize_product_name(user_model)
    if not q:
        raise ValueError("Пустое название модели.")

    q_key = normalize_for_match_key(user_model)
    if not q_key:
        q_key = q

    adaptive_min = min_similarity
    ref_len = max(len(q), len(q_key))
    if ref_len > 55:
        adaptive_min = max(0.74, min_similarity - 0.06)

    if _indexed_cache is not None:
        indexed = list(_indexed_cache)
    else:
        indexed = build_column_index_cache(headers)

    if not indexed:
        raise ValueError("Нет ни одной непустой строки для сравнения.")

    color_hint = _extract_color_hint(q)
    if color_hint:
        filtered = [t for t in indexed if _color_matches_row(t[2], color_hint)]
        if filtered:
            indexed = filtered

    indexed = _filter_indexed_by_model_family(indexed, q)
    indexed = _filter_indexed_by_storage(indexed, q)
    indexed = _filter_indexed_by_sim_suffix(indexed, q)

    if not indexed:
        extra = ""
        if re.search(r"\b(\d+)\s*(gb|tb)\b", q, re.I):
            extra = " Убедитесь, что в A есть тот же объём памяти (256/512 GB, 1/2 TB), не другая комплектация."
        raise ValueError(
            f"Нет строки для «{user_model}» (модель / цвет / SIM vs eSIM).{extra} "
            "Проверьте колонку A: нужна отдельная строка с тем же eSIM или SIM."
        )

    # 1) Точное совпадение (полная нормализация или без артикула)
    exact = [
        (c, h)
        for c, h, hn, hk in indexed
        if hn == q or (q_key and hk and q_key == hk)
    ]
    if len(exact) == 1:
        return exact[0][0], exact[0][1]
    if len(exact) > 1:
        raise ValueError(
            "В шапке несколько строк с одинаковым названием — сделайте названия уникальными."
        )

    # 2) Ровно одно вхождение подстроки
    subs = []
    for c, h, hn, hk in indexed:
        if q == hn or (q_key and hk and q_key == hk):
            continue
        if q in hn or hn in q or (q_key and hk and (q_key in hk or hk in q_key)):
            subs.append((c, h, hn))
    if len(subs) == 1:
        return subs[0][0], subs[0][1]

    # 3) Похожесть (по ключу без артикула)
    scored: list[tuple[float, int, str]] = []
    for c, h, hn, hk in indexed:
        sim = SequenceMatcher(None, q_key, hk).ratio()
        scored.append((sim, c, h))
    scored.sort(key=lambda x: (-x[0], x[1]))

    if not scored:
        raise ValueError("Не удалось сопоставить колонку.")

    best_sim, best_c, best_h = scored[0]
    second_sim = scored[1][0] if len(scored) > 1 else 0.0
    gap = best_sim - second_sim

    # Явный лидер по похожести (длинные названия Mac — чуть мягче порог)
    if best_sim >= adaptive_min and gap >= 0.03:
        return best_c, best_h

    # Два близких кандидата (например Deep Blue vs Sky Blue): берём лучший при достаточной базе
    if best_sim >= 0.78 and gap >= 0.015:
        return best_c, best_h

    # Один кандидат заметно выше остальных по «хвосту», даже при малом gap
    if best_sim >= 0.76 and second_sim < 0.72:
        return best_c, best_h

    # Очень похоже, но список короткий — берём лучший (типично 2–3 оттенка blue)
    if len(scored) <= 4 and best_sim >= 0.74:
        return best_c, best_h

    if best_sim < 0.68:
        raise ValueError(
            f"Строка для «{user_model}» не найдена. "
            "Скопируйте название из колонки A таблицы."
        )

    names = ", ".join(f"«{t[2]}»" for t in scored[:4])
    raise ValueError(
        f"Неоднозначно, какая строка соответствует «{user_model}». "
        f"Похожие: {names}. Уточните название, как в таблице."
    )
