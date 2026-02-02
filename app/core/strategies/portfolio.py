from __future__ import annotations

from typing import Optional

from .models import Portfolio, Position


def mark_to_market(portfolio: Portfolio, position: Position, price: float) -> float:
    if position.size == 0 or position.entry_price is None:
        portfolio.equity = portfolio.cash
        portfolio.update_drawdown()
        return 0.0
    pnl = (price - position.entry_price) * position.size
    portfolio.equity = portfolio.cash + pnl
    portfolio.update_drawdown()
    return pnl


def close_position(position: Position) -> None:
    position.size = 0.0
    position.entry_price = None
    position.entry_ts = None


def position_side(position: Position) -> Optional[str]:
    if position.size > 0:
        return "LONG"
    if position.size < 0:
        return "SHORT"
    return None
