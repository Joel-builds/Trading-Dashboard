from datetime import datetime
from typing import Iterable, List, Optional, Tuple

import numpy as np
import pyqtgraph as pg
from PyQt6.QtCore import Qt, QRectF, QPointF
from PyQt6.QtGui import QFont, QPainter, QPicture, QColor

from .performance import calculate_visible_range, calculate_lod_step, MAX_VISIBLE_BARS_DENSE
from .volume_histogram import update_volume_histogram


class CandlestickItem(pg.GraphicsObject):
    def __init__(
        self,
        data: List[Iterable[float]],
        up_color: QColor,
        down_color: QColor,
        bar_colors: Optional[List[Optional[QColor]]] = None,
    ) -> None:
        super().__init__()
        self.data = data
        self.base_color = up_color
        self.down_color = down_color
        self.bar_colors = bar_colors if bar_colors is not None else []
        self.picture = QPicture()
        self._cached_bounds: Optional[QRectF] = None
        self._is_painting = False
        self.generate_picture()

    def generate_picture(self) -> None:
        if self._is_painting:
            return
        self._is_painting = True
        try:
            self.picture = QPicture()
            painter = QPainter(self.picture)
            try:
                if len(self.data) == 0:
                    self._cached_bounds = QRectF(0, 0, 1, 1)
                    return
                w = 0.3
                try:
                    vb = self.getViewBox()
                except Exception:
                    vb = None
                start_idx, end_idx = calculate_visible_range(vb, len(self.data), margin=10)
                visible_count = max(0, end_idx - start_idx)
                step = calculate_lod_step(visible_count, MAX_VISIBLE_BARS_DENSE)
                y_min = float('inf')
                y_max = float('-inf')
                x_min = float('inf')
                x_max = float('-inf')

                for idx in range(start_idx, end_idx, step):
                    candle = self.data[idx]
                    if len(candle) < 5:
                        continue
                    try:
                        open_price = float(candle[1])
                        high = float(candle[2])
                        low = float(candle[3])
                        close = float(candle[4])
                    except (ValueError, TypeError):
                        continue
                    if low <= 0 or high <= 0 or open_price <= 0 or close <= 0:
                        continue
                    if not (np.isfinite(low) and np.isfinite(high) and np.isfinite(open_price) and np.isfinite(close)):
                        continue
                    if high < low:
                        high, low = low, high
                    price_avg = (open_price + close) / 2.0
                    if price_avg <= 0 or not np.isfinite(price_avg):
                        continue
                    price_range = high - low
                    if price_range > price_avg * 10:
                        continue
                    if low < price_avg * 0.1 or high > price_avg * 10:
                        continue
                    y_min = min(y_min, low)
                    y_max = max(y_max, high)
                    x_min = min(x_min, idx - w)
                    x_max = max(x_max, idx + w)

                    is_bear = close < open_price
                    if len(self.bar_colors) > 0 and idx < len(self.bar_colors) and self.bar_colors[idx] is not None:
                        current_color = self.bar_colors[idx]
                    else:
                        current_color = self.down_color if is_bear else self.base_color

                    painter.setPen(pg.mkPen(current_color))
                    painter.setBrush(pg.mkBrush(current_color))
                    if high != low:
                        painter.drawLine(QPointF(idx, low), QPointF(idx, high))
                    body_top = max(open_price, close)
                    body_bottom = min(open_price, close)
                    body_height = body_top - body_bottom
                    if body_height > 0:
                        painter.drawRect(QRectF(idx - w, body_bottom, w * 2, body_height))
                    else:
                        painter.drawLine(QPointF(idx - w, close), QPointF(idx + w, close))

                if y_min != float('inf') and y_max != float('-inf'):
                    self._cached_bounds = QRectF(x_min, y_min, x_max - x_min, y_max - y_min)
                else:
                    self._cached_bounds = QRectF(self.picture.boundingRect())
            finally:
                painter.end()
        finally:
            self._is_painting = False

    def paint(self, painter: QPainter, option, widget) -> None:
        try:
            painter.drawPicture(0, 0, self.picture)
        except RuntimeError:
            pass

    def boundingRect(self) -> QRectF:
        if self._cached_bounds is not None and self._cached_bounds.isValid():
            return self._cached_bounds
        return QRectF(self.picture.boundingRect())

    def set_data(self, data: List[Iterable[float]], bar_colors: Optional[List[Optional[QColor]]] = None) -> None:
        if bar_colors is not None:
            self.bar_colors = bar_colors
        self.data = data
        self.generate_picture()
        try:
            self.informViewBoundsChanged()
        except RuntimeError:
            pass
        try:
            self.update()
        except RuntimeError:
            pass


