from typing import Optional, Tuple


def calculate_price_diff(competitor_price: Optional[int], my_price: Optional[int]) -> Optional[int]:
    if competitor_price is None or my_price is None:
        return None
    return competitor_price - my_price


def choose_cheaper_side(competitor_price: Optional[int], my_price: Optional[int]) -> Tuple[str, bool]:
    if competitor_price is None or my_price is None:
        return "unknown", False
    if competitor_price < my_price:
        return "competitor", True
    if competitor_price > my_price:
        return "me", False
    return "equal", False
