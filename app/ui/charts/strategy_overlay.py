from __future__ import annotations

from typing import Dict, List, Optional, Tuple

import pyqtgraph as pg
from PyQt6.QtGui import QPainter, QPicture, QColor
from PyQt6.QtCore import QRectF
from PyQt6.QtCore import QPointF


class StrategyOverlayRenderer(pg.GraphicsObject):
    def __init__(self, markers: List[Dict], get_index_for_ts=None) -> None:
        super().__init__()
        self._markers = markers
        self._chunk_size = 400
        self._chunk_cache: Dict[int, QPicture] = {}
        self._get_index_for_ts = get_index_for_ts
        self._ts_cache: Optional[List[float]] = None
        self._bounds = QRectF()

    def set_ts_cache(self, ts_cache: List[float]) -> None:
        self._ts_cache = ts_cache
        self._chunk_cache = {}
        self._bounds = self._compute_bounds()
        self.update()

    def set_markers(self, markers: List[Dict]) -> None:
        self._markers = markers
        self._chunk_cache = {}
        self._bounds = self._compute_bounds()
        self.update()

    def paint(self, painter: QPainter, option, widget) -> None:
        if not self._markers:
            return
        try:
            vb = self.getViewBox()
        except Exception:
            vb = None
        if vb is not None:
            try:
                (x_range, _) = vb.viewRange()
                x_min, x_max = x_range
            except Exception:
                x_min = None
                x_max = None
        else:
            x_min = x_max = None

        markers = self._markers
        if x_min is not None and x_max is not None:
            markers = [m for m in markers if x_min <= m.get("ts", 0) <= x_max]

        if not markers:
            return

        total = len(markers)
        start_chunk = 0
        end_chunk = (total - 1) // self._chunk_size
        for chunk_idx in range(start_chunk, end_chunk + 1):
            picture = self._chunk_cache.get(chunk_idx)
            if picture is None:
                picture = self._render_chunk(chunk_idx)
                self._chunk_cache[chunk_idx] = picture
            painter.drawPicture(0, 0, picture)

    def boundingRect(self):
        return self._bounds if not self._bounds.isNull() else super().boundingRect()

    def _compute_bounds(self) -> QRectF:
        if not self._markers:
            return QRectF()
        try:
            ts_vals = [float(m.get("ts", 0)) for m in self._markers]
            price_vals = [float(m.get("price", 0)) for m in self._markers]
            min_ts = min(ts_vals)
            max_ts = max(ts_vals)
            min_p = min(price_vals)
            max_p = max(price_vals)
            if max_ts == min_ts:
                max_ts += 1.0
            if max_p == min_p:
                max_p += 1.0
            return QRectF(min_ts, min_p, max_ts - min_ts, max_p - min_p)
        except Exception:
            return QRectF()

    def _render_chunk(self, chunk_idx: int) -> QPicture:
        picture = QPicture()
        painter = QPainter(picture)
        try:
            start = chunk_idx * self._chunk_size
            end = min(len(self._markers), start + self._chunk_size)
            for marker in self._markers[start:end]:
                ts = float(marker.get("ts", 0))
                price = float(marker.get("price", 0))
                kind = marker.get("kind", "entry")
                side = marker.get("side", "LONG")
                color = QColor('#22C55E') if side == "LONG" else QColor('#EF5350')
                painter.setPen(pg.mkPen(color))
                painter.setBrush(pg.mkBrush(color))
                size = 6.0
                if kind == "entry":
                    points = [
                        QPointF(ts, price + size),
                        QPointF(ts - size, price - size),
                        QPointF(ts + size, price - size),
                    ]
                else:
                    points = [
                        QPointF(ts, price - size),
                        QPointF(ts - size, price + size),
                        QPointF(ts + size, price + size),
                    ]
                painter.drawPolygon(*points)
        finally:
            painter.end()
        return picture