class CandlestickChart:
    def __init__(self, plot_widget: pg.PlotWidget, up_color: str, down_color: str) -> None:
        self.plot_widget = plot_widget
        self.base_color = QColor(up_color)
        self.down_color = QColor(down_color)
        self.candles: List[List[float]] = []
        self._day_gridlines = []
        self.bar_colors: List[Optional[QColor]] = []
        self.volume_item: Optional[pg.BarGraphItem] = None
        self.volume_max: float = 0.0

        self.plot_widget.setClipToView(True)
        try:
            view_box = self.plot_widget.getViewBox()
            if view_box:
                view_box.enableAutoRange('x', False)
                view_box.enableAutoRange('y', False)
                view_box.sigRangeChanged.connect(self._on_view_changed)
        except Exception:
            pass

        self.item = CandlestickItem([], self.base_color, self.down_color)
        self.plot_widget.addItem(self.item)

        self._setup_price_axis()
        self._setup_date_index_axis()

    def _setup_price_axis(self) -> None:
        class PriceAxis(pg.AxisItem):
            def tickStrings(self, values, scale, spacing):
                out = []
                for v in values:
                    try:
                        if not np.isfinite(v) or v <= 0:
                            out.append('')
                            continue
                        if v >= 1000:
                            out.append(f'{v:,.0f}')
                        elif v >= 100:
                            out.append(f'{v:,.1f}')
                        elif v >= 10:
                            out.append(f'{v:,.2f}')
                        elif v >= 1:
                            out.append(f'{v:,.3f}')
                        elif v >= 0.01:
                            out.append(f'{v:.4f}')
                        elif v >= 0.0001:
                            out.append(f'{v:.6f}')
                        elif v >= 0.000001:
                            out.append(f'{v:.8f}')
                        else:
                            out.append(f'{v:.10f}'.rstrip('0').rstrip('.'))
                    except Exception:
                        out.append('')
                return out

        try:
            price_axis = PriceAxis(orientation='left')
            font = QFont()
            font.setPointSize(8)
            price_axis.setTickFont(font)
            self.plot_widget.setAxisItems({'left': price_axis})
        except Exception:
            pass

    def _setup_date_index_axis(self) -> None:
        class DateIndexAxis(pg.AxisItem):
            def __init__(self, parent_chart, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.parent_chart = parent_chart
                self._day_rollover_indices = []
                self._update_day_rollovers()

            def _update_day_rollovers(self):
                self._day_rollover_indices = []
                candles = self.parent_chart.candles
                if not candles:
                    return
                last_day = None
                for idx, candle in enumerate(candles):
                    try:
                        ts_ms = float(candle[0])
                        dt = datetime.fromtimestamp(ts_ms / 1000.0)
                        current_day = dt.date()
                        if last_day is not None and current_day != last_day:
                            self._day_rollover_indices.append(idx)
                        last_day = current_day
                    except Exception:
                        continue

            def tickValues(self, minVal, maxVal, size):
                if not self._day_rollover_indices:
                    self._update_day_rollovers()
                visible_indices = [idx for idx in self._day_rollover_indices if minVal <= idx <= maxVal]
                if not visible_indices:
                    return []
                spacing = max(1, int((maxVal - minVal) / 10))
                step = max(1, len(visible_indices) // 10)
                selected = visible_indices[::max(1, step)]
                return [(1, selected)]

            def tickStrings(self, values, scale, spacing):
                out = []
                candles = self.parent_chart.candles
                for v in values:
                    try:
                        idx = int(round(v))
                    except Exception:
                        out.append('')
                        continue
                    if idx < 0 or idx >= len(candles):
                        out.append('')
                        continue
                    ts_ms = candles[idx][0]
                    try:
                        dt = datetime.fromtimestamp(ts_ms / 1000.0)
                        date_str = dt.strftime('%Y-%m-%d')
                    except Exception:
                        out.append('')
                        continue
                    out.append(date_str)
                return out

        bottom_axis = DateIndexAxis(self, orientation='bottom')
        font = QFont()
        font.setPointSize(8)
        bottom_axis.setTickFont(font)
        bottom_axis.setStyle(autoExpandTextSpace=False, tickTextOffset=2)
        bottom_axis.setHeight(38)
        self.plot_widget.setAxisItems({'bottom': bottom_axis})
        left_axis = self.plot_widget.getAxis('left')
        if left_axis:
            left_axis.setTickFont(font)
        self._date_index_axis = bottom_axis
        self._update_day_gridlines()

    def _update_day_gridlines(self) -> None:
        for line in self._day_gridlines:
            try:
                self.plot_widget.removeItem(line)
            except Exception:
                pass
        self._day_gridlines = []
        if not self.candles:
            if hasattr(self, '_date_index_axis') and self._date_index_axis:
                self._date_index_axis._update_day_rollovers()
            return
        last_day = None
        gridline_color = QColor(self.base_color)
        gridline_color.setAlpha(20)
        pen = pg.mkPen(gridline_color, width=1)
        for idx, candle in enumerate(self.candles):
            try:
                ts_ms = float(candle[0])
                dt = datetime.fromtimestamp(ts_ms / 1000.0)
                current_day = dt.date()
                if last_day is not None and current_day != last_day:
                    gridline = pg.InfiniteLine(pos=float(idx), angle=90, pen=pen)
                    self.plot_widget.addItem(gridline)
                    self._day_gridlines.append(gridline)
                last_day = current_day
            except Exception:
                continue
        if hasattr(self, '_date_index_axis') and self._date_index_axis:
            self._date_index_axis._update_day_rollovers()

    def _on_view_changed(self) -> None:
        try:
            self.item.generate_picture()
            self.item.update()
            if self.volume_item and self.candles:
                self._update_volume_histogram(self.candles)
        except Exception:
            pass

    def _update_volume_histogram(self, candles: List[Iterable[float]]) -> None:
        def extract_volume(candle: Iterable[float], idx: int) -> float:
            if len(candle) > 5:
                return float(candle[5]) if candle[5] is not None else 0.0
            return 0.0

        def extract_x(candle: Iterable[float], idx: int) -> float:
            return float(idx)

        volume_color = QColor('#22C55E')
        self.volume_item, self.volume_max = update_volume_histogram(
            plot_widget=self.plot_widget,
            volume_item=self.volume_item,
            base_color=volume_color,
            data=candles,
            extract_volume=extract_volume,
            extract_x=extract_x,
            volume_height_ratio=0.15,
            bar_width=0.8,
            flush_bottom=True,
        )

    def set_historical_data(self, data: List[Iterable[float]]) -> None:
        normalized = []
        for c in data:
            if not isinstance(c, (list, tuple)) or len(c) < 5:
                continue
            ts, o, h, l, cl = c[0], c[1], c[2], c[3], c[4]
            vol = c[5] if len(c) > 5 else 0.0
            try:
                o, h, l, cl = float(o), float(h), float(l), float(cl)
                if o <= 0 or h <= 0 or l <= 0 or cl <= 0:
                    continue
                if not (np.isfinite(o) and np.isfinite(h) and np.isfinite(l) and np.isfinite(cl)):
                    continue
            except (ValueError, TypeError):
                continue
            normalized.append([ts, o, h, l, cl, vol])
        if not normalized:
            return
        self.candles = normalized
        self.item.set_data(self.candles, bar_colors=self.bar_colors)
        self._update_volume_histogram(self.candles)
        self._update_day_gridlines()
        self._auto_range()

    def _auto_range(self) -> None:
        if not self.candles:
            return
        lows = [c[3] for c in self.candles if c[3] > 0]
        highs = [c[2] for c in self.candles if c[2] > 0]
        if not lows or not highs:
            return
        y_min, y_max = min(lows), max(highs)
        price_range = y_max - y_min
        if price_range > 0:
            self.plot_widget.setYRange(y_min - price_range * 0.1, y_max + price_range * 0.1)
        n = len(self.candles)
        show_candles = min(400, n)
        self.plot_widget.setXRange(max(0, n - show_candles - 5), n + 5)

    def set_bar_colors(self, bar_colors: List[Optional[QColor]]) -> None:
        self.bar_colors = bar_colors
        try:
            self.item.set_data(self.candles, bar_colors=self.bar_colors)
        except RuntimeError:
            pass
