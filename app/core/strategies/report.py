from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List

import numpy as np

from .models import Trade


@dataclass
class StrategyReport:
    run_id: str
    stats: Dict[str, float]
    equity_ts: List[int]
    equity: List[float]
    drawdown: List[float]
    trades: List[Trade]
    markers: List[Dict[str, Any]]


def compute_stats(trades: List[Trade], equity: List[float]) -> Dict[str, float]:
    total_return = 0.0
    if equity:
        total_return = (equity[-1] - equity[0]) / equity[0] * 100.0 if equity[0] != 0 else 0.0
    wins = [t for t in trades if t.pnl > 0]
    losses = [t for t in trades if t.pnl <= 0]
    win_rate = (len(wins) / len(trades) * 100.0) if trades else 0.0
    profit = sum(t.pnl for t in wins)
    loss = abs(sum(t.pnl for t in losses))
    profit_factor = (profit / loss) if loss > 0 else 0.0
    max_dd = 0.0
    if equity:
        peak = equity[0]
        for val in equity:
            if val > peak:
                peak = val
            dd = (peak - val) / peak if peak > 0 else 0.0
            if dd > max_dd:
                max_dd = dd
    return {
        "total_return_pct": total_return,
        "max_drawdown_pct": max_dd * 100.0,
        "num_trades": float(len(trades)),
        "win_rate_pct": win_rate,
        "profit_factor": profit_factor,
    }


def build_markers(trades: List[Trade]) -> List[Dict[str, Any]]:
    markers: List[Dict[str, Any]] = []
    for t in trades:
        markers.append({
            "ts": t.entry_ts,
            "price": t.entry_price,
            "kind": "entry",
            "side": t.side,
        })
        markers.append({
            "ts": t.exit_ts,
            "price": t.exit_price,
            "kind": "exit",
            "side": t.side,
            "pnl": t.pnl,
        })
    return markers


def build_report(run_id: str, trades: List[Trade], equity_ts: List[int], equity: List[float], drawdown: List[float]) -> StrategyReport:
    stats = compute_stats(trades, equity)
    markers = build_markers(trades)
    return StrategyReport(
        run_id=run_id,
        stats=stats,
        equity_ts=equity_ts,
        equity=equity,
        drawdown=drawdown,
        trades=trades,
        markers=markers,
    )
