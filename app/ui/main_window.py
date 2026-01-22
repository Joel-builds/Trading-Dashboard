from PyQt6.QtWidgets import QMainWindow, QDockWidget
from PyQt6.QtCore import Qt

from .chart_view import ChartView
from .indicator_panel import IndicatorPanel
from .error_dock import ErrorDock


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle('Trading Dashboard')
        self.resize(1400, 900)

        self.indicator_panel = IndicatorPanel()
        self.error_dock = ErrorDock()
        self.chart_view = ChartView(error_sink=self.error_dock)
        self.setCentralWidget(self.chart_view)

        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.indicator_panel)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self.error_dock)

        self.tabifyDockWidget(self.indicator_panel, self.error_dock)
        self.indicator_panel.raise_()

