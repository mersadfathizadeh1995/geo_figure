"""File I/O actions: open curves, load target, load Vs profiles."""
from pathlib import Path

from PySide6.QtWidgets import QFileDialog, QDialog, QVBoxLayout, QHBoxLayout, QCheckBox, QComboBox, QLabel, QSpinBox, QDialogButtonBox, QGroupBox

from geo_figure.core.models import CurveType, WaveType
from geo_figure.io.curve_reader import detect_and_read, read_theoretical_dc_txt


class _VsLoadOptionsDialog(QDialog):
    """Pre-load dialog for Vs profile files with data mapper and group option."""

    def __init__(self, filepaths, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Load Vs Profile Options")
        self.setMinimumWidth(380)
        layout = QVBoxLayout(self)

        n = len(filepaths)
        names = [Path(f).name for f in filepaths[:3]]
        lbl = ", ".join(names) + (f" (+{n - 3} more)" if n > 3 else "")
        layout.addWidget(QLabel(f"<b>Files:</b> {lbl}"))

        grp = QGroupBox("Options")
        g_layout = QVBoxLayout(grp)

        self.mapper_check = QCheckBox("Use Data Mapper (manually assign columns)")
        g_layout.addWidget(self.mapper_check)

        self.group_check = QCheckBox("Group multiple profiles under one layer")
        self.group_check.setChecked(True)
        self.group_check.setToolTip(
            "When a file contains multiple profiles, group them under a "
            "collapsible parent node in the data tree"
        )
        g_layout.addWidget(self.group_check)

        layout.addWidget(grp)

        btn_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        btn_box.accepted.connect(self.accept)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

    @property
    def use_mapper(self) -> bool:
        return self.mapper_check.isChecked()

    @property
    def group_multi(self) -> bool:
        return self.group_check.isChecked()


class _LoadOptionsDialog(QDialog):
    """Pre-load dialog with data mapper toggle, wave type, and mode."""

    def __init__(self, filepaths, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Load Options")
        self.setMinimumWidth(380)
        layout = QVBoxLayout(self)

        # File summary
        n = len(filepaths)
        names = [Path(f).name for f in filepaths[:3]]
        lbl = ", ".join(names) + (f" (+{n - 3} more)" if n > 3 else "")
        layout.addWidget(QLabel(f"<b>Files:</b> {lbl}"))

        # Options group
        grp = QGroupBox("Options")
        g_layout = QVBoxLayout(grp)

        # Wave type
        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Wave type:"))
        self.wave_combo = QComboBox()
        self.wave_combo.addItems(["Rayleigh", "Love"])
        row1.addWidget(self.wave_combo)
        row1.addStretch()
        g_layout.addLayout(row1)

        # Mode
        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Mode number:"))
        self.mode_spin = QSpinBox()
        self.mode_spin.setRange(0, 20)
        self.mode_spin.setValue(0)
        row2.addWidget(self.mode_spin)
        row2.addStretch()
        g_layout.addLayout(row2)

        # Data mapper toggle
        self.mapper_check = QCheckBox("Use Data Mapper (manually assign columns)")
        g_layout.addWidget(self.mapper_check)
        layout.addWidget(grp)

        # Buttons
        btn_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        btn_box.accepted.connect(self.accept)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

    @property
    def wave_type(self) -> WaveType:
        return (WaveType.LOVE if self.wave_combo.currentText() == "Love"
                else WaveType.RAYLEIGH)

    @property
    def mode(self) -> int:
        return self.mode_spin.value()

    @property
    def use_mapper(self) -> bool:
        return self.mapper_check.isChecked()


class FileActionsMixin:
    """File loading actions."""

    def _on_open_file(self):
        """Open one or more dispersion curve files (auto-detect format)."""
        files, _ = QFileDialog.getOpenFileNames(
            self, "Open Dispersion Curve Files",
            "",
            "All supported (*.txt *.csv *.target);;Text files (*.txt);;"
            "CSV files (*.csv);;Target files (*.target);;All files (*.*)"
        )
        if not files:
            return

        # Show load options dialog
        dlg = _LoadOptionsDialog(files, parent=self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        wave_type = dlg.wave_type
        mode_num = dlg.mode
        use_mapper = dlg.use_mapper

        # Resolve mapping if data mapper requested
        mapping = None
        if use_mapper:
            mapping = self._run_data_mapper(files[0])
            if mapping is None:
                return  # user cancelled the mapper

        canvas = self.sheet_tabs.get_current_canvas()
        for filepath in files:
            try:
                curves = detect_and_read(
                    filepath, mapping=mapping,
                    wave_type=wave_type, mode=mode_num,
                )
                for curve in curves:
                    if curve.curve_type != CurveType.THEORETICAL:
                        curve.color = self.curve_tree.get_next_color()
                    self._add_curve(curve, canvas)
                n = len(curves)
                fname = Path(filepath).name
                self.log_panel.log_success(
                    f"Loaded {n} curve(s) from {fname}"
                )
            except Exception as e:
                self.log_panel.log_error(f"Failed to load {filepath}: {e}")

        canvas.auto_range()

    def _run_data_mapper(self, filepath):
        """Open the DataMapper dialog for the given file. Returns ColumnMapping or None."""
        try:
            from geo_figure.io.data_mapper import (
                DataMapperDialog, dispersion_config, parse_file,
            )
            columns = parse_file(filepath)
            if not columns:
                self.log_panel.log_error(f"No data columns found in {filepath}")
                return None
            config = dispersion_config()
            dlg = DataMapperDialog(columns, config=config, parent=self)
            if dlg.exec() == QDialog.DialogCode.Accepted:
                return dlg.get_mapping()
            return None
        except Exception as e:
            self.log_panel.log_error(f"Data mapper error: {e}")
            return None

        canvas.auto_range()

    def _on_open_theoretical(self):
        """Open a theoretical DC file (gpdc output format)."""
        filepath, _ = QFileDialog.getOpenFileName(
            self, "Open Theoretical DC File",
            "",
            "Text files (*.txt);;All files (*.*)"
        )
        if not filepath:
            return

        canvas = self.sheet_tabs.get_current_canvas()
        try:
            curves = read_theoretical_dc_txt(filepath)
            for curve in curves:
                self._add_curve(curve, canvas)
            self.log_panel.log_success(
                f"Loaded {len(curves)} theoretical models from {Path(filepath).name}"
            )
            canvas.auto_range()
        except Exception as e:
            self.log_panel.log_error(f"Failed to load theoretical DC: {e}")

    def _on_load_target(self):
        """Load a Dinver .target file."""
        filepath, _ = QFileDialog.getOpenFileName(
            self, "Load Target File",
            "",
            "Target files (*.target);;All files (*.*)"
        )
        if not filepath:
            return
        canvas = self.sheet_tabs.get_current_canvas()
        try:
            from geo_figure.io.target_reader import read_target_file
            curves, summary = read_target_file(filepath)
            for curve in curves:
                curve.color = self.curve_tree.get_next_color()
                self._add_curve(curve, canvas)
            n = summary['total_curves']
            self.log_panel.log_success(
                f"Loaded {n} curve(s) from target: "
                f"{summary['rayleigh_count']} Rayleigh, {summary['love_count']} Love"
            )
            canvas.auto_range()
        except Exception as e:
            self.log_panel.log_error(f"Failed to load target: {e}")

    def _on_load_vs_profile(self):
        """Load one or more Vs/Vp/density soil profile files."""
        files, _ = QFileDialog.getOpenFileNames(
            self, "Load Vs Profile Files",
            "",
            "All supported (*.txt *.csv);;Text files (*.txt);;CSV files (*.csv);;All files (*.*)"
        )
        if not files:
            return

        # Show Vs load options dialog
        dlg = _VsLoadOptionsDialog(files, parent=self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        use_mapper = dlg.use_mapper
        group_multi = dlg.group_multi

        # Resolve mapping if data mapper requested
        mapping = None
        if use_mapper:
            mapping = self._run_vs_data_mapper(files[0])
            if mapping is None:
                return

        from geo_figure.io.vs_reader import detect_and_read_vs, read_vs_mapped
        from geo_figure.core.models import CURVE_COLORS, SoilProfileGroup

        canvas = self.sheet_tabs.get_current_canvas()
        target_key = canvas.active_subplot or "main"

        # Auto-convert DC subplot to vs_profile if no DC data on it
        subplot_type = canvas._subplot_types.get(target_key, "dc")
        if subplot_type != "vs_profile":
            has_dc = any(
                c.subplot_key == target_key for c in self._curves.values()
            ) or any(
                e.subplot_key == target_key for e in self._ensembles.values()
            )
            if not has_dc:
                canvas.set_subplot_type(target_key, "vs_profile")
                self._rebuild_tree()
                target_key = canvas.active_subplot or target_key

        color_idx = len(canvas._soil_profiles)
        for filepath in files:
            try:
                if mapping:
                    profiles = read_vs_mapped(filepath, mapping)
                else:
                    profiles = detect_and_read_vs(filepath)

                for prof in profiles:
                    prof.color = CURVE_COLORS[color_idx % len(CURVE_COLORS)]
                    color_idx += 1
                    prof.subplot_key = target_key

                fname = Path(filepath).name
                if len(profiles) > 1 and group_multi:
                    # Group multiple profiles under a parent node
                    group = SoilProfileGroup(
                        name=Path(filepath).stem,
                        profiles=profiles,
                        subplot_key=profiles[0].subplot_key,
                    )
                    sd = self._sheet_data.get(self._current_sheet_idx, {})
                    sp_dict = sd.setdefault("soil_profiles", {})
                    for prof in profiles:
                        sp_dict[prof.uid] = prof
                    self.curve_tree.add_soil_profile_group(group)
                    for prof in profiles:
                        canvas.add_soil_profile(prof)
                else:
                    for prof in profiles:
                        self._add_soil_profile(prof, canvas)

                self.log_panel.log_success(
                    f"Loaded {len(profiles)} profile(s) from {fname}"
                )
            except Exception as e:
                self.log_panel.log_error(f"Failed to load Vs profile {filepath}: {e}")
        canvas.auto_range()

    def _run_vs_data_mapper(self, filepath):
        """Open the DataMapper dialog for Vs profile files."""
        try:
            from geo_figure.io.data_mapper import DataMapperDialog, parse_file
            from geo_figure.io.vs_reader import vs_profile_config
            columns = parse_file(filepath)
            if not columns:
                self.log_panel.log_error(f"No data columns found in {filepath}")
                return None
            config = vs_profile_config()
            dlg = DataMapperDialog(columns, config=config, parent=self)
            if dlg.exec() == QDialog.DialogCode.Accepted:
                return dlg.get_mapping()
            return None
        except Exception as e:
            self.log_panel.log_error(f"Data mapper error: {e}")
            return None

    def _on_export_csv(self):
        """Export current sheet data (curves + ensembles) as CSV files."""
        import numpy as np

        project_csv = getattr(self, '_project_dir', None)
        default_dir = str(project_csv / "csv") if project_csv else ""

        # Curves
        curves = self._curves
        ensembles = self._ensembles

        if not curves and not ensembles:
            self.log_panel.log_info("Nothing to export.")
            return

        save_dir = QFileDialog.getExistingDirectory(
            self, "Select CSV Export Directory", default_dir
        )
        if not save_dir:
            return

        count = 0
        save_path = Path(save_dir)

        # Export experimental curves
        for uid, curve in curves.items():
            if not curve.has_data:
                continue
            name = curve.display_name.replace(" ", "_").replace("/", "_")
            mask = curve.point_mask if curve.point_mask is not None else np.ones(len(curve.frequency), dtype=bool)
            freq = curve.frequency[mask]
            vel = curve.velocity[mask]
            lines = ["Frequency_Hz,Phase_Velocity_mps"]
            if curve.stddev is not None and len(curve.stddev) == len(curve.frequency):
                lines[0] += ",StdDev"
                std = curve.stddev[mask]
                for f, v, s in zip(freq, vel, std):
                    lines.append(f"{f:.6f},{v:.4f},{s:.6f}")
            else:
                for f, v in zip(freq, vel):
                    lines.append(f"{f:.6f},{v:.4f}")
            fpath = save_path / f"{name}.csv"
            fpath.write_text("\n".join(lines), encoding="utf-8")
            count += 1

        # Export ensemble statistics
        for uid, ens in ensembles.items():
            if not ens.has_data:
                continue
            name = ens.display_name.replace(" ", "_").replace("/", "_")
            # Median + percentiles
            header = "Frequency_Hz,Median_mps"
            cols = [ens.freq, ens.median]
            if ens.p_low is not None:
                header += ",P16_mps"
                cols.append(ens.p_low)
            if ens.p_high is not None:
                header += ",P84_mps"
                cols.append(ens.p_high)
            if ens.envelope_min is not None:
                header += ",Min_mps"
                cols.append(ens.envelope_min)
            if ens.envelope_max is not None:
                header += ",Max_mps"
                cols.append(ens.envelope_max)
            if ens.sigma_ln is not None:
                header += ",Sigma_ln"
                cols.append(ens.sigma_ln)
            lines = [header]
            for i in range(len(ens.freq)):
                row = ",".join(f"{c[i]:.6f}" for c in cols)
                lines.append(row)
            fpath = save_path / f"{name}_stats.csv"
            fpath.write_text("\n".join(lines), encoding="utf-8")
            count += 1

        self.log_panel.log_success(f"Exported {count} CSV file(s) to {save_dir}")
