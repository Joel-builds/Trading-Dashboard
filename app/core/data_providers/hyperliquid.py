from typing import Iterable, List


def fetch_ohlcv(symbol: str, timeframe: str, start_ts: int, end_ts: int) -> List[Iterable[float]]:
    _ = (symbol, timeframe, start_ts, end_ts)
    return []


def fetch_symbols() -> List[str]:
    return []
