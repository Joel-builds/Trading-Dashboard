from typing import Iterable, List
import pyqtgraph as pg
from PyQt6.QtGui import QColor


class LineChart:
    def __init__(self, plot_widget: pg.PlotWidget, color: str) -> None:
        self.plot_widget = plot_widget
        self.base_color = QColor(color)
        self.candles: List[List[float]] = []

    def set_historical_data(self, data: List[Iterable[float]]) -> None:
        self.candles = [list(c) for c in data]

    def update_live_price(self, bid: float, ask: float, ts: float, timeframe_ms: int) -> None:
        _ = (bid, ask, ts, timeframe_ms)
