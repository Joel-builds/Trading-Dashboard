from __future__ import annotations

from typing import Tuple


def compute_fill_price(open_price: float, side: str, slippage_bps: float) -> float:
    if side.upper() == "BUY":
        return open_price * (1.0 + slippage_bps / 10000.0)
    if side.upper() == "SELL":
        return open_price * (1.0 - slippage_bps / 10000.0)
    return open_price


def compute_fee(size: float, price: float, commission_bps: float) -> float:
    return abs(size) * price * (commission_bps / 10000.0)


def margin_required(size: float, price: float, leverage: float) -> float:
    if leverage <= 0:
        leverage = 1.0
    return abs(size) * price / leverage


def can_fill(size: float, price: float, equity: float, leverage: float) -> Tuple[bool, float]:
    required = margin_required(size, price, leverage)
    return required <= equity, required
