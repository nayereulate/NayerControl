from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QRadioButton,
    QStackedWidget,
    QSystemTrayIcon,
    QVBoxLayout,
    QWidget,
)

from .. import config as cfg
from .. import device_manager as dm
from .pairing_wizard import PairingWizard
from .settings_dialog import SettingsDialog
from .workers import Worker

STATUS_UNKNOWN = "gray"
STATUS_OK = "#2ecc71"
STATUS_ERROR = "#e74c3c"

MODE_USB, MODE_WIFI = "usb", "wifi"


class MainWindow(QMainWindow):
    def __init__(self, app_icon: QIcon):
        super().__init__()
        self.setWindowTitle("NayerControl - Control remoto de Android")
        self.setMinimumSize(540, 520)
        self.setWindowIcon(app_icon)

        self.config = cfg.load()
        self.selected_serial: str | None = self.config.get("last_device")
        self._worker: Worker | None = None

        self._build_ui(app_icon)
        self._refresh_wifi_combo()
        self._log("Bienvenido a NayerControl.")

        initial_mode = self.config.get("connection_mode", MODE_WIFI)
        (self.usb_radio if initial_mode == MODE_USB else self.wifi_radio).setChecked(True)

        if initial_mode == MODE_WIFI:
            if self.selected_serial:
                self._try_auto_reconnect()
            else:
                self._log("Conecta tu celular por primera vez con el asistente de la pestaña Wi-Fi.")

    # ---------------- UI ----------------

    def _build_ui(self, app_icon: QIcon):
        central = QWidget()
        layout = QVBoxLayout(central)
        layout.setSpacing(14)
        layout.setContentsMargins(20, 20, 20, 20)

        title = QLabel("NayerControl")
        title.setStyleSheet("font-size: 22px; font-weight: 700;")
        subtitle = QLabel("Controla tu Android por cable USB o de forma inalambrica")
        subtitle.setStyleSheet("color: #888;")
        layout.addWidget(title)
        layout.addWidget(subtitle)

        mode_box = QGroupBox("Modo de conexion")
        mode_layout = QHBoxLayout(mode_box)
        self.usb_radio = QRadioButton("USB (cable)")
        self.wifi_radio = QRadioButton("Wi-Fi (inalambrico)")
        self.mode_group = QButtonGroup(self)
        self.mode_group.addButton(self.usb_radio)
        self.mode_group.addButton(self.wifi_radio)
        self.usb_radio.toggled.connect(self._on_mode_toggled)
        self.wifi_radio.toggled.connect(self._on_mode_toggled)
        mode_layout.addWidget(self.usb_radio)
        mode_layout.addWidget(self.wifi_radio)
        mode_layout.addStretch()
        layout.addWidget(mode_box)

        self.mode_stack = QStackedWidget()
        self.mode_stack.addWidget(self._build_usb_page())
        self.mode_stack.addWidget(self._build_wifi_page())
        layout.addWidget(self.mode_stack)

        shared_row = QHBoxLayout()
        self.settings_btn = QPushButton("Ajustes de video")
        self.settings_btn.clicked.connect(self._on_settings_clicked)
        shared_row.addWidget(self.settings_btn)
        shared_row.addStretch()
        layout.addLayout(shared_row)

        log_box = QGroupBox("Estado")
        log_layout = QVBoxLayout(log_box)
        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumBlockCount(300)
        log_layout.addWidget(self.log_view)
        layout.addWidget(log_box, stretch=1)

        self.setCentralWidget(central)

        self.tray = QSystemTrayIcon(app_icon, self)
        self.tray.setToolTip("NayerControl")
        self.tray.activated.connect(self._on_tray_activated)
        self.tray.show()

    def _build_usb_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 8, 0, 0)

        hint = QLabel(
            "Conecta el celular con un cable USB y activa 'Depuracion USB' "
            "en Opciones de desarrollador. No necesitas configurar nada mas."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #888;")
        layout.addWidget(hint)

        row = QHBoxLayout()
        self.usb_device_combo = QComboBox()
        self.usb_refresh_btn = QPushButton("Actualizar")
        self.usb_refresh_btn.clicked.connect(self._refresh_usb_devices)
        row.addWidget(self.usb_device_combo, stretch=1)
        row.addWidget(self.usb_refresh_btn)
        layout.addLayout(row)

        self.usb_start_btn = QPushButton("Iniciar control remoto (USB)")
        self.usb_start_btn.setStyleSheet("font-weight: 600; padding: 10px;")
        self.usb_start_btn.setEnabled(False)
        self.usb_start_btn.clicked.connect(self._on_usb_start_clicked)
        layout.addWidget(self.usb_start_btn)

        return page

    def _build_wifi_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 8, 0, 0)

        device_box = QGroupBox("Dispositivo emparejado")
        device_layout = QVBoxLayout(device_box)

        row = QHBoxLayout()
        self.wifi_device_combo = QComboBox()
        self.wifi_device_combo.currentIndexChanged.connect(self._on_wifi_device_selected)
        row.addWidget(self.wifi_device_combo, stretch=1)
        device_layout.addLayout(row)

        status_row = QHBoxLayout()
        self.status_dot = QLabel("●")
        self.status_dot.setStyleSheet(f"color: {STATUS_UNKNOWN}; font-size: 16px;")
        self.status_label = QLabel("Sin comprobar")
        status_row.addWidget(self.status_dot)
        status_row.addWidget(self.status_label)
        status_row.addStretch()
        device_layout.addLayout(status_row)
        layout.addWidget(device_box)

        actions_box = QGroupBox("Acciones")
        actions_layout = QVBoxLayout(actions_box)

        self.wifi_start_btn = QPushButton("Iniciar control remoto")
        self.wifi_start_btn.setStyleSheet("font-weight: 600; padding: 10px;")
        self.wifi_start_btn.clicked.connect(self._on_wifi_start_clicked)
        actions_layout.addWidget(self.wifi_start_btn)

        btn_row = QHBoxLayout()
        self.wifi_reconnect_btn = QPushButton("Reconectar por Wi-Fi")
        self.wifi_reconnect_btn.clicked.connect(self._on_reconnect_clicked)
        self.wifi_add_device_btn = QPushButton("Conectar celular nuevo (USB)")
        self.wifi_add_device_btn.clicked.connect(self._on_add_device_clicked)
        btn_row.addWidget(self.wifi_reconnect_btn)
        btn_row.addWidget(self.wifi_add_device_btn)
        actions_layout.addLayout(btn_row)

        self.wifi_forget_btn = QPushButton("Olvidar este dispositivo")
        self.wifi_forget_btn.clicked.connect(self._on_forget_clicked)
        actions_layout.addWidget(self.wifi_forget_btn)

        layout.addWidget(actions_box)
        return page

    # ---------------- helpers ----------------

    def _log(self, message: str):
        self.log_view.appendPlainText(message)

    def _set_status(self, ok: bool, text: str):
        self.status_dot.setStyleSheet(
            f"color: {STATUS_OK if ok else STATUS_ERROR}; font-size: 16px;"
        )
        self.status_label.setText(text)

    def _run_worker(self, fn, on_success, on_error, *args):
        self._set_buttons_enabled(False)
        self._worker = Worker(fn, *args)
        self._worker.succeeded.connect(lambda r: (self._set_buttons_enabled(True), on_success(r)))
        self._worker.failed.connect(lambda e: (self._set_buttons_enabled(True), on_error(e)))
        self._worker.start()

    def _set_buttons_enabled(self, enabled: bool):
        for btn in (
            self.usb_refresh_btn,
            self.usb_start_btn,
            self.wifi_start_btn,
            self.wifi_reconnect_btn,
            self.wifi_add_device_btn,
            self.wifi_forget_btn,
            self.settings_btn,
        ):
            btn.setEnabled(enabled)

    # ---------------- mode switching ----------------

    def _on_mode_toggled(self, checked: bool):
        if not checked:
            return
        mode = MODE_USB if self.usb_radio.isChecked() else MODE_WIFI
        self.mode_stack.setCurrentIndex(0 if mode == MODE_USB else 1)
        self.config["connection_mode"] = mode
        cfg.save(self.config)
        if mode == MODE_USB:
            self._refresh_usb_devices()

    # ---------------- USB mode ----------------

    def _refresh_usb_devices(self):
        self._log("Buscando dispositivos USB...")
        self._run_worker(
            dm.list_usb_devices,
            self._on_usb_devices_found,
            self._on_usb_devices_failed,
        )

    def _on_usb_devices_found(self, devices: list[dm.Device]):
        self.usb_device_combo.clear()
        for device in devices:
            self.usb_device_combo.addItem(f"{device.name}  ({device.serial})", userData=device.serial)
        has_devices = len(devices) > 0
        self.usb_start_btn.setEnabled(has_devices)
        if has_devices:
            self._log(f"{len(devices)} dispositivo(s) USB detectado(s).")
        else:
            pending = dm.list_unauthorized()
            if pending:
                self._log(
                    "El celular pidio autorizacion. Acepta 'Permitir depuracion USB' "
                    "en la pantalla del telefono y pulsa 'Actualizar'."
                )
            else:
                self._log(
                    "No se detecto ningun celular por USB. Conecta el cable y activa "
                    "la Depuracion USB."
                )

    def _on_usb_devices_failed(self, error: str):
        self.usb_device_combo.clear()
        self.usb_start_btn.setEnabled(False)
        self._log(f"Error al buscar dispositivos USB: {error}")

    def _on_usb_start_clicked(self):
        serial = self.usb_device_combo.currentData()
        if not serial:
            return
        try:
            dm.launch_mirror(serial, self.config)
            self._log(f"Ventana de control remoto abierta (USB, {serial}).")
        except dm.DeviceError as exc:
            self._log(f"Error al iniciar scrcpy: {exc}")
            QMessageBox.critical(self, "Error", str(exc))

    # ---------------- Wi-Fi mode ----------------

    def _refresh_wifi_combo(self):
        self.wifi_device_combo.blockSignals(True)
        self.wifi_device_combo.clear()
        devices = self.config.get("devices", {})
        for serial, info in devices.items():
            self.wifi_device_combo.addItem(f"{info['name']}  ({info['ip']})", userData=serial)
        self.wifi_device_combo.blockSignals(False)

        if self.selected_serial and self.selected_serial in devices:
            index = self.wifi_device_combo.findData(self.selected_serial)
            if index >= 0:
                self.wifi_device_combo.setCurrentIndex(index)
        elif self.wifi_device_combo.count() > 0:
            self.wifi_device_combo.setCurrentIndex(0)
            self.selected_serial = self.wifi_device_combo.currentData()
        else:
            self.selected_serial = None

        has_devices = self.wifi_device_combo.count() > 0
        self.wifi_start_btn.setEnabled(has_devices)
        self.wifi_reconnect_btn.setEnabled(has_devices)
        self.wifi_forget_btn.setEnabled(has_devices)

    def _on_wifi_device_selected(self, _index: int):
        self.selected_serial = self.wifi_device_combo.currentData()
        self.config["last_device"] = self.selected_serial
        cfg.save(self.config)
        self._set_status(False, "Sin comprobar")

    def _current_device_info(self) -> dict | None:
        if not self.selected_serial:
            return None
        return self.config.get("devices", {}).get(self.selected_serial)

    def _try_auto_reconnect(self):
        info = self._current_device_info()
        if not info:
            return
        self._log(f"Reconectando con '{info['name']}' por Wi-Fi...")
        self._run_worker(
            dm.connect_tcpip,
            lambda _: self._set_status(True, f"Conectado ({info['ip']})"),
            lambda err: self._set_status(False, "No disponible - usa 'Reconectar por Wi-Fi'"),
            info["ip"],
            info["port"],
        )

    def _on_reconnect_clicked(self):
        info = self._current_device_info()
        if not info:
            return
        self._log(f"Conectando con '{info['name']}' ({info['ip']}:{info['port']})...")
        self._run_worker(
            dm.connect_tcpip,
            self._on_reconnect_success,
            self._on_reconnect_failed,
            info["ip"],
            info["port"],
        )

    def _on_reconnect_success(self, _result):
        info = self._current_device_info()
        self._set_status(True, f"Conectado ({info['ip']})")
        self._log("Conexion establecida.")

    def _on_reconnect_failed(self, error: str):
        self._set_status(False, "Desconectado")
        self._log(f"No se pudo reconectar: {error}")
        self._log("Sugerencia: si el celular cambio de red Wi-Fi, vuelve a emparejarlo por USB.")

    def _on_add_device_clicked(self):
        wizard = PairingWizard(self)
        if wizard.exec() == PairingWizard.Accepted and wizard.result_device:
            serial, name, ip, port = wizard.result_device
            cfg.remember_device(self.config, serial, name, ip, port)
            self.selected_serial = serial
            self._refresh_wifi_combo()
            self._set_status(True, f"Conectado ({ip})")
            self._log(f"'{name}' agregado y conectado por Wi-Fi.")

    def _on_wifi_start_clicked(self):
        info = self._current_device_info()
        if not info:
            return
        self._log("Iniciando control remoto...")
        self._run_worker(
            self._ensure_connected_and_launch,
            self._on_launch_success,
            self._on_launch_failed,
            self.selected_serial,
            info,
        )

    @staticmethod
    def _ensure_connected_and_launch(serial: str, info: dict):
        connected = any(d.serial in (serial, f"{info['ip']}:{info['port']}") for d in dm.list_devices())
        if not connected:
            dm.connect_tcpip(info["ip"], info["port"])
        target = f"{info['ip']}:{info['port']}"
        matches = [d for d in dm.list_devices() if d.serial == target]
        real_serial = matches[0].serial if matches else target
        return real_serial

    def _on_launch_success(self, real_serial: str):
        self._set_status(True, "Conectado")
        try:
            dm.launch_mirror(real_serial, self.config)
            self._log("Ventana de control remoto abierta.")
        except dm.DeviceError as exc:
            self._log(f"Error al iniciar scrcpy: {exc}")
            QMessageBox.critical(self, "Error", str(exc))

    def _on_launch_failed(self, error: str):
        self._set_status(False, "Desconectado")
        self._log(f"No se pudo conectar: {error}")
        QMessageBox.warning(
            self,
            "No se pudo conectar",
            "No se pudo conectar con el celular por Wi-Fi.\n\n"
            "Verifica que este encendido y en la misma red Wi-Fi, o vuelve a "
            "emparejarlo con 'Conectar celular nuevo (USB)'.",
        )

    def _on_settings_clicked(self):
        dialog = SettingsDialog(self.config, self)
        if dialog.exec() == SettingsDialog.Accepted:
            self.config = dialog.apply_to_config()
            cfg.save(self.config)
            self._log("Ajustes guardados.")

    def _on_forget_clicked(self):
        info = self._current_device_info()
        if not info:
            return
        confirm = QMessageBox.question(
            self,
            "Olvidar dispositivo",
            f"¿Olvidar '{info['name']}'? Tendras que emparejarlo de nuevo por USB.",
        )
        if confirm == QMessageBox.Yes:
            cfg.forget_device(self.config, self.selected_serial)
            self.selected_serial = self.config.get("last_device")
            self._refresh_wifi_combo()
            self._set_status(False, "Sin comprobar")
            self._log(f"'{info['name']}' olvidado.")

    def _on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.Trigger:
            self.showNormal()
            self.activateWindow()

    def closeEvent(self, event):
        self.tray.hide()
        event.accept()
