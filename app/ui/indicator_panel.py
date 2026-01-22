from PyQt6.QtWidgets import QDockWidget, QWidget, QVBoxLayout, QLabel, QListWidget


class IndicatorPanel(QDockWidget):
    def __init__(self) -> None:
        super().__init__('Indicators')
        self.setObjectName('IndicatorPanel')

        container = QWidget()
        layout = QVBoxLayout(container)

        layout.addWidget(QLabel('Available Indicators'))
        self.indicator_list = QListWidget()
        layout.addWidget(self.indicator_list)

        layout.addWidget(QLabel('Parameters'))
        self.params_placeholder = QLabel('Select an indicator to edit parameters.')
        self.params_placeholder.setWordWrap(True)
        layout.addWidget(self.params_placeholder)

        self.setWidget(container)
