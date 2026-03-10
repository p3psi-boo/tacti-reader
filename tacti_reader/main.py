import sys

from PyQt5.QtWidgets import QApplication

from .main_window import TactiReader


def run() -> int:
    app = QApplication(sys.argv)
    initial_pdf = sys.argv[1] if len(sys.argv) > 1 else None
    window = TactiReader(initial_pdf)
    window.show()
    return app.exec_()


if __name__ == "__main__":
    sys.exit(run())
