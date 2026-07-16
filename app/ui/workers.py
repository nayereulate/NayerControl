"""Generic background worker so blocking adb/scrcpy calls don't freeze the UI."""
from PySide6.QtCore import QThread, Signal


class Worker(QThread):
    succeeded = Signal(object)
    failed = Signal(str)

    def __init__(self, fn, *args, **kwargs):
        super().__init__()
        self.fn = fn
        self.args = args
        self.kwargs = kwargs

    def run(self):
        try:
            result = self.fn(*self.args, **self.kwargs)
        except Exception as exc:  # noqa: BLE001 - surfaced to the UI as a message
            self.failed.emit(str(exc))
        else:
            self.succeeded.emit(result)
