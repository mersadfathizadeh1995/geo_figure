"""Vs Profile dialog -- configure and run profile extraction from .report."""
from pathlib import Path

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QGroupBox,
    QLabel, QLineEdit, QPushButton, QComboBox, QSpinBox,
    QDoubleSpinBox, QFileDialog, QCheckBox, QGridLayout,
    QProgressBar, QMessageBox,
)
from PySide6.QtCore import Qt, QSettings, QThread, Signal


class ProfileWorker(QThread):
    """Background thread for running Geopsy profile extraction."""
    finished = Signal(list, str)   # list of (depth, vel) tuples, raw_text
    error = Signal(str)
    progress = Signal(str)

    def __init__(self, params: dict, parent=None):
        super().__init__(parent)
        self._params = params

    def run(self):
        try:
            from geo_figure.io.report_reader import extract_vs_profiles
            self.progress.emit("Running gpdcreport | gpprofile ...")
            profiles, raw_text = extract_vs_profiles(**self._params)
            self.finished.emit(profiles, raw_text)
        except Exception as e:
            self.error.emit(str(e))


class VsProfileDialog(QDialog):
    """Dialog to configure and run Vs/Vp/Density profile extraction."""

    # Emits list of (profiles, params) -- one entry per extracted property
    extraction_complete = Signal(list)

    # Legacy signal for single-property backward compat
    extraction_complete_single = Signal(list, dict)

    def __init__(self, parent=None, subplot_info=None):
        super().__init__(parent)
        self.setWindowTitle("Profile Extraction")
        self.setMinimumWidth(500)
        self._worker = None
        self._subplot_info = subplot_info or [("main", "Main")]
        self._pending_extractions = []
        self._completed_results = []
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

        self.depth_max_spin = QDoubleSpinBox()
        self.depth_max_spin.setRange(10.0, 5000.0)
        self.depth_max_spin.setValue(200.0)
        self.depth_max_spin.setSuffix(" m")
        form.addRow("Max Depth:", self.depth_max_spin)

        self.unit_combo = QComboBox()
        self.unit_combo.addItems(["Metric (m, m/s)", "Imperial (ft, ft/s)"])
        form.addRow("Output Units:", self.unit_combo)

        layout.addWidget(settings_group)

        # Property selection with subplot assignment
        prop_group = QGroupBox("Properties to Extract")
        prop_grid = QGridLayout(prop_group)
        prop_grid.addWidget(QLabel("<b>Extract</b>"), 0, 0)
        prop_grid.addWidget(QLabel("<b>Property</b>"), 0, 1)
        self._subplot_header = QLabel("<b>Target Subplot</b>")
        prop_grid.addWidget(self._subplot_header, 0, 2)

        self._prop_checks = {}
        self._prop_combos = {}
        for row_i, (key, label) in enumerate(
            [("vs", "Vs"), ("vp", "Vp"), ("rho", "Density")], start=1
        ):
            cb = QCheckBox()
            cb.setChecked(key == "vs")
            cb.stateChanged.connect(self._on_prop_changed)
            self._prop_checks[key] = cb
            prop_grid.addWidget(cb, row_i, 0, Qt.AlignmentFlag.AlignCenter)
            prop_grid.addWidget(QLabel(label), row_i, 1)

            combo = QComboBox()
            for sp_key, sp_name in self._subplot_info:
                combo.addItem(sp_name, sp_key)
            self._prop_combos[key] = combo
            prop_grid.addWidget(combo, row_i, 2)

        prop_grid.setColumnStretch(2, 1)
        layout.addWidget(prop_group)

        self._on_prop_changed()

        # Progress
        self.progress_label = QLabel("")
        layout.addWidget(self.progress_label)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
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

    def _on_prop_changed(self):
        """Show subplot combos only when multiple properties are selected."""
        checked = self._selected_properties()
        show = len(checked) > 1
        self._subplot_header.setVisible(show)
        for combo in self._prop_combos.values():
            combo.setVisible(show)

    def _selected_properties(self) -> list:
        """Return list of checked property keys."""
        return [k for k, cb in self._prop_checks.items() if cb.isChecked()]

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
            QMessageBox.warning(self, "Error",
                                "Please select a valid .report file.")
            return

        selected = self._selected_properties()
        if not selected:
            QMessageBox.warning(self, "Error",
                                "Select at least one property to extract.")
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

        units = "ft" if self.unit_combo.currentIndex() == 1 else "m"

        # Build extraction queue: one entry per selected property
        self._pending_extractions = []
        self._completed_results = []
        for prop_key in selected:
            target = self._prop_combos[prop_key].currentData() \
                if len(selected) > 1 else None
            base_params = {
                "report_file": Path(report_path),
                "geopsy_bin": Path(geopsy_bin),
                "bash_exe": Path(bash_exe),
                "profile_type": prop_key,
                "selection_mode": ("best"
                                   if self.mode_combo.currentIndex() == 0
                                   else "misfit"),
                "n_best": self.n_best_spin.value(),
                "misfit_max": self.misfit_spin.value(),
                "n_max_models": self.n_max_spin.value(),
                "depth_max": self.depth_max_spin.value(),
            }
            meta = {
                "profile_type": prop_key,
                "depth_max": self.depth_max_spin.value(),
                "units": units,
                "target_subplot": target,
            }
            self._pending_extractions.append((base_params, meta))

        self.extract_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self._run_next_extraction()

    def _run_next_extraction(self):
        """Start the next extraction in the queue."""
        if not self._pending_extractions:
            self._all_done()
            return

        base_params, meta = self._pending_extractions[0]
        ptype_label = {"vs": "Vs", "vp": "Vp", "rho": "Density"}.get(
            meta["profile_type"], "?")
        idx = len(self._completed_results) + 1
        total = idx + len(self._pending_extractions)
        self.progress_label.setText(
            f"Extracting {ptype_label} ({idx}/{total})..."
        )

        self._current_meta = meta
        self._worker = ProfileWorker(base_params, self)
        self._worker.finished.connect(self._on_one_finished)
        self._worker.error.connect(self._on_error)
        self._worker.progress.connect(self._on_progress)
        self._worker.start()

    def _on_progress(self, msg):
        self.progress_label.setText(msg)

    def _on_one_finished(self, profiles, raw_text):
        """One property finished; store result and run next."""
        self._worker.finished.disconnect(self._on_one_finished)
        self._worker.error.disconnect(self._on_error)
        self._pending_extractions.pop(0)

        meta = self._current_meta
        meta["raw_text"] = raw_text
        self._completed_results.append((profiles, meta))

        self._run_next_extraction()

    def _all_done(self):
        """All properties extracted; emit results."""
        self.progress_bar.setVisible(False)
        self.extract_btn.setEnabled(True)

        total_profiles = sum(len(p) for p, _ in self._completed_results)
        if total_profiles == 0:
            self.progress_label.setText("No profiles extracted.")
            return

        n_props = len(self._completed_results)
        self.progress_label.setText(
            f"Done: {total_profiles} profiles across {n_props} "
            f"propert{'y' if n_props == 1 else 'ies'}."
        )

        if n_props == 1:
            # Single-property: emit legacy signal for backward compat
            profiles, params = self._completed_results[0]
            self.extraction_complete_single.emit(profiles, params)
        # Always emit the list signal
        self.extraction_complete.emit(self._completed_results)

    def _on_error(self, msg):
        self.progress_bar.setVisible(False)
        self.extract_btn.setEnabled(True)
        self.progress_label.setText(f"Error: {msg}")
        QMessageBox.critical(self, "Extraction Error", msg)
