"""Project setup dialog — shown on app startup to set project directory."""
import os
from pathlib import Path

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLineEdit,
    QPushButton, QFileDialog, QDialogButtonBox, QLabel, QGroupBox,
)
from PySide6.QtCore import QSettings


SETTINGS_KEY_LAST_PROJECT_DIR = "project/last_dir"
SETTINGS_KEY_LAST_PROJECT_NAME = "project/last_name"


class ProjectDialog(QDialog):
    """Dialog to configure the project directory and name."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("GeoFigure - Project Setup")
        self.setMinimumWidth(480)
        self._setup_ui()
        self._load_defaults()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        info = QLabel(
            "Set a project directory where GeoFigure will store all files "
            "(theoretical curves, CSVs, session data). These files persist "
            "after closing the app."
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        group = QGroupBox("Project")
        form = QFormLayout(group)

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("e.g. Site_A_Analysis")
        form.addRow("Project Name:", self.name_edit)

        dir_row = QHBoxLayout()
        self.dir_edit = QLineEdit()
        self.dir_edit.setPlaceholderText("Select a directory...")
        dir_row.addWidget(self.dir_edit)
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self._browse_dir)
        dir_row.addWidget(browse_btn)
        form.addRow("Directory:", dir_row)

        self.resolved_label = QLabel("")
        self.resolved_label.setStyleSheet("color: #666666; font-size: 11px;")
        self.resolved_label.setWordWrap(True)
        form.addRow("Full Path:", self.resolved_label)

        layout.addWidget(group)

        # Update resolved path on edits
        self.name_edit.textChanged.connect(self._update_resolved)
        self.dir_edit.textChanged.connect(self._update_resolved)

        # Buttons
        btn_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        btn_box.accepted.connect(self._on_accept)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

    def _browse_dir(self):
        path = QFileDialog.getExistingDirectory(
            self, "Select Project Directory", self.dir_edit.text()
        )
        if path:
            self.dir_edit.setText(path)

    def _update_resolved(self):
        base = self.dir_edit.text().strip()
        name = self.name_edit.text().strip()
        if base and name:
            self.resolved_label.setText(str(Path(base) / name))
        elif base:
            self.resolved_label.setText(base)
        else:
            self.resolved_label.setText("")

    def _load_defaults(self):
        s = QSettings("GeoFigure", "GeoFigure")
        last_dir = s.value(SETTINGS_KEY_LAST_PROJECT_DIR, "")
        last_name = s.value(SETTINGS_KEY_LAST_PROJECT_NAME, "")
        if last_dir:
            self.dir_edit.setText(last_dir)
        if last_name:
            self.name_edit.setText(last_name)
        self._update_resolved()

    def _on_accept(self):
        base = self.dir_edit.text().strip()
        name = self.name_edit.text().strip()
        if not base:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Error", "Please select a project directory.")
            return
        if not name:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Error", "Please enter a project name.")
            return

        # Save for next launch
        s = QSettings("GeoFigure", "GeoFigure")
        s.setValue(SETTINGS_KEY_LAST_PROJECT_DIR, base)
        s.setValue(SETTINGS_KEY_LAST_PROJECT_NAME, name)

        # Create project directory structure
        project_dir = Path(base) / name
        project_dir.mkdir(parents=True, exist_ok=True)
        (project_dir / "theoretical").mkdir(exist_ok=True)
        (project_dir / "experimental").mkdir(exist_ok=True)
        (project_dir / "figures").mkdir(exist_ok=True)
        (project_dir / "csv").mkdir(exist_ok=True)
        (project_dir / "session").mkdir(exist_ok=True)

        self.accept()

    def get_project_dir(self) -> Path:
        """Return the full project directory path."""
        base = self.dir_edit.text().strip()
        name = self.name_edit.text().strip()
        return Path(base) / name

    def get_project_name(self) -> str:
        return self.name_edit.text().strip()
