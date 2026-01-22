from PyQt6.QtWidgets import QDockWidget, QTextEdit


class DebugDock(QDockWidget):
    def __init__(self) -> None:
        super().__init__('Debug')
        self.setObjectName('DebugDock')

        self.text = QTextEdit()
        self.text.setReadOnly(True)
        self.text.setPlaceholderText('Debug metrics will appear here.')
        self.setWidget(self.text)

    def set_metrics(self, lines: list[str]) -> None:
        self.text.setPlainText('\n'.join(lines))
