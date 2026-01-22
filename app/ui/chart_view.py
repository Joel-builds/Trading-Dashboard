import os
import time
from typing import Optional, List
import pyqtgraph as pg
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QComboBox, QLabel
from PyQt6.QtGui import QFont
from PyQt6.QtCore import QThread, pyqtSignal

from core.data_store import DataStore
from core.data_fetch import load_recent_bars, load_symbols, load_more_history
from .theme import theme
from .charts.candlestick_chart import CandlestickChart


class DataFetchWorker(QThread):
    data_ready = pyqtSignal(list)
    error = pyqtSignal(str)

    def __init__(self, mode: str, store: DataStore, exchange: str, symbol: str, timeframe: str, bar_count: int) -> None:
        super().__init__()
        self.mode = mode
        self.store = store
        self.exchange = exchange
        self.symbol = symbol
        self.timeframe = timeframe
        self.bar_count = bar_count

    def run(self) -> None:
        try:
            if self.mode == 'load':
                bars = load_recent_bars(self.store, self.exchange, self.symbol, self.timeframe, self.bar_count)
            elif self.mode == 'backfill':
                bars = load_more_history(self.store, self.exchange, self.symbol, self.timeframe, self.bar_count)
            else:
                raise ValueError(f'Unknown fetch mode: {self.mode}')
            self.data_ready.emit(bars)
        except Exception as exc:
            self.error.emit(str(exc))


class SymbolFetchWorker(QThread):
    data_ready = pyqtSignal(list)
    error = pyqtSignal(str)

    def __init__(self, store: DataStore, exchange: str) -> None:
        super().__init__()
        self.store = store
        self.exchange = exchange

    def run(self) -> None:
        try:
            symbols = load_symbols(self.store, self.exchange)
            self.data_ready.emit(symbols)
        except Exception as exc:
            self.error.emit(str(exc))


class ChartView(QWidget):
    def __init__(self, error_sink=None) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.toolbar = QWidget()
        toolbar_layout = QHBoxLayout(self.toolbar)
        toolbar_layout.setContentsMargins(8, 8, 8, 4)
        toolbar_layout.setSpacing(8)

        toolbar_layout.addWidget(QLabel('Symbol'))
        self.symbol_box = QComboBox()
        toolbar_layout.addWidget(self.symbol_box)

        toolbar_layout.addWidget(QLabel('Timeframe'))
        self.timeframe_box = QComboBox()
        self.timeframe_box.addItems(['1m', '5m', '15m', '1h', '4h', '1d'])
        toolbar_layout.addWidget(self.timeframe_box)

        self.load_button = QPushButton('Load')
        toolbar_layout.addWidget(self.load_button)

        self.backfill_button = QPushButton('Load More')
        toolbar_layout.addWidget(self.backfill_button)

        self.status_label = QLabel('')
        toolbar_layout.addWidget(self.status_label)
        toolbar_layout.addStretch(1)

        layout.addWidget(self.toolbar)

        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setBackground(theme.BACKGROUND)
        self.plot_widget.showGrid(x=True, y=True, alpha=0.2)
        self.plot_widget.setClipToView(True)

        self._apply_axis_style()

        layout.addWidget(self.plot_widget)

        self.candles = CandlestickChart(self.plot_widget, theme.UP, theme.DOWN)
        self._setup_data_store()
        self._load_symbols()

        self.load_button.clicked.connect(self._on_load_clicked)
        self.backfill_button.clicked.connect(self._on_backfill_clicked)
        self.error_sink = error_sink

    def _apply_axis_style(self) -> None:
        axis_pen = pg.mkPen(theme.GRID)
        text_pen = pg.mkPen(theme.TEXT)
        font = QFont()
        font.setPointSize(9)

        for axis_name in ('left', 'bottom'):
            axis = self.plot_widget.getAxis(axis_name)
            axis.setPen(axis_pen)
            axis.setTextPen(text_pen)
            axis.setTickFont(font)

    def _setup_data_store(self) -> None:
        db_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'ohlcv.sqlite')
        db_path = os.path.abspath(db_path)
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.store = DataStore(db_path)
        self.exchange = 'binance'
        self._worker: Optional[DataFetchWorker] = None
        self._symbol_worker: Optional[SymbolFetchWorker] = None

    def _load_symbols(self) -> None:
        if self._symbol_worker and self._symbol_worker.isRunning():
            return
        self._set_loading(True, 'Loading symbols...')
        self._symbol_worker = SymbolFetchWorker(self.store, self.exchange)
        self._symbol_worker.data_ready.connect(self._on_symbols_ready)
        self._symbol_worker.error.connect(self._on_symbol_error)
        self._symbol_worker.finished.connect(self._on_symbol_fetch_finished)
        self._symbol_worker.start()

    def _on_symbols_ready(self, symbols: List[str]) -> None:
        if symbols:
            self.symbol_box.addItems(symbols)
            if 'BTCUSDT' in symbols:
                self.symbol_box.setCurrentText('BTCUSDT')
        self._load_initial_data()

    def _on_symbol_error(self, message: str) -> None:
        self._report_error(f'Symbol list fetch failed: {message}')
        self._load_initial_data()

    def _on_symbol_fetch_finished(self) -> None:
        self._set_loading(False, '')

    def _load_initial_data(self) -> None:
        symbol = self.symbol_box.currentText() or 'BTCUSDT'
        timeframe = self.timeframe_box.currentText() or '1m'
        bar_count = 500
        self._start_fetch('load', symbol, timeframe, bar_count)

    def _on_load_clicked(self) -> None:
        self._load_initial_data()

    def _on_backfill_clicked(self) -> None:
        symbol = self.symbol_box.currentText() or 'BTCUSDT'
        timeframe = self.timeframe_box.currentText() or '1m'
        bar_count = 2000
        self._start_fetch('backfill', symbol, timeframe, bar_count)

    def _start_fetch(self, mode: str, symbol: str, timeframe: str, bar_count: int) -> None:
        if self._worker and self._worker.isRunning():
            return
        self._set_loading(True, f'Loading {symbol} {timeframe}...')
        self._worker = DataFetchWorker(mode, self.store, self.exchange, symbol, timeframe, bar_count)
        self._worker.data_ready.connect(self._on_data_ready)
        self._worker.error.connect(self._on_error)
        self._worker.finished.connect(self._on_fetch_finished)
        self._worker.start()

    def _on_data_ready(self, bars: list) -> None:
        if bars:
            try:
                self.candles.set_historical_data(bars)
            except Exception as exc:
                self._report_error(f'Chart render failed: {exc}')

    def _on_error(self, message: str) -> None:
        self.status_label.setText(f'Error: {message}')
        self.status_label.setStyleSheet('color: #EF5350;')
        self._report_error(message)

    def _on_fetch_finished(self) -> None:
        self._set_loading(False, '')

    def _set_loading(self, is_loading: bool, message: str) -> None:
        self.load_button.setEnabled(not is_loading)
        self.backfill_button.setEnabled(not is_loading)
        if is_loading:
            self.status_label.setText(message)
            self.status_label.setStyleSheet('color: #B2B5BE;')
        else:
            if not self.status_label.text().startswith('Error:'):
                self.status_label.setText('')

    def _report_error(self, message: str) -> None:
        if self.error_sink is not None:
            try:
                self.error_sink.append_error(message)
            except Exception:
                pass
