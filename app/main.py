import sys
from pathlib import Path

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from app.ui.main_window import MainWindow
else:
    from .ui.main_window import MainWindow


def _icon_path() -> Path:
    if getattr(sys, "frozen", False):
        base = Path(sys._MEIPASS)  # type: ignore[attr-defined]
    else:
        base = Path(__file__).resolve().parent.parent / "resources"
    return base / "icon.ico"


def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(True)

    icon = QIcon(str(_icon_path()))
    window = MainWindow(icon)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
