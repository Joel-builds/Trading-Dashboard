from __future__ import annotations

import time
from typing import Any, Callable, Dict, Optional, Tuple

import numpy as np

from .broker import compute_fill_price, compute_fee, can_fill
from .context import StrategyContext
from .models import Order, Position, Trade, RunConfig, BacktestResult
from .portfolio import mark_to_market, close_position, position_side


def run_backtest(
    bars: np.ndarray,
    strategy_module: object,
    params: Dict[str, Any],
    config: RunConfig,
    cancel_flag: Optional[Callable[[], bool]] = None,
    progress_cb: Optional[Callable[[int, int], None]] = None,
) -> Tuple[BacktestResult, str]:
    if bars is None or len(bars) < 2:
        raise ValueError("Not enough bars for backtest")

    ctx = StrategyContext(bars, params, config.initial_cash, config.leverage)
    result = BacktestResult()
    last_warn: Dict[str, bool] = {}

    on_init = getattr(strategy_module, "on_init", None)
    on_bar = getattr(strategy_module, "on_bar", None)
    on_order = getattr(strategy_module, "on_order", None)
    on_trade = getattr(strategy_module, "on_trade", None)
    on_finish = getattr(strategy_module, "on_finish", None)

    if on_init:
        on_init(ctx)
    # Debug: capture EMA values for EMA Cross if no trades
    try:
        if getattr(strategy_module, "__name__", "") and hasattr(strategy_module, "schema"):
            if strategy_module.schema().get("id") == "ema_cross":
                fast_len = int(params.get("fast", 12))
                slow_len = int(params.get("slow", 26))
                ctx._debug_fast = ctx.ind.ema(ctx.close, fast_len)
                ctx._debug_slow = ctx.ind.ema(ctx.close, slow_len)
    except Exception:
        pass

    n = len(bars)
    cancel_every = 100
    status = "DONE"

    pending_orders: list[dict] = []
    for i in range(0, n - 1):
        if cancel_flag and i % cancel_every == 0 and cancel_flag():
            status = "CANCELED"
            break
        if progress_cb and i % cancel_every == 0:
            progress_cb(i, n)

        ctx.set_bar_index(i)
        ts = int(bars[i][0])
        close_price = float(bars[i][4])
        mark_to_market(ctx.portfolio, ctx.position, close_price)

        if ts >= config.start_ts:
            result.equity_ts.append(ts)
            result.equity.append(ctx.portfolio.equity)
            result.drawdown.append(ctx.portfolio.drawdown)
            result.position_size.append(ctx.position.size)
            result.price.append(close_price)

        if pending_orders:
            open_price = float(bars[i][1])
            for o in pending_orders:
                side = o.get("side")
                size = float(o.get("size", 0.0))
                if side == "FLATTEN":
                    if ctx.position.size == 0:
                        continue
                    side = "SELL" if ctx.position.size > 0 else "BUY"
                    size = abs(ctx.position.size)

                order = Order(submitted_ts=int(o.get("submitted_ts", ts)), side=side, size=size)
                fill_price = compute_fill_price(open_price, side, config.slippage_bps)
                ok, _ = can_fill(size, fill_price, ctx.portfolio.equity, config.leverage)
                if not ok:
                    order.status = "REJECTED"
                    order.reason = "margin"
                    result.orders.append(order)
                    if on_order:
                        on_order(ctx, order)
                    continue
                fee = compute_fee(size, fill_price, config.commission_bps)
                order.fill_ts = ts
                order.fill_price = fill_price
                order.fee = fee
                order.status = "FILLED"
                result.orders.append(order)

                if ctx.position.size == 0:
                    ctx.position.size = size if side == "BUY" else -size
                    ctx.position.entry_price = fill_price
                    ctx.position.entry_ts = ts
                    ctx.portfolio.cash -= fee
                else:
                    if (ctx.position.size > 0 and side == "BUY") or (ctx.position.size < 0 and side == "SELL"):
                        if not last_warn.get("scale", False):
                            ctx.logger.warn("scaling not supported in V2", ts, ts)
                            last_warn["scale"] = True
                        continue
                    entry_price = float(ctx.position.entry_price or fill_price)
                    entry_ts = int(ctx.position.entry_ts or ts)
                    pnl = (fill_price - entry_price) * ctx.position.size
                    ctx.portfolio.cash += pnl
                    ctx.portfolio.cash -= fee
                    trade = Trade(
                        side=position_side(ctx.position) or "LONG",
                        size=abs(ctx.position.size),
                        entry_ts=entry_ts,
                        entry_price=entry_price,
                        exit_ts=ts,
                        exit_price=fill_price,
                        pnl=pnl - fee,
                        fee_total=fee,
                        bars_held=max(1, int((ts - entry_ts) / max(1, (bars[1][0] - bars[0][0])))),
                    )
                    result.trades.append(trade)
                    if on_trade:
                        on_trade(ctx, trade)
                    close_position(ctx.position)
                if on_order:
                    on_order(ctx, order)

        if ts < config.start_ts:
            ctx.trading_enabled = False
            if on_bar:
                on_bar(ctx, i)
            ctx.trading_enabled = True
        else:
            if on_bar:
                on_bar(ctx, i)
        # Orders placed during on_bar(i) should execute at open of bar i+1.
        pending_orders = ctx.pop_orders()

    if status == "CANCELED":
        i = min(i, n - 1)
        if ctx.position.size != 0:
            close_price = float(bars[i][4])
            fee = compute_fee(abs(ctx.position.size), close_price, config.commission_bps)
            pnl = (close_price - float(ctx.position.entry_price or close_price)) * ctx.position.size
            ctx.portfolio.cash += pnl - fee
            trade = Trade(
                side=position_side(ctx.position) or "LONG",
                size=abs(ctx.position.size),
                entry_ts=int(ctx.position.entry_ts or bars[i][0]),
                entry_price=float(ctx.position.entry_price or close_price),
                exit_ts=int(bars[i][0]),
                exit_price=close_price,
                pnl=pnl - fee,
                fee_total=fee,
                bars_held=1,
            )
            result.trades.append(trade)
            close_position(ctx.position)
    else:
        if config.close_on_finish and ctx.position.size != 0:
            close_price = float(bars[-1][4])
            fee = compute_fee(abs(ctx.position.size), close_price, config.commission_bps)
            pnl = (close_price - float(ctx.position.entry_price or close_price)) * ctx.position.size
            ctx.portfolio.cash += pnl - fee
            trade = Trade(
                side=position_side(ctx.position) or "LONG",
                size=abs(ctx.position.size),
                entry_ts=int(ctx.position.entry_ts or bars[-1][0]),
                entry_price=float(ctx.position.entry_price or close_price),
                exit_ts=int(bars[-1][0]),
                exit_price=close_price,
                pnl=pnl - fee,
                fee_total=fee,
                bars_held=1,
            )
            result.trades.append(trade)
            close_position(ctx.position)

    pending_orders = []
    result.logs.extend(ctx.get_logs())
    try:
        if hasattr(ctx, "_debug_fast"):
            result._debug_fast = ctx._debug_fast
        if hasattr(ctx, "_debug_slow"):
            result._debug_slow = ctx._debug_slow
        if hasattr(ctx, "_debug_fast") and hasattr(ctx, "_debug_slow"):
            fast = ctx._debug_fast
            slow = ctx._debug_slow
            cross_up = 0
            cross_dn = 0
            for j in range(1, len(fast)):
                if np.isnan(fast[j - 1]) or np.isnan(slow[j - 1]) or np.isnan(fast[j]) or np.isnan(slow[j]):
                    continue
                if fast[j] > slow[j] and fast[j - 1] <= slow[j - 1]:
                    cross_up += 1
                if fast[j] < slow[j] and fast[j - 1] >= slow[j - 1]:
                    cross_dn += 1
            result._debug_cross = (cross_up, cross_dn)
    except Exception:
        pass
    if on_finish:
        on_finish(ctx)
    return result, status
