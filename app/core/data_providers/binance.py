from typing import Iterable, List, Optional
import time
import requests

BASE_URL = 'https://api.binance.com'
KLINES_LIMIT = 1000
TIMEOUT_SEC = 15


def _to_ms(ts: Optional[int]) -> Optional[int]:
    if ts is None:
        return None
    if ts < 1_000_000_000_000:
        return int(ts * 1000)
    return int(ts)


def fetch_ohlcv(symbol: str, timeframe: str, start_ts: int, end_ts: int) -> List[Iterable[float]]:
    start_ms = _to_ms(start_ts)
    end_ms = _to_ms(end_ts)
    if start_ms is None or end_ms is None:
        return []

    out: List[Iterable[float]] = []
    next_start = start_ms

    while next_start <= end_ms:
        params = {
            'symbol': symbol,
            'interval': timeframe,
            'startTime': next_start,
            'endTime': end_ms,
            'limit': KLINES_LIMIT,
        }
        resp = _get_with_retry('/api/v3/klines', params)
        resp.raise_for_status()
        data = resp.json()
        if not data:
            break
        for row in data:
            # [open_time, open, high, low, close, volume, close_time, ...]
            out.append([
                int(row[0]),
                float(row[1]),
                float(row[2]),
                float(row[3]),
                float(row[4]),
                float(row[5]),
            ])
        last_open = int(data[-1][0])
        if last_open == next_start:
            break
        next_start = last_open + 1
        time.sleep(0.1)

    return out


def fetch_symbols() -> List[str]:
    resp = _get_with_retry('/api/v3/exchangeInfo')
    resp.raise_for_status()
    data = resp.json()
    symbols = []
    for info in data.get('symbols', []):
        if info.get('status') == 'TRADING':
            symbols.append(info.get('symbol'))
    return symbols


def _get_with_retry(path: str, params: Optional[dict] = None) -> requests.Response:
    url = f'{BASE_URL}{path}'
    last_exc: Optional[Exception] = None
    for attempt in range(2):
        try:
            return requests.get(url, params=params, timeout=TIMEOUT_SEC)
        except requests.RequestException as exc:
            last_exc = exc
            if attempt == 0:
                time.sleep(0.5)
    if last_exc:
        raise last_exc
    raise requests.RequestException('Unknown request failure')
