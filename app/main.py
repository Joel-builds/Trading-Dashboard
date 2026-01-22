import os
from PyQt6.QtWidgets import QApplication
from ui.main_window import MainWindow

def main():
    app = QApplication([])
    qss_path = os.path.join(os.path.dirname(__file__), 'ui', 'theme', 'app.qss')
    if os.path.exists(qss_path):
        with open(qss_path, 'r', encoding='utf-8') as handle:
            app.setStyleSheet(handle.read())
    window = MainWindow()
    window.show()
    app.exec()

if __name__ == '__main__':
    main()
