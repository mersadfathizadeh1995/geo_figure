"""Settings dialog for external tool paths (Geopsy, bash)."""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QLineEdit,
    QPushButton, QHBoxLayout, QDialogButtonBox, QGroupBox,
    QFileDialog, QLabel
)
from PySide6.QtCore import QSettings


SETTINGS_KEY_GEOPSY_BIN = "paths/geopsy_bin"
SETTINGS_KEY_BASH = "paths/bash_exe"


def get_geopsy_bin() -> str:
    return QSettings("GeoFigure", "GeoFigure").value(SETTINGS_KEY_GEOPSY_BIN, "")


def get_bash_exe() -> str:
    return QSettings("GeoFigure", "GeoFigure").value(SETTINGS_KEY_BASH, "")


class SettingsDialog(QDialog):
    """Dialog to configure external tool paths."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setMinimumWidth(520)
        self._setup_ui()
        self._load_settings()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # Paths group
        paths_group = QGroupBox("External Tool Paths")
        form = QFormLayout(paths_group)

        # Geopsy bin directory
        geopsy_row = QHBoxLayout()
        self.geopsy_edit = QLineEdit()
        self.geopsy_edit.setPlaceholderText("e.g. C:\\geopsypack-win64-3.4.2\\bin")
        geopsy_row.addWidget(self.geopsy_edit)
        geopsy_btn = QPushButton("Browse...")
        geopsy_btn.clicked.connect(self._browse_geopsy)
        geopsy_row.addWidget(geopsy_btn)
        form.addRow("Geopsy bin:", geopsy_row)

        # Bash executable
        bash_row = QHBoxLayout()
        self.bash_edit = QLineEdit()
        self.bash_edit.setPlaceholderText("e.g. C:\\Users\\...\\Git\\bin\\bash.exe")
        bash_row.addWidget(self.bash_edit)
        bash_btn = QPushButton("Browse...")
        bash_btn.clicked.connect(self._browse_bash)
        bash_row.addWidget(bash_btn)
        form.addRow("Bash:", bash_row)

        info = QLabel(
            "These paths are used for extracting theoretical curves and "
            "Vs profiles from Geopsy .report files."
        )
        info.setWordWrap(True)
        info.setStyleSheet("color: #888888; font-size: 11px;")
        form.addRow(info)

        layout.addWidget(paths_group)

        # Dialog buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(self._save_and_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _browse_geopsy(self):
        path = QFileDialog.getExistingDirectory(
            self, "Select Geopsy bin Directory", self.geopsy_edit.text()
        )
        if path:
            self.geopsy_edit.setText(path)

    def _browse_bash(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select bash.exe",
            self.bash_edit.text(),
            "Executable (*.exe);;All files (*.*)"
        )
        if path:
            self.bash_edit.setText(path)

    def _load_settings(self):
        self.geopsy_edit.setText(get_geopsy_bin())
        self.bash_edit.setText(get_bash_exe())

    def _save_and_accept(self):
        settings = QSettings("GeoFigure", "GeoFigure")
        settings.setValue(SETTINGS_KEY_GEOPSY_BIN, self.geopsy_edit.text().strip())
        settings.setValue(SETTINGS_KEY_BASH, self.bash_edit.text().strip())
        self.accept()
