from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QSpinBox,
)

RESOLUTION_OPTIONS = {
    "Original (sin cambios)": 0,
    "1920 px (lado mayor)": 1920,
    "1280 px (lado mayor)": 1280,
    "1024 px (lado mayor)": 1024,
    "800 px (lado mayor)": 800,
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

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

        self.setLayout(form)

    def apply_to_config(self) -> dict:
        self.config["bitrate_mbps"] = self.bitrate_spin.value()
        self.config["max_size"] = RESOLUTION_OPTIONS[self.resolution_combo.currentText()]
        self.config["fullscreen"] = self.fullscreen_check.isChecked()
        self.config["turn_screen_off"] = self.screen_off_check.isChecked()
        self.config["stay_awake"] = self.stay_awake_check.isChecked()
        return self.config
