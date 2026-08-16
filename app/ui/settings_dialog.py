from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QSpinBox,
    QVBoxLayout,
)

RESOLUTION_OPTIONS = {
    "Original (sin cambios)": 0,
    "1920 px (lado mayor)": 1920,
    "1280 px (lado mayor)": 1280,
    "1024 px (lado mayor)": 1024,
    "800 px (lado mayor)": 800,
}

WIFI_RESOLUTION_OPTIONS = {
    "Original (sin cambios)": 0,
    "1280 px (lado mayor)": 1280,
    "1024 px (lado mayor)": 1024,
    "800 px (lado mayor)": 800,
    "640 px (lado mayor)": 640,
}

FPS_OPTIONS = {
    "Sin limite": 0,
    "60 fps": 60,
    "30 fps": 30,
    "24 fps": 24,
    "15 fps": 15,
}


class SettingsDialog(QDialog):
    def __init__(self, config: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Ajustes de video")
        self.config = config

        self.bitrate_spin = QSpinBox()
        self.bitrate_spin.setRange(1, 50)
        self.bitrate_spin.setSuffix(" Mbps")
        self.bitrate_spin.setValue(config.get("bitrate_mbps", 8))

        self.resolution_combo = QComboBox()
        self.resolution_combo.addItems(list(RESOLUTION_OPTIONS.keys()))
        current_max_size = config.get("max_size", 0)
        for label, value in RESOLUTION_OPTIONS.items():
            if value == current_max_size:
                self.resolution_combo.setCurrentText(label)
                break

        self.fullscreen_check = QCheckBox("Iniciar en pantalla completa")
        self.fullscreen_check.setChecked(config.get("fullscreen", False))

        self.screen_off_check = QCheckBox("Apagar la pantalla del celular al conectar")
        self.screen_off_check.setChecked(config.get("turn_screen_off", False))

        self.stay_awake_check = QCheckBox("Mantener el celular activo mientras esta conectado")
        self.stay_awake_check.setChecked(config.get("stay_awake", True))

        form = QFormLayout()
        form.addRow("Calidad de video:", self.bitrate_spin)
        form.addRow("Resolucion maxima:", self.resolution_combo)
        form.addRow(self.fullscreen_check)
        form.addRow(self.screen_off_check)
        form.addRow(self.stay_awake_check)

        self.wifi_optimize_check = QCheckBox("Optimizar automaticamente para Wi-Fi (recomendado)")
        self.wifi_optimize_check.setChecked(config.get("wifi_optimize", True))
        self.wifi_optimize_check.toggled.connect(self._on_wifi_optimize_toggled)

        self.wifi_bitrate_spin = QSpinBox()
        self.wifi_bitrate_spin.setRange(1, 50)
        self.wifi_bitrate_spin.setSuffix(" Mbps")
        self.wifi_bitrate_spin.setValue(config.get("wifi_bitrate_mbps", 6))

        self.wifi_resolution_combo = QComboBox()
        self.wifi_resolution_combo.addItems(list(WIFI_RESOLUTION_OPTIONS.keys()))
        current_wifi_size = config.get("wifi_max_size", 1280)
        for label, value in WIFI_RESOLUTION_OPTIONS.items():
            if value == current_wifi_size:
                self.wifi_resolution_combo.setCurrentText(label)
                break

        self.wifi_fps_combo = QComboBox()
        self.wifi_fps_combo.addItems(list(FPS_OPTIONS.keys()))
        current_wifi_fps = config.get("wifi_max_fps", 30)
        for label, value in FPS_OPTIONS.items():
            if value == current_wifi_fps:
                self.wifi_fps_combo.setCurrentText(label)
                break

        self.wifi_no_audio_check = QCheckBox("Sin audio por Wi-Fi (ahorra ancho de banda)")
        self.wifi_no_audio_check.setChecked(config.get("wifi_no_audio", True))

        wifi_box = QGroupBox("Rendimiento por Wi-Fi")
        wifi_form = QFormLayout()
        wifi_form.addRow(self.wifi_optimize_check)
        wifi_form.addRow("Calidad de video:", self.wifi_bitrate_spin)
        wifi_form.addRow("Resolucion maxima:", self.wifi_resolution_combo)
        wifi_form.addRow("Cuadros por segundo:", self.wifi_fps_combo)
        wifi_form.addRow(self.wifi_no_audio_check)
        wifi_box.setLayout(wifi_form)
        self._on_wifi_optimize_toggled(self.wifi_optimize_check.isChecked())

        outer = QVBoxLayout(self)
        outer.addLayout(form)
        outer.addWidget(wifi_box)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        outer.addWidget(buttons)

    def _on_wifi_optimize_toggled(self, checked: bool):
        for widget in (
            self.wifi_bitrate_spin,
            self.wifi_resolution_combo,
            self.wifi_fps_combo,
            self.wifi_no_audio_check,
        ):
            widget.setEnabled(checked)

    def apply_to_config(self) -> dict:
        self.config["bitrate_mbps"] = self.bitrate_spin.value()
        self.config["max_size"] = RESOLUTION_OPTIONS[self.resolution_combo.currentText()]
        self.config["fullscreen"] = self.fullscreen_check.isChecked()
        self.config["turn_screen_off"] = self.screen_off_check.isChecked()
        self.config["stay_awake"] = self.stay_awake_check.isChecked()
        self.config["wifi_optimize"] = self.wifi_optimize_check.isChecked()
        self.config["wifi_bitrate_mbps"] = self.wifi_bitrate_spin.value()
        self.config["wifi_max_size"] = WIFI_RESOLUTION_OPTIONS[self.wifi_resolution_combo.currentText()]
        self.config["wifi_max_fps"] = FPS_OPTIONS[self.wifi_fps_combo.currentText()]
        self.config["wifi_no_audio"] = self.wifi_no_audio_check.isChecked()
        return self.config
