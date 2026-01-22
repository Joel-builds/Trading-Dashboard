import time
from typing import List, Optional

from core.data_store import DataStore
from core.data_providers import binance


def load_recent_bars(
    store: DataStore,
    exchange: str,
    symbol: str,
    timeframe: str,
    bar_count: int,
) -> List[List[float]]:
    now_ms = int(time.time() * 1000)
    interval_ms = timeframe_to_ms(timeframe)
    start_ms = now_ms - (bar_count * interval_ms)

    cached_range = store.get_cached_range(exchange, symbol, timeframe)
    if cached_range is not None:
        _, cached_max = cached_range
        if cached_max < now_ms - interval_ms:
            forward_bars = binance.fetch_ohlcv(symbol, timeframe, cached_max + interval_ms, now_ms)
            store.store_bars(exchange, symbol, timeframe, forward_bars)

    # Always refresh the most recent candle window to avoid stale closes near rollover.
    recent_start = max(0, now_ms - (interval_ms * 2))
    recent = binance.fetch_ohlcv(symbol, timeframe, recent_start, now_ms)
    store.store_bars(exchange, symbol, timeframe, recent)

    cached = store.load_bars(exchange, symbol, timeframe, start_ms, now_ms)
    if cached:
        expected_min = int(bar_count * 0.9)
        has_gap = False
        if len(cached) >= 2:
            prev_ts = int(cached[0][0])
            for row in cached[1:]:
                ts = int(row[0])
                if ts - prev_ts > interval_ms * 1.5:
                    has_gap = True
                    break
                prev_ts = ts
        if len(cached) >= expected_min and not has_gap:
            return [list(row) for row in cached]
        # If the cache is sparse or has gaps inside the requested window, refetch the full window.
        refetch = binance.fetch_ohlcv(symbol, timeframe, start_ms, now_ms)
        store.store_bars(exchange, symbol, timeframe, refetch)
        cached = store.load_bars(exchange, symbol, timeframe, start_ms, now_ms)
        return [list(row) for row in cached]

    bars = binance.fetch_ohlcv(symbol, timeframe, start_ms, now_ms)
    store.store_bars(exchange, symbol, timeframe, bars)
    return [list(row) for row in bars]


def load_cached_bars(
    store: DataStore,
    exchange: str,
    symbol: str,
    timeframe: str,
    bar_count: int,
) -> List[List[float]]:
    cached_range = store.get_cached_range(exchange, symbol, timeframe)
    if cached_range is None:
        return []
    min_ts, max_ts = cached_range
    interval_ms = timeframe_to_ms(timeframe)
    start_ms = max(min_ts, max_ts - (bar_count * interval_ms))
    cached = store.load_bars(exchange, symbol, timeframe, start_ms, max_ts)
    return [list(row) for row in cached]


def load_cached_full(
    store: DataStore,
    exchange: str,
    symbol: str,
    timeframe: str,
) -> List[List[float]]:
    cached_range = store.get_cached_range(exchange, symbol, timeframe)
    if cached_range is None:
        return []
    min_ts, max_ts = cached_range
    cached = store.load_bars(exchange, symbol, timeframe, min_ts, max_ts)
    return [list(row) for row in cached]


def load_symbols(store: DataStore, exchange: str, max_age_sec: int = 86400) -> List[str]:
    now = int(time.time())
    last_fetch = store.get_symbols_last_fetch(exchange)
    if last_fetch is not None and (now - last_fetch) < max_age_sec:
        cached = store.get_symbols(exchange)
        if cached:
            return cached

    symbols = binance.fetch_symbols()
    store.store_symbols(exchange, symbols, now)
    return symbols


