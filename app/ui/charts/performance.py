import numpy as np
from PyQt6.QtGui import QPainterPath
from typing import Callable, Optional, Tuple

MAX_VISIBLE_BARS_DENSE = 2000


def calculate_visible_range(viewbox: Optional[object], data_length: int, margin: int = 10) -> Tuple[int, int]:
    start_idx = 0
    end_idx = data_length

    if viewbox is not None:
        try:
            (x_range, _) = viewbox.viewRange()
            x_min, x_max = x_range
            start_idx = max(0, int(x_min) - margin)
            end_idx = min(data_length, int(x_max) + margin + 1)
            if start_idx >= end_idx:
                start_idx = 0
                end_idx = data_length
        except Exception:
            start_idx = 0
            end_idx = data_length

    return start_idx, end_idx


def calculate_lod_step(visible_count: int, max_dense: int = MAX_VISIBLE_BARS_DENSE) -> int:
    if visible_count > max_dense:
        return int(np.ceil(visible_count / max_dense))
    return 1


def create_line_path(data: list, start_idx: int, end_idx: int, step: int, extract_close_price: Callable) -> Optional[QPainterPath]:
    if step <= 1:
        return None

    line_path = QPainterPath()
    have_line_point = False

    for idx in range(start_idx, end_idx, step):
        try:
            close_val = extract_close_price(data[idx], idx)
            if close_val is not None and np.isfinite(close_val):
                if not have_line_point:
                    line_path.moveTo(float(idx), close_val)
                    have_line_point = True
                else:
                    line_path.lineTo(float(idx), close_val)
        except Exception:
            continue

    return line_path if have_line_point else None
