"""Vs Profile dialog -- configure and run profile extraction from .report."""
from pathlib import Path

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QGroupBox,
    QLabel, QLineEdit, QPushButton, QComboBox, QSpinBox,
    QDoubleSpinBox, QFileDialog, QDialogButtonBox,
    QProgressBar, QMessageBox,
)
from PySide6.QtCore import Qt, QSettings, QThread, Signal


class ProfileWorker(QThread):
    """Background thread for running Geopsy profile extraction."""
    finished = Signal(list)   # list of (depth, vel) tuples
    error = Signal(str)
    progress = Signal(str)

    def __init__(self, params: dict, parent=None):
        super().__init__(parent)
        self._params = params

    def run(self):
        try:
            from geo_figure.io.report_reader import extract_vs_profiles
            self.progress.emit("Running gpdcreport | gpprofile ...")
            profiles = extract_vs_profiles(**self._params)
            self.finished.emit(profiles)
        except Exception as e:
            self.error.emit(str(e))


class VsProfileDialog(QDialog):
    """Dialog to configure and run Vs profile extraction."""

    extraction_complete = Signal(list, dict)  # profiles, params

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Vs Profile - Load Report")
        self.setMinimumWidth(480)
        self._worker = None
        self._setup_ui()
        self._load_defaults()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # Report file
        file_group = QGroupBox("Report File")
        file_layout = QHBoxLayout(file_group)
        self.report_edit = QLineEdit()
        self.report_edit.setPlaceholderText("Path to .report file")
        file_layout.addWidget(self.report_edit)
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self._browse_report)
        file_layout.addWidget(browse_btn)
        layout.addWidget(file_group)

        # Extraction settings
        settings_group = QGroupBox("Extraction Settings")
        form = QFormLayout(settings_group)

        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["Best N", "Misfit Threshold"])
        form.addRow("Selection:", self.mode_combo)

        self.n_best_spin = QSpinBox()
        self.n_best_spin.setRange(10, 10000)
        self.n_best_spin.setValue(1000)
        form.addRow("Best N:", self.n_best_spin)

        self.misfit_spin = QDoubleSpinBox()
        self.misfit_spin.setRange(0.01, 100.0)
        self.misfit_spin.setValue(1.0)
        self.misfit_spin.setDecimals(2)
        form.addRow("Max Misfit:", self.misfit_spin)

        self.n_max_spin = QSpinBox()
        self.n_max_spin.setRange(10, 10000)
        self.n_max_spin.setValue(1000)
        form.addRow("Max Models:", self.n_max_spin)

        self.profile_type_combo = QComboBox()
        self.profile_type_combo.addItems(["Vs", "Vp", "Density"])
        form.addRow("Profile Type:", self.profile_type_combo)

        self.depth_max_spin = QDoubleSpinBox()
        self.depth_max_spin.setRange(10.0, 5000.0)
        self.depth_max_spin.setValue(200.0)
        self.depth_max_spin.setSuffix(" m")
        form.addRow("Max Depth:", self.depth_max_spin)

        self.unit_combo = QComboBox()
        self.unit_combo.addItems(["Metric (m, m/s)", "Imperial (ft, ft/s)"])
        form.addRow("Output Units:", self.unit_combo)

        layout.addWidget(settings_group)

        # Progress
        self.progress_label = QLabel("")
        layout.addWidget(self.progress_label)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)  # indeterminate
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        # Buttons
        btn_layout = QHBoxLayout()
        self.extract_btn = QPushButton("Extract")
        self.extract_btn.clicked.connect(self._on_extract)
        btn_layout.addWidget(self.extract_btn)
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.reject)
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)

    def _load_defaults(self):
        s = QSettings("GeoFigure", "GeoFigure")
        last = s.value("last_report_file", "")
        if last:
            self.report_edit.setText(last)

    def _browse_report(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Report File", "",
            "Report files (*.report);;All files (*.*)"
        )
        if path:
            self.report_edit.setText(path)

    def _on_extract(self):
        report_path = self.report_edit.text().strip()
        if not report_path or not Path(report_path).exists():
            QMessageBox.warning(self, "Error", "Please select a valid .report file.")
            return

        s = QSettings("GeoFigure", "GeoFigure")
        s.setValue("last_report_file", report_path)
        geopsy_bin = s.value("paths/geopsy_bin", "")
        bash_exe = s.value("paths/bash_exe", "")

        if not geopsy_bin or not bash_exe:
            QMessageBox.warning(
                self, "Settings Required",
                "Set Geopsy bin path and Bash path in Settings first."
            )
            return

        ptype_map = {"Vs": "vs", "Vp": "vp", "Density": "rho"}
        profile_type = ptype_map[self.profile_type_combo.currentText()]

        params = {
            "report_file": Path(report_path),
            "geopsy_bin": Path(geopsy_bin),
            "bash_exe": Path(bash_exe),
            "profile_type": profile_type,
            "selection_mode": "best" if self.mode_combo.currentIndex() == 0 else "misfit",
            "n_best": self.n_best_spin.value(),
            "misfit_max": self.misfit_spin.value(),
            "n_max_models": self.n_max_spin.value(),
            "depth_max": self.depth_max_spin.value(),
        }

        self.extract_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_label.setText("Extracting profiles...")

        self._extract_params = {
            "profile_type": profile_type,
            "depth_max": self.depth_max_spin.value(),
            "units": "ft" if self.unit_combo.currentIndex() == 1 else "m",
        }

        self._worker = ProfileWorker(params, self)
        self._worker.finished.connect(self._on_finished)
        self._worker.error.connect(self._on_error)
        self._worker.progress.connect(self._on_progress)
        self._worker.start()

    def _on_progress(self, msg):
        self.progress_label.setText(msg)

    def _on_finished(self, profiles):
        self.progress_bar.setVisible(False)
        self.extract_btn.setEnabled(True)
        n = len(profiles)
        if n == 0:
            self.progress_label.setText("No profiles extracted.")
            return
        self.progress_label.setText(f"Extracted {n} profiles.")
        self.extraction_complete.emit(profiles, self._extract_params)

    def _on_error(self, msg):
        self.progress_bar.setVisible(False)
        self.extract_btn.setEnabled(True)
        self.progress_label.setText(f"Error: {msg}")
        QMessageBox.critical(self, "Extraction Error", msg)
