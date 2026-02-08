"""Export panel — format, quality presets, transparent, batch export."""
import os
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout, QComboBox, QCheckBox,
    QGroupBox, QPushButton, QFileDialog, QLabel, QHBoxLayout,
)
from PySide6.QtCore import Signal

FORMATS = ["PNG", "PDF", "SVG", "EPS", "TIFF"]
QUALITY_PRESETS = {
    "Draft (150 DPI)": 150,
    "Presentation (200 DPI)": 200,
    "Publication (300 DPI)": 300,
    "High Quality (600 DPI)": 600,
}


class ExportPanel(QWidget):
    """Controls for figure export."""

    export_requested = Signal(str, dict)  # path, options dict
    batch_requested = Signal(str, dict)   # directory, options dict

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(6)

        # -- Format group --
        fmt_grp = QGroupBox("Format")
        fmt_form = QFormLayout(fmt_grp)
        fmt_form.setSpacing(4)

        self.format_combo = QComboBox()
        self.format_combo.addItems(FORMATS)
        fmt_form.addRow("Format:", self.format_combo)

        self.quality_combo = QComboBox()
        self.quality_combo.addItems(QUALITY_PRESETS.keys())
        self.quality_combo.setCurrentIndex(2)  # Publication
        fmt_form.addRow("Quality:", self.quality_combo)

        self.transparent_check = QCheckBox("Transparent Background")
        fmt_form.addRow(self.transparent_check)

        self.tight_check = QCheckBox("Tight Bounding Box")
        self.tight_check.setChecked(True)
        fmt_form.addRow(self.tight_check)

        layout.addWidget(fmt_grp)

        # -- Export buttons --
        btn_grp = QGroupBox("Export")
        btn_layout = QVBoxLayout(btn_grp)
        btn_layout.setSpacing(6)

        self.export_btn = QPushButton("Export Figure...")
        self.export_btn.clicked.connect(self._on_export)
        btn_layout.addWidget(self.export_btn)

        self.batch_btn = QPushButton("Batch Export (All Formats)...")
        self.batch_btn.clicked.connect(self._on_batch)
        btn_layout.addWidget(self.batch_btn)

        self.status_label = QLabel("")
        btn_layout.addWidget(self.status_label)

        layout.addWidget(btn_grp)
        layout.addStretch()

    def get_export_options(self) -> dict:
        """Return current export options as a dict."""
        fmt = self.format_combo.currentText().lower()
        quality_txt = self.quality_combo.currentText()
        dpi = QUALITY_PRESETS.get(quality_txt, 300)
        return {
            "format": fmt,
            "dpi": dpi,
            "transparent": self.transparent_check.isChecked(),
            "bbox_inches": "tight" if self.tight_check.isChecked() else None,
            "pad_inches": 0.1 if self.tight_check.isChecked() else None,
            "facecolor": "none" if self.transparent_check.isChecked() else "white",
        }

    def _on_export(self):
        fmt = self.format_combo.currentText().lower()
        filt = f"{fmt.upper()} files (*.{fmt})"
        path, _ = QFileDialog.getSaveFileName(self, "Export Figure", "", filt)
        if path:
            self.export_requested.emit(path, self.get_export_options())

    def _on_batch(self):
        directory = QFileDialog.getExistingDirectory(self, "Select Export Directory")
        if directory:
            self.batch_requested.emit(directory, self.get_export_options())

    def set_status(self, text: str):
        self.status_label.setText(text)
