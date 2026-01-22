from PyQt6.QtWidgets import QDockWidget, QTextEdit


class ErrorDock(QDockWidget):
    def __init__(self) -> None:
        super().__init__('Errors')
        self.setObjectName('ErrorDock')

        self.text = QTextEdit()
        self.text.setReadOnly(True)
        self.text.setPlaceholderText('Indicator errors will appear here.')
        self.setWidget(self.text)

    def append_error(self, message: str) -> None:
        self.text.append(message)
