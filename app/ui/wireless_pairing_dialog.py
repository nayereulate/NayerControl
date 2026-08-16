"""Pair a phone using Android's native Wireless debugging (Android 11+).
Never requires a USB cable, and the resulting connection is independent of
any USB debugging session, so it survives unplugging/replugging fine."""
import re

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from .. import device_manager as dm
from .workers import Worker

STEP_PAIR_FORM, STEP_PAIRING, STEP_CONNECT_FORM, STEP_CONNECTING, STEP_DONE = range(5)


def _split_host_port(text: str) -> tuple[str, int]:
    """Parse an 'ip:port' string exactly as Android shows it on the Wireless
    debugging screens. Splits on the last ':' so it also works if a future
    Android version shows an IPv6 address."""
    text = text.strip()
    if ":" not in text:
        raise ValueError(f"Falta el puerto en '{text}'. Escribe la direccion completa, ej: 192.168.1.4:37181")
    host, _, port_text = text.rpartition(":")
    if not host or not port_text.isdigit():
        raise ValueError(f"'{text}' no es una direccion valida. Escribela como IP:puerto, ej: 192.168.1.4:37181")
    return host, int(port_text)


class WirelessPairingDialog(QDialog):
    """Pairing and connecting are kept as two separate steps (not one form
    submitted together): completing the pairing handshake can itself cause
    the phone's Wireless debugging connect port to change, so a connect
    address copied *before* pairing may already be stale by the time pairing
    finishes. Asking for it only after pairing succeeds avoids that race,
    and lets the user retry just the connect step without repeating the
    (single-use) pairing code."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Depuracion inalambrica (sin cable)")
        self.setMinimumWidth(480)
        self.setModal(True)

        self.result_device = None  # (serial, name, ip, port)
        self._worker: Worker | None = None
        self._name: str | None = None

        self.stack = QStackedWidget()
        self.stack.addWidget(self._build_pair_form_page())
        self.stack.addWidget(self._build_status_page("Emparejando..."))
        self.stack.addWidget(self._build_connect_form_page())
        self.stack.addWidget(self._build_status_page("Conectando..."))
        self.stack.addWidget(self._build_done_page())

        layout = QVBoxLayout(self)
        layout.addWidget(self.stack)

    # ---------- pages ----------

    def _build_pair_form_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        title = QLabel("Empareja tu celular sin cable")
        title.setStyleSheet("font-size: 15px; font-weight: 600;")

        steps = QLabel(
            "1. En tu celular: Ajustes > Sistema > Opciones de desarrollador >\n"
            "   Depuracion inalambrica.\n"
            "2. Toca 'Emparejar dispositivo con codigo de emparejamiento'. Copia\n"
            "   tal cual el texto 'IP address & Port' (ej: 192.168.1.4:37181) y\n"
            "   el codigo de 6 digitos que aparecen ahi."
        )
        steps.setWordWrap(True)
        steps.setStyleSheet("color: #888;")

        self.pair_addr_edit = QLineEdit()
        self.pair_addr_edit.setPlaceholderText("192.168.1.4:37181")

        self.code_edit = QLineEdit()
        self.code_edit.setPlaceholderText("123456")
        self.code_edit.setMaxLength(6)

        form = QFormLayout()
        form.addRow("IP:puerto de emparejamiento:", self.pair_addr_edit)
        form.addRow("Codigo (6 digitos):", self.code_edit)

        self.pair_error_label = QLabel("")
        self.pair_error_label.setStyleSheet("color: #c0392b;")
        self.pair_error_label.setWordWrap(True)

        pair_btn = QPushButton("Emparejar")
        pair_btn.setStyleSheet("font-weight: 600; padding: 8px;")
        pair_btn.clicked.connect(self._on_pair_clicked)
        cancel_btn = QPushButton("Cancelar")
        cancel_btn.clicked.connect(self.reject)

        btn_row = QHBoxLayout()
        btn_row.addWidget(cancel_btn)
        btn_row.addStretch()
        btn_row.addWidget(pair_btn)

        layout.addWidget(title)
        layout.addWidget(steps)
        layout.addLayout(form)
        layout.addWidget(self.pair_error_label)
        layout.addLayout(btn_row)
        return page

    def _build_connect_form_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        title = QLabel("Emparejamiento exitoso")
        title.setStyleSheet("font-size: 15px; font-weight: 600;")

        hint = QLabel(
            "Ahora vuelve a la pantalla principal de 'Depuracion inalambrica' "
            "en tu celular (sal de la pantalla de emparejamiento si sigues ahi) "
            "y copia tal cual el 'IP address & Port' que aparece arriba, junto "
            "al nombre del telefono. Puede ser distinto al que usaste para "
            "emparejar."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #888;")

        self.connect_addr_edit = QLineEdit()
        self.connect_addr_edit.setPlaceholderText("192.168.1.4:41235")

        form = QFormLayout()
        form.addRow("IP:puerto de conexion:", self.connect_addr_edit)

        self.connect_error_label = QLabel("")
        self.connect_error_label.setStyleSheet("color: #c0392b;")
        self.connect_error_label.setWordWrap(True)

        connect_btn = QPushButton("Conectar")
        connect_btn.setStyleSheet("font-weight: 600; padding: 8px;")
        connect_btn.clicked.connect(self._on_connect_clicked)
        cancel_btn = QPushButton("Cancelar")
        cancel_btn.clicked.connect(self.reject)

        btn_row = QHBoxLayout()
        btn_row.addWidget(cancel_btn)
        btn_row.addStretch()
        btn_row.addWidget(connect_btn)

        layout.addWidget(title)
        layout.addWidget(hint)
        layout.addLayout(form)
        layout.addWidget(self.connect_error_label)
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

    def _on_pair_clicked(self):
        code = self.code_edit.text().strip()
        if not code:
            self.pair_error_label.setText("Escribe el codigo de emparejamiento de 6 digitos.")
            return
        try:
            pair_ip, pair_port = _split_host_port(self.pair_addr_edit.text())
        except ValueError as exc:
            self.pair_error_label.setText(str(exc))
            return

        self.pair_error_label.setText("")
        self.stack.setCurrentIndex(STEP_PAIRING)
        self._worker = Worker(dm.pair, pair_ip, pair_port, code)
        self._worker.succeeded.connect(self._on_pair_success)
        self._worker.failed.connect(self._on_pair_failed)
        self._worker.start()

    def _on_pair_success(self, _result):
        self.connect_error_label.setText("")
        self.connect_addr_edit.setFocus()
        self.stack.setCurrentIndex(STEP_CONNECT_FORM)

    def _on_pair_failed(self, message: str):
        self.stack.setCurrentIndex(STEP_PAIR_FORM)
        self.pair_error_label.setText(message)

    def _on_connect_clicked(self):
        try:
            connect_ip, connect_port = _split_host_port(self.connect_addr_edit.text())
        except ValueError as exc:
            self.connect_error_label.setText(str(exc))
            return

        self.connect_error_label.setText("")
        self.stack.setCurrentIndex(STEP_CONNECTING)
        self._worker = Worker(self._connect, connect_ip, connect_port)
        self._worker.succeeded.connect(self._on_connect_success)
        self._worker.failed.connect(self._on_connect_failed)
        self._worker.start()

    @staticmethod
    def _connect(ip: str, port: int):
        dm.connect_tcpip(ip, port)
        serial = f"{ip}:{port}"
        name = dm.get_device_name(serial) or serial
        return serial, name, ip, port

    def _on_connect_success(self, payload):
        serial, name, ip, port = payload
        self.result_device = (serial, name, ip, port)
        self.done_message.setText(
            f"'{name}' quedo emparejado por Wi-Fi ({ip}:{port}), sin cable.\n"
            "Esta conexion no depende del cable USB, asi que no deberia "
            "cerrarse al desconectarlo."
        )
        self.stack.setCurrentIndex(STEP_DONE)

    def _on_connect_failed(self, message: str):
        self.stack.setCurrentIndex(STEP_CONNECT_FORM)
        self.connect_error_label.setText(
            f"{message}\n\nRevisa de nuevo la pantalla principal de Depuracion "
            "inalambrica en tu celular: el puerto puede cambiar cada vez que se "
            "actualiza esa pantalla. No hace falta repetir el emparejamiento."
        )


class UpdateAddressDialog(QDialog):
    """Android's Wireless debugging connect port changes over time (on Wi-Fi
    toggle, reboot, network change, etc.), unlike the old fixed-port `adb
    tcpip` trick. Once a phone has been paired, re-typing the code isn't
    needed again: this just updates the ip:port used to reconnect."""

    def __init__(self, current_ip: str, current_port: int, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Actualizar direccion de conexion")
        self.setMinimumWidth(420)
        self.setModal(True)
        self.new_ip: str | None = None
        self.new_port: int | None = None
        self._worker: Worker | None = None

        layout = QVBoxLayout(self)

        hint = QLabel(
            "El puerto de 'Depuracion inalambrica' de tu celular puede cambiar "
            "con el tiempo. En tu telefono, ve a Ajustes > Opciones de "
            "desarrollador > Depuracion inalambrica y copia el 'IP address & "
            "Port' que aparece arriba, junto al nombre del telefono."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #888;")
        layout.addWidget(hint)

        form = QFormLayout()
        self.addr_edit = QLineEdit(f"{current_ip}:{current_port}")
        form.addRow("IP:puerto de conexion:", self.addr_edit)
        layout.addLayout(form)

        self.error_label = QLabel("")
        self.error_label.setStyleSheet("color: #c0392b;")
        self.error_label.setWordWrap(True)
        layout.addWidget(self.error_label)

        update_btn = QPushButton("Actualizar y conectar")
        update_btn.setStyleSheet("font-weight: 600; padding: 8px;")
        update_btn.clicked.connect(self._on_update_clicked)
        cancel_btn = QPushButton("Cancelar")
        cancel_btn.clicked.connect(self.reject)

        btn_row = QHBoxLayout()
        btn_row.addWidget(cancel_btn)
        btn_row.addStretch()
        btn_row.addWidget(update_btn)
        layout.addLayout(btn_row)

    def _on_update_clicked(self):
        try:
            ip, port = _split_host_port(self.addr_edit.text())
        except ValueError as exc:
            self.error_label.setText(str(exc))
            return

        self.error_label.setText("")
        self._worker = Worker(self._resolve, ip, port)
        self._worker.succeeded.connect(lambda result: self._on_success(*result))
        self._worker.failed.connect(self._on_failed)
        self._worker.start()

    @staticmethod
    def _resolve(typed_ip: str, typed_port: int) -> tuple[str, int]:
        """Try automatic network discovery first: the ip:port the user just
        typed off the phone's screen may already be stale (Wireless
        debugging's address can change again right after toggling USB
        debugging). Only fall back to connecting with the typed value if
        nothing gets auto-discovered."""
        device = dm.find_wifi_device()
        if device:
            match = re.match(r"^(\d{1,3}(?:\.\d{1,3}){3}):(\d+)$", device.serial)
            if match:
                return match.group(1), int(match.group(2))
        dm.connect_tcpip(typed_ip, typed_port)
        return typed_ip, typed_port

    def _on_success(self, ip: str, port: int):
        self.new_ip = ip
        self.new_port = port
        self.accept()

    def _on_failed(self, message: str):
        self.error_label.setText(message)
