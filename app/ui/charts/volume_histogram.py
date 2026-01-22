import pyqtgraph as pg
from PyQt6.QtGui import QColor
from typing import Any, Callable, Iterable, List, Optional, Tuple

from .performance import calculate_visible_range, calculate_lod_step, MAX_VISIBLE_BARS_DENSE


def update_volume_histogram(
    plot_widget: pg.PlotWidget,
    volume_item: Optional[pg.BarGraphItem],
    base_color: QColor,
    data: List[Iterable],
    extract_volume: Callable[[Any, int], float],
    extract_x: Callable[[Any, int], float],
    volume_height_ratio: float = 0.15,
    bar_width: float = 0.8,
    flush_bottom: bool = True,
) -> Tuple[Optional[pg.BarGraphItem], float]:
    if not data:
        if volume_item:
            plot_widget.removeItem(volume_item)
            volume_item = None
        return None, 0.0

    try:
        viewbox = plot_widget.getViewBox()
    except Exception:
        viewbox = None

    start_idx, end_idx = calculate_visible_range(viewbox, len(data), margin=10)
    visible_count = max(0, end_idx - start_idx)
    step = calculate_lod_step(visible_count, MAX_VISIBLE_BARS_DENSE)

    volumes = []
    x_positions = []
    for idx in range(start_idx, end_idx, step):
        item = data[idx]
        vol = extract_volume(item, idx)
        x_pos = extract_x(item, idx)
        volumes.append(vol)
        x_positions.append(x_pos)

    if not volumes:
        return volume_item, 0.0

    try:
        viewbox = plot_widget.getViewBox()
        _, y_range = viewbox.viewRange()
        visible_y_min, visible_y_max = y_range
        visible_range = visible_y_max - visible_y_min
    except Exception:
        visible_range = 100.0
        visible_y_min = 0.0
        try:
            visible_data = [data[idx] for idx in range(start_idx, end_idx, step)]
            if visible_data:
                if hasattr(visible_data[0], 'get'):
                    lows = [float(item.get("low", 0)) for item in visible_data if item.get("low", 0) > 0]
                    highs = [float(item.get("high", 0)) for item in visible_data if item.get("high", 0) > 0]
                else:
                    lows = [float(item[3]) for item in visible_data if len(item) > 3 and item[3] > 0]
                    highs = [float(item[2]) for item in visible_data if len(item) > 2 and item[2] > 0]
                if lows and highs:
                    visible_y_min = min(lows)
                    visible_y_max = max(highs)
                    visible_range = visible_y_max - visible_y_min
        except Exception:
            pass

    volume_max = max(volumes) if volumes else 1.0
    if volume_max <= 0:
        volume_max = 1.0

    volume_max_height = visible_range * volume_height_ratio
    if flush_bottom:
        volume_bottom = visible_y_min
    else:
        gap = visible_range * 0.02
        volume_bottom = visible_y_min + gap

    scaled_heights = [(v / volume_max) * volume_max_height for v in volumes]
    volume_y_positions = [volume_bottom for _ in volumes]
    volume_color = QColor(base_color)
    volume_color.setAlpha(120)
    if volume_item is None:
        volume_item = pg.BarGraphItem(
            x=x_positions,
            height=scaled_heights,
            y0=volume_y_positions,
            width=bar_width,
            brush=volume_color,
            pen=pg.mkPen(base_color, width=1),
        )
        volume_item.setZValue(10)
        plot_widget.addItem(volume_item)
    else:
        volume_item.setOpts(
            x=x_positions,
            height=scaled_heights,
            y0=volume_y_positions,
            width=bar_width,
            brush=volume_color,
            pen=pg.mkPen(base_color, width=1),
        )
        volume_item.update()

    return volume_item, volume_max
