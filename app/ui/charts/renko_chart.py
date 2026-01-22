from typing import Iterable, List
import pyqtgraph as pg
from PyQt6.QtGui import QColor


class RenkoChart:
    def __init__(self, plot_widget: pg.PlotWidget, brick_pct: float, color: str) -> None:
        self.plot_widget = plot_widget
        self.brick_pct = brick_pct
        self.base_color = QColor(color)
        self.bricks: List[dict] = []

    def set_historical_data(self, ohlcv_data: List[Iterable[float]]) -> None:
        _ = ohlcv_data

    def update_live_price(self, bid: float, ask: float, ts: float) -> None:
        _ = (bid, ask, ts)
