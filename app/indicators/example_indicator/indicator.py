from typing import Dict, List, Tuple


def schema() -> Dict:
    return {
        'id': 'sma',
        'name': 'SMA',
        'inputs': {
            'length': {'type': 'int', 'default': 20, 'min': 2, 'max': 200}
        }
    }


def compute(bars: List[Dict], params: Dict) -> Dict[str, List[Tuple[int, float]]]:
    length = int(params.get('length', 20))
    if length <= 0:
        return {'sma': []}

    closes = []
    times = []
    for bar in bars:
        try:
            closes.append(float(bar['close']))
            times.append(int(bar['time']))
        except Exception:
            continue

    out = []
    for i in range(len(closes)):
        if i + 1 < length:
            continue
        window = closes[i + 1 - length: i + 1]
        out.append((times[i], sum(window) / length))

    return {'sma': out}