def load_more_history(
    store: DataStore,
    exchange: str,
    symbol: str,
    timeframe: str,
    bar_count: int,
    current_min_ts: Optional[int] = None,
    current_max_ts: Optional[int] = None,
) -> List[List[float]]:
    cached_range = store.get_cached_range(exchange, symbol, timeframe)
    if cached_range is None:
        return load_recent_bars(store, exchange, symbol, timeframe, bar_count)

    min_ts, max_ts = cached_range
    if current_min_ts is None:
        current_min_ts = min_ts
    if current_max_ts is None:
        current_max_ts = max_ts
    oldest_ts, oldest_reached = store.get_history_limit(exchange, symbol, timeframe)
    if oldest_reached and oldest_ts is not None and current_min_ts <= oldest_ts:
        return [list(row) for row in store.load_bars(exchange, symbol, timeframe, current_min_ts, current_max_ts)]
    interval_ms = timeframe_to_ms(timeframe)
    new_start = max(0, current_min_ts - (bar_count * interval_ms))
    if new_start >= current_min_ts:
        return [list(row) for row in store.load_bars(exchange, symbol, timeframe, current_min_ts, current_max_ts)]

    cached_prev = store.load_bars(exchange, symbol, timeframe, new_start, current_min_ts - 1)
    expected_count = int((current_min_ts - 1 - new_start) / interval_ms) + 1 if interval_ms > 0 else 0
    has_gap = False
    if cached_prev and len(cached_prev) >= max(1, int(expected_count * 0.9)):
        prev_ts = int(cached_prev[0][0])
        for row in cached_prev[1:]:
            ts = int(row[0])
            if ts - prev_ts > interval_ms * 1.5:
                has_gap = True
                break
            prev_ts = ts
    else:
        has_gap = True

    if has_gap:
        bars = binance.fetch_ohlcv(symbol, timeframe, new_start, current_min_ts - 1)
        if bars:
            store.store_bars(exchange, symbol, timeframe, bars)
        else:
            store.set_history_limit(exchange, symbol, timeframe, current_min_ts, True)
            return [list(row) for row in store.load_bars(exchange, symbol, timeframe, current_min_ts, current_max_ts)]
    merged = store.load_bars(exchange, symbol, timeframe, new_start, current_max_ts)
    return [list(row) for row in merged]


def load_window_bars(
    store: DataStore,
    exchange: str,
    symbol: str,
    timeframe: str,
    start_ms: int,
    end_ms: int,
) -> List[List[float]]:
    if start_ms >= end_ms:
        return []
    interval_ms = timeframe_to_ms(timeframe)
    cached = store.load_bars(exchange, symbol, timeframe, start_ms, end_ms)
    if cached:
        has_gap = False
        prev_ts = int(cached[0][0])
        for row in cached[1:]:
            ts = int(row[0])
            if interval_ms > 0 and ts - prev_ts > interval_ms * 1.5:
                has_gap = True
                break
            prev_ts = ts
        expected_min = int((end_ms - start_ms) / interval_ms) if interval_ms > 0 else 0
        if expected_min > 0:
            expected_min = int(expected_min * 0.9)
        if not has_gap and (expected_min <= 0 or len(cached) >= expected_min):
            return [list(row) for row in cached]

    bars = binance.fetch_ohlcv(symbol, timeframe, start_ms, end_ms)
    if bars:
        store.store_bars(exchange, symbol, timeframe, bars)
    cached_range = store.get_cached_range(exchange, symbol, timeframe)
    if cached_range:
        min_ts, _ = cached_range
        if start_ms <= min_ts:
            if not bars:
                store.set_history_limit(exchange, symbol, timeframe, min_ts, True)
            else:
                try:
                    earliest = int(bars[0][0])
                except Exception:
                    earliest = min_ts
                if earliest >= min_ts:
                    store.set_history_limit(exchange, symbol, timeframe, min_ts, True)
    cached = store.load_bars(exchange, symbol, timeframe, start_ms, end_ms)
    return [list(row) for row in cached]


def timeframe_to_ms(timeframe: str) -> int:
    if not timeframe:
        return 60_000
    unit = timeframe[-1].lower()
    try:
        mult = int(timeframe[:-1])
    except (ValueError, TypeError):
        return 60_000
    if unit == 'm':
        return mult * 60_000
    if unit == 'h':
        return mult * 3_600_000
    if unit == 'd':
        return mult * 86_400_000
    if unit == 'w':
        return mult * 7 * 86_400_000
    if unit == 'M':
        return mult * 30 * 86_400_000
    return 60_000
