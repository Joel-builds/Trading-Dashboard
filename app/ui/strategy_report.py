from __future__ import annotations

from typing import List

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QDockWidget, QTableWidget, QTableWidgetItem, QVBoxLayout, QLabel, QWidget

from core.strategies.report import StrategyReport
from .strategy_equity import StrategyEquityWidget


class StrategyReportDock(QDockWidget):
    trade_selected = pyqtSignal(int)

    def __init__(self) -> None:
        super().__init__("Strategy Report")
        self.setObjectName("StrategyReportDock")
        self._trades: List = []

        container = QWidget()
        layout = QVBoxLayout(container)
        self.stats_label = QLabel("Run a strategy to see stats.")
        layout.addWidget(self.stats_label)

        self.equity_widget = StrategyEquityWidget()
        layout.addWidget(self.equity_widget)

        self.trades_table = QTableWidget(0, 6)
        self.trades_table.setHorizontalHeaderLabels(["Side", "Entry", "Exit", "Size", "PnL", "Bars"])
        self.trades_table.cellClicked.connect(self._on_trade_clicked)
        layout.addWidget(self.trades_table)

        self.setWidget(container)

    def set_report(self, report: StrategyReport) -> None:
        self._trades = list(report.trades)
        stats = report.stats
        self.stats_label.setText(
            f"Return: {stats.get('total_return_pct', 0):.2f}% | "
            f"Max DD: {stats.get('max_drawdown_pct', 0):.2f}% | "
            f"Trades: {int(stats.get('num_trades', 0))} | "
            f"Win rate: {stats.get('win_rate_pct', 0):.1f}% | "
            f"PF: {stats.get('profit_factor', 0):.2f}"
        )
        self.equity_widget.set_equity(report.equity_ts, report.equity)

        self.trades_table.setRowCount(0)
        for trade in report.trades:
            row = self.trades_table.rowCount()
            self.trades_table.insertRow(row)
            self.trades_table.setItem(row, 0, QTableWidgetItem(trade.side))
            self.trades_table.setItem(row, 1, QTableWidgetItem(str(trade.entry_ts)))
            self.trades_table.setItem(row, 2, QTableWidgetItem(str(trade.exit_ts)))
            self.trades_table.setItem(row, 3, QTableWidgetItem(f"{trade.size:.4f}"))
            self.trades_table.setItem(row, 4, QTableWidgetItem(f"{trade.pnl:.2f}"))
            self.trades_table.setItem(row, 5, QTableWidgetItem(str(trade.bars_held)))

    def _on_trade_clicked(self, row: int, _column: int) -> None:
        if row < 0 or row >= len(self._trades):
            return
        trade = self._trades[row]
        try:
            ts = int(trade.entry_ts)
        except Exception:
            return
        self.trade_selected.emit(ts)
