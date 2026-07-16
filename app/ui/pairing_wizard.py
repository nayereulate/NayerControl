"""First-time setup wizard: pair a phone over USB, then switch it to Wi-Fi."""
import time

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from .. import device_manager as dm
from .workers import Worker

STEP_INSTRUCTIONS, STEP_SEARCHING, STEP_CONFIGURING, STEP_DONE = range(4)


class PairingWizard(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Conectar un celular nuevo")
        self.setMinimumWidth(460)
        self.setModal(True)

        self.result_device = None  # (serial, name, ip, port)
        self._worker: Worker | None = None

        self.stack = QStackedWidget()
        self.stack.addWidget(self._build_instructions_page())
        self.stack.addWidget(self._build_status_page("Buscando el dispositivo..."))
        self.stack.addWidget(self._build_status_page("Configurando Wi-Fi..."))
        self.stack.addWidget(self._build_done_page())

        layout = QVBoxLayout(self)
        layout.addWidget(self.stack)

    # ---------- pages ----------

    def _build_instructions_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        title = QLabel("Paso 1 de 2: conecta el cable USB")
        title.setStyleSheet("font-size: 15px; font-weight: 600;")

        steps = QLabel(
            "1. En tu celular, activa las Opciones de desarrollador\n"
            "   (Ajustes > Acerca del telefono > toca 7 veces 'Numero de compilacion').\n"
            "2. Dentro de Opciones de desarrollador, activa 'Depuracion USB'.\n"
            "3. Conecta el celular a este PC con un cable USB.\n"
            "4. Cuando el celular muestre 'Permitir depuracion USB', acepta y marca\n"
            "   'Permitir siempre desde este equipo'.\n"
            "5. Asegurate de que el celular y el PC esten en la misma red Wi-Fi."
        )
        steps.setWordWrap(True)

        self.instructions_error = QLabel("")
        self.instructions_error.setStyleSheet("color: #c0392b;")
        self.instructions_error.setWordWrap(True)

        search_btn = QPushButton("Buscar dispositivo")
        search_btn.clicked.connect(self._start_search)

        cancel_btn = QPushButton("Cancelar")
        cancel_btn.clicked.connect(self.reject)

        btn_row = QHBoxLayout()
        btn_row.addWidget(cancel_btn)
        btn_row.addStretch()
        btn_row.addWidget(search_btn)

        layout.addWidget(title)
        layout.addWidget(steps)
        layout.addWidget(self.instructions_error)
        layout.addLayout(btn_row)
        return page

    def _build_status_page(self, text: str) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setAlignment(Qt.AlignCenter)
        label = QLabel(text)
        label.setAlignment(Qt.AlignCenter)
        label.setStyleSheet("font-size: 14px;")
        layout.addWidget(label)
        return page

    def _build_done_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        title = QLabel("Listo")
        title.setStyleSheet("font-size: 15px; font-weight: 600;")
        self.done_message = QLabel("")
        self.done_message.setWordWrap(True)
        finish_btn = QPushButton("Finalizar")
        finish_btn.clicked.connect(self.accept)

        layout.addWidget(title)
        layout.addWidget(self.done_message)
        layout.addStretch()
        layout.addWidget(finish_btn, alignment=Qt.AlignRight)
        return page

    # ---------- logic ----------

    def _start_search(self):
        self.instructions_error.setText("")
        self.stack.setCurrentIndex(STEP_SEARCHING)
        self._worker = Worker(dm.find_authorized_usb_device)
        self._worker.succeeded.connect(self._on_device_found)
        self._worker.failed.connect(self._on_search_failed)
        self._worker.start()

    def _on_search_failed(self, message: str):
        self.stack.setCurrentIndex(STEP_INSTRUCTIONS)
        self.instructions_error.setText(message)

    def _on_device_found(self, device: dm.Device):
        self.stack.setCurrentIndex(STEP_CONFIGURING)
        self._worker = Worker(self._configure_wifi, device)
        self._worker.succeeded.connect(self._on_wifi_ready)
        self._worker.failed.connect(self._on_wifi_failed)
        self._worker.start()

    @staticmethod
    def _configure_wifi(device: dm.Device):
        ip = dm.get_device_ip(device.serial)
        if not ip:
            raise dm.DeviceError(
                "No se pudo obtener la IP Wi-Fi del celular. Verifica que este "
                "conectado a una red Wi-Fi (no datos moviles) e intenta de nuevo."
            )
        dm.enable_tcpip(device.serial, dm.DEFAULT_TCPIP_PORT)
        time.sleep(2)
        dm.connect_tcpip(ip, dm.DEFAULT_TCPIP_PORT)
        return device, ip, dm.DEFAULT_TCPIP_PORT

    def _on_wifi_failed(self, message: str):
        self.stack.setCurrentIndex(STEP_INSTRUCTIONS)
        self.instructions_error.setText(message)

    def _on_wifi_ready(self, payload):
        device, ip, port = payload
        self.result_device = (device.serial, device.name, ip, port)
        self.done_message.setText(
            f"'{device.name}' quedo conectado por Wi-Fi ({ip}:{port}).\n"
            "Ya puedes desconectar el cable USB. La proxima vez la app se "
            "conectara sola, sin necesidad de cable."
        )
        self.stack.setCurrentIndex(STEP_DONE)
