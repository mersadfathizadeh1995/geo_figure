"""DC Compare dialog — configure and run theoretical curve extraction."""
from pathlib import Path

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QGroupBox,
    QLabel, QLineEdit, QPushButton, QComboBox, QSpinBox,
    QDoubleSpinBox, QFileDialog, QDialogButtonBox, QCheckBox,
    QProgressBar, QMessageBox,
)
from PySide6.QtCore import Qt, QSettings, QThread, Signal


class ExtractionWorker(QThread):
    """Background thread for running Geopsy extraction."""
    finished = Signal(dict)   # parsed results
    error = Signal(str)
    progress = Signal(str)

    def __init__(self, params: dict, parent=None):
        super().__init__(parent)
        self._params = params

    def run(self):
        try:
            from geo_figure.io.report_reader import extract_theoretical_curves
            self.progress.emit("Running gpdcreport | gpdc ...")
            results = extract_theoretical_curves(**self._params)
            self.finished.emit(results)
        except Exception as e:
            self.error.emit(str(e))


class DCCompareDialog(QDialog):
    """Dialog to configure and run DC Compare extraction."""

    extraction_complete = Signal(dict)  # parsed results

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("DC Compare - Load Report")
        self.setMinimumWidth(520)
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

        self.curve_type_combo = QComboBox()
        self.curve_type_combo.addItems(["Rayleigh", "Love", "Both"])
        form.addRow("Curve Type:", self.curve_type_combo)

        self.selection_combo = QComboBox()
        self.selection_combo.addItems(["Best N models", "Misfit threshold"])
        self.selection_combo.currentIndexChanged.connect(self._on_selection_changed)
        form.addRow("Selection:", self.selection_combo)

        self.n_best_spin = QSpinBox()
        self.n_best_spin.setRange(10, 10000)
        self.n_best_spin.setValue(1000)
        form.addRow("N Best:", self.n_best_spin)

        self.misfit_spin = QDoubleSpinBox()
        self.misfit_spin.setRange(0.01, 100.0)
        self.misfit_spin.setValue(1.0)
        self.misfit_spin.setDecimals(2)
        self.misfit_spin.setVisible(False)
        self.misfit_label = QLabel("Max Misfit:")
        self.misfit_label.setVisible(False)
        form.addRow(self.misfit_label, self.misfit_spin)

        self.n_max_spin = QSpinBox()
        self.n_max_spin.setRange(10, 50000)
        self.n_max_spin.setValue(1000)
        self.n_max_spin.setVisible(False)
        self.n_max_label = QLabel("Max Models:")
        self.n_max_label.setVisible(False)
        form.addRow(self.n_max_label, self.n_max_spin)

        # Frequency range
        freq_row = QHBoxLayout()
        self.freq_min_spin = QDoubleSpinBox()
        self.freq_min_spin.setRange(0.01, 100.0)
        self.freq_min_spin.setValue(0.2)
        self.freq_min_spin.setDecimals(2)
        freq_row.addWidget(QLabel("Min:"))
        freq_row.addWidget(self.freq_min_spin)
        self.freq_max_spin = QDoubleSpinBox()
        self.freq_max_spin.setRange(0.1, 1000.0)
        self.freq_max_spin.setValue(50.0)
        self.freq_max_spin.setDecimals(1)
        freq_row.addWidget(QLabel("Max:"))
        freq_row.addWidget(self.freq_max_spin)
        form.addRow("Freq Range (Hz):", freq_row)

        self.n_points_spin = QSpinBox()
        self.n_points_spin.setRange(20, 500)
        self.n_points_spin.setValue(100)
        form.addRow("N Freq Points:", self.n_points_spin)

        # Mode counts
        mode_row = QHBoxLayout()
        self.ray_modes_spin = QSpinBox()
        self.ray_modes_spin.setRange(0, 10)
        self.ray_modes_spin.setValue(1)
        mode_row.addWidget(QLabel("Rayleigh:"))
        mode_row.addWidget(self.ray_modes_spin)
        self.love_modes_spin = QSpinBox()
        self.love_modes_spin.setRange(0, 10)
        self.love_modes_spin.setValue(0)
        mode_row.addWidget(QLabel("Love:"))
        mode_row.addWidget(self.love_modes_spin)
        form.addRow("Modes:", mode_row)

        self.include_individual_cb = QCheckBox("Show individual model curves")
        self.include_individual_cb.setChecked(False)
        form.addRow(self.include_individual_cb)

        layout.addWidget(settings_group)

        # Progress
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        self.status_label = QLabel("")
        layout.addWidget(self.status_label)

        # Buttons
        btn_box = QDialogButtonBox()
        self.run_btn = btn_box.addButton("Extract", QDialogButtonBox.AcceptRole)
        self.run_btn.clicked.connect(self._on_extract)
        btn_box.addButton("Cancel", QDialogButtonBox.RejectRole)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

    def _load_defaults(self):
        """Pre-fill from QSettings (last used paths)."""
        s = QSettings("GeoFigure", "GeoFigure")
        last_report = s.value("last_report_file", "")
        if last_report:
            self.report_edit.setText(last_report)

    def _browse_report(self):
        filepath, _ = QFileDialog.getOpenFileName(
            self, "Select Report File", "",
            "Report files (*.report);;All files (*.*)"
        )
        if filepath:
            self.report_edit.setText(filepath)

    def _on_selection_changed(self, index):
        is_misfit = index == 1
        self.n_best_spin.setVisible(not is_misfit)
        self.misfit_spin.setVisible(is_misfit)
        self.misfit_label.setVisible(is_misfit)
        self.n_max_spin.setVisible(is_misfit)
        self.n_max_label.setVisible(is_misfit)

    def _on_extract(self):
        report_path = self.report_edit.text().strip()
        if not report_path or not Path(report_path).exists():
            QMessageBox.warning(self, "Error", "Please select a valid .report file.")
            return

        # Get Geopsy paths from settings
        from geo_figure.gui.dialogs.settings_dialog import get_geopsy_bin, get_bash_exe
        geopsy_bin = get_geopsy_bin()
        bash_exe = get_bash_exe()

        if not geopsy_bin or not Path(geopsy_bin).exists():
            QMessageBox.warning(
                self, "Error",
                "Geopsy bin directory not set. Go to File -> Settings first."
            )
            return
        if not bash_exe or not Path(bash_exe).exists():
            QMessageBox.warning(
                self, "Error",
                "Bash executable not set. Go to File -> Settings first."
            )
            return

        # Save last used report
        QSettings("GeoFigure", "GeoFigure").setValue("last_report_file", report_path)

        params = {
            "report_file": Path(report_path),
            "geopsy_bin": Path(geopsy_bin),
            "bash_exe": Path(bash_exe),
            "curve_type": self.curve_type_combo.currentText(),
            "selection_mode": "best" if self.selection_combo.currentIndex() == 0 else "misfit",
            "n_best": self.n_best_spin.value(),
            "misfit_max": self.misfit_spin.value(),
            "n_max_models": self.n_max_spin.value(),
            "ray_modes": self.ray_modes_spin.value(),
            "love_modes": self.love_modes_spin.value(),
            "freq_min": self.freq_min_spin.value(),
            "freq_max": self.freq_max_spin.value(),
            "n_freq_points": self.n_points_spin.value(),
        }

        self.progress_bar.setVisible(True)
        self.run_btn.setEnabled(False)
        self.status_label.setText("Extracting theoretical curves...")

        self._worker = ExtractionWorker(params, self)
        self._worker.finished.connect(self._on_extraction_done)
        self._worker.error.connect(self._on_extraction_error)
        self._worker.progress.connect(lambda msg: self.status_label.setText(msg))
        self._worker.start()

    def _on_extraction_done(self, results: dict):
        self.progress_bar.setVisible(False)
        self.run_btn.setEnabled(True)
        n_total = sum(r.get("n_profiles", 0) for r in results.values())
        self.status_label.setText(
            f"Extraction complete: {n_total} profiles extracted."
        )
        # Store include_individual preference with results
        results["__include_individual"] = self.include_individual_cb.isChecked()
        self.extraction_complete.emit(results)
        self.accept()

    def _on_extraction_error(self, msg: str):
        self.progress_bar.setVisible(False)
        self.run_btn.setEnabled(True)
        self.status_label.setText(f"Error: {msg}")
        QMessageBox.critical(self, "Extraction Failed", msg)

    def get_include_individual(self) -> bool:
        return self.include_individual_cb.isChecked()
