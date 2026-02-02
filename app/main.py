import os
import faulthandler
import sys
import traceback
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QIcon
from ui.main_window import MainWindow

def _install_exception_logging() -> None:
    log_path = os.path.join(os.path.dirname(__file__), "exception.log")
    def _hook(exc_type, exc_value, exc_tb):
        try:
            with open(log_path, "a", encoding="utf-8") as handle:
                handle.write("\n=== Unhandled Exception ===\n")
                traceback.print_exception(exc_type, exc_value, exc_tb, file=handle)
        except Exception:
            pass
    sys.excepthook = _hook
    try:
        import threading
        def _thread_hook(args):
            _hook(args.exc_type, args.exc_value, args.exc_traceback)
        threading.excepthook = _thread_hook
    except Exception:
        pass


def main():
    try:
        log_path = os.path.join(os.path.dirname(__file__), "faulthandler.log")
        faulthandler.enable(open(log_path, "a"))
    except Exception:
        faulthandler.enable()
    _install_exception_logging()
    app = QApplication([])
    qss_path = os.path.join(os.path.dirname(__file__), 'ui', 'theme', 'app.qss')
    if os.path.exists(qss_path):
        with open(qss_path, 'r', encoding='utf-8') as handle:
            app.setStyleSheet(handle.read())
    icon_path = os.path.join(os.path.dirname(__file__), 'ui', 'theme', 'pysuperchart.png')
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))
    window = MainWindow()
    window.show()
    app.exec()

if __name__ == '__main__':
    main()
