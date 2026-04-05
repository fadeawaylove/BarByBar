from __future__ import annotations

import re

DEFAULT_TICK_SIZE = 1.0

_SYMBOL_TICK_SIZES = {
    "AG": 1.0,
    "AU": 0.02,
    "CU": 10.0,
    "AL": 5.0,
    "ZN": 5.0,
    "PB": 5.0,
    "NI": 10.0,
    "SN": 10.0,
    "SS": 5.0,
    "RB": 1.0,
    "HC": 1.0,
    "BU": 2.0,
    "RU": 5.0,
    "FU": 1.0,
    "SP": 2.0,
    "SC": 0.1,
    "PG": 1.0,
    "EB": 1.0,
    "TA": 2.0,
    "MA": 1.0,
    "FG": 1.0,
    "SA": 1.0,
    "SR": 1.0,
    "CF": 5.0,
    "RM": 1.0,
    "OI": 1.0,
    "C": 1.0,
    "CS": 1.0,
    "A": 1.0,
    "B": 1.0,
    "M": 1.0,
    "Y": 2.0,
    "P": 2.0,
    "JD": 1.0,
    "I": 0.5,
    "J": 0.5,
    "JM": 0.5,
    "IF": 0.2,
    "IH": 0.2,
    "IC": 0.2,
    "IM": 0.2,
}

_CHINESE_ALIASES = {
    "白银": "AG",
    "沪银": "AG",
    "黄金": "AU",
    "沪金": "AU",
    "螺纹": "RB",
    "热卷": "HC",
    "原油": "SC",
    "沪铜": "CU",
    "沪铝": "AL",
    "沪锌": "ZN",
    "豆粕": "M",
    "豆油": "Y",
    "棕榈": "P",
    "铁矿": "I",
    "焦炭": "J",
    "焦煤": "JM",
    "沪深300": "IF",
    "上证50": "IH",
    "中证500": "IC",
    "中证1000": "IM",
}


def resolve_symbol_root(symbol: str) -> str:
    normalized = symbol.strip().upper()
    letters = re.match(r"[A-Z]+", normalized)
    if letters:
        return letters.group(0)
    for alias, root in _CHINESE_ALIASES.items():
        if alias in symbol:
            return root
    return normalized


def default_tick_size_for_symbol(symbol: str) -> float:
    root = resolve_symbol_root(symbol)
    return _SYMBOL_TICK_SIZES.get(root, DEFAULT_TICK_SIZE)


def snap_price(price: float, tick_size: float) -> float:
    valid_tick = max(float(tick_size), 0.0001)
    snapped = round(price / valid_tick) * valid_tick
    tick_text = f"{valid_tick:.8f}".rstrip("0").rstrip(".")
    decimals = len(tick_text.split(".")[1]) if "." in tick_text else 0
    return round(snapped, decimals)


def price_decimals_for_tick(tick_size: float) -> int:
    valid_tick = max(float(tick_size), 0.0001)
    tick_text = f"{valid_tick:.8f}".rstrip("0").rstrip(".")
    decimals = len(tick_text.split(".")[1]) if "." in tick_text else 0
    return min(decimals, 2)


def format_price(price: float | int | None, tick_size: float) -> str:
    if price is None:
        return "-"
    decimals = price_decimals_for_tick(tick_size)
    return f"{float(price):.{decimals}f}"
