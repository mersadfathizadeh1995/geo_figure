"""File I/O actions: open curves, load target, load Vs profiles."""
from pathlib import Path

from PySide6.QtWidgets import (
    QFileDialog, QDialog, QVBoxLayout, QHBoxLayout, QCheckBox, QComboBox,
    QLabel, QSpinBox, QDialogButtonBox, QGroupBox,
    QMessageBox, QGridLayout,
)
from PySide6.QtCore import Qt

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

        # Unit selection
        unit_row = QHBoxLayout()
        unit_row.addWidget(QLabel("Units:"))
        self.unit_combo = QComboBox()
        self.unit_combo.addItems(["m  (metric)", "ft  (imperial)"])
        unit_row.addWidget(self.unit_combo)
        unit_row.addStretch()
        g_layout.addLayout(unit_row)

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

    @property
    def units(self) -> str:
        """Return 'm' or 'ft'."""
        return "ft" if self.unit_combo.currentIndex() == 1 else "m"


class _VsPropertyDialog(QDialog):
    """Choose which properties to draw and where to place them.

    Shown only when a loaded file contains Vp and/or density in addition to Vs.
    """

    def __init__(self, has_vp: bool, has_density: bool,
                 subplot_info=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Property Selection")
        self.setMinimumWidth(440)
        self.setModal(True)
        main_layout = QVBoxLayout(self)

        available = ["Vs"]
        if has_vp:
            available.append("Vp")
        if has_density:
            available.append("Density")

        main_layout.addWidget(QLabel(
            f"<b>Available properties:</b> {', '.join(available)}"
        ))

        # -- Mode combo instead of radio buttons --
        mode_row = QHBoxLayout()
        mode_row.addWidget(QLabel("Display mode:"))
        self._mode_combo = QComboBox()
        self._mode_combo.addItem("Single property", "single")
        self._mode_combo.addItem("Side by side (sections)", "multi")
        self._mode_combo.addItem("Assign to subplots", "split")
        self._mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        mode_row.addWidget(self._mode_combo, 1)
        main_layout.addLayout(mode_row)

        # -- Property table: checkbox + subplot combo per property --
        self._prop_group = QGroupBox("Properties")
        prop_grid = QGridLayout(self._prop_group)
        prop_grid.addWidget(QLabel("<b>Draw</b>"), 0, 0)
        prop_grid.addWidget(QLabel("<b>Property</b>"), 0, 1)
        self._subplot_header = QLabel("<b>Target subplot</b>")
        prop_grid.addWidget(self._subplot_header, 0, 2)

        # Build subplot list for dropdowns
        self._subplot_info = subplot_info or [("main", "Main")]
        sp_names = [name for _, name in self._subplot_info]

        self._prop_checks = {}
        self._prop_combos = {}
        for row_i, prop in enumerate(available, start=1):
            cb = QCheckBox()
            cb.setChecked(True)
            self._prop_checks[prop.lower()] = cb
            prop_grid.addWidget(cb, row_i, 0, Qt.AlignmentFlag.AlignCenter)

            prop_grid.addWidget(QLabel(prop), row_i, 1)

            combo = QComboBox()
            for sp_key, sp_name in self._subplot_info:
                combo.addItem(sp_name, sp_key)
            self._prop_combos[prop.lower()] = combo
            prop_grid.addWidget(combo, row_i, 2)

        prop_grid.setColumnStretch(2, 1)
        main_layout.addWidget(self._prop_group)

        # -- Button box --
        btn_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        btn_box.accepted.connect(self.accept)
        btn_box.rejected.connect(self.reject)
        main_layout.addWidget(btn_box)

        # Set initial UI state
        self._on_mode_changed()

    def _on_mode_changed(self):
        """Show/hide subplot combos based on mode."""
        mode = self.mode
        show_combos = (mode == "split")
        self._subplot_header.setVisible(show_combos)
        for combo in self._prop_combos.values():
            combo.setVisible(show_combos)
        if mode == "single":
            # Keep only the first checked, uncheck the rest
            first_found = False
            for cb in self._prop_checks.values():
                if not first_found:
                    cb.setChecked(True)
                    first_found = True
                else:
                    cb.setChecked(False)
        else:
            for cb in self._prop_checks.values():
                cb.setChecked(True)

    @property
    def mode(self) -> str:
        return self._mode_combo.currentData()

    @property
    def selected_properties(self) -> list:
        return [k for k, cb in self._prop_checks.items() if cb.isChecked()]

    @property
    def property_targets(self) -> dict:
        """Return {prop_name: subplot_key} for split mode."""
        result = {}
        for prop, combo in self._prop_combos.items():
            if self._prop_checks.get(prop, None) and self._prop_checks[prop].isChecked():
                result[prop] = combo.currentData()
        return result


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

        # Unit selection
        row_u = QHBoxLayout()
        row_u.addWidget(QLabel("Units:"))
        self.unit_combo = QComboBox()
        self.unit_combo.addItems(["m  (metric)", "ft  (imperial)"])
        row_u.addWidget(self.unit_combo)
        row_u.addStretch()
        g_layout.addLayout(row_u)

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

    @property
    def units(self) -> str:
        """Return 'm' or 'ft'."""
        return "ft" if self.unit_combo.currentIndex() == 1 else "m"


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
        units = dlg.units

        # Resolve mapping if data mapper requested
        mapping = None
        if use_mapper:
            mapping = self._run_data_mapper(files[0])
            if mapping is None:
                return  # user cancelled the mapper

        from geo_figure.io.converters import convert_dc_curve_ft_to_m

        canvas = self.sheet_tabs.get_current_canvas()
        for filepath in files:
            try:
                curves = detect_and_read(
                    filepath, mapping=mapping,
                    wave_type=wave_type, mode=mode_num,
                )
                for curve in curves:
                    if units == "ft":
                        convert_dc_curve_ft_to_m(curve)
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
        units = dlg.units

        # Resolve mapping if data mapper requested
        mapping = None
        if use_mapper:
            mapping = self._run_vs_data_mapper(files[0])
            if mapping is None:
                return

        from geo_figure.io.vs_reader import detect_and_read_vs, read_vs_mapped
        from geo_figure.io.converters import convert_soil_profile_ft_to_m
        from geo_figure.core.models import CURVE_COLORS, SoilProfileGroup
        import copy

        # Read all profiles first to detect available properties
        all_file_profiles = []
        for filepath in files:
            try:
                if mapping:
                    profiles = read_vs_mapped(filepath, mapping)
                else:
                    profiles = detect_and_read_vs(filepath)
                # Convert from imperial to metric if needed
                if units == "ft":
                    for prof in profiles:
                        convert_soil_profile_ft_to_m(prof)
                all_file_profiles.append((filepath, profiles))
            except Exception as e:
                self.log_panel.log_error(
                    f"Failed to load Vs profile {filepath}: {e}"
                )

        if not all_file_profiles:
            return

        # Detect multi-property availability
        has_vp = any(
            p.vp is not None
            for _, profs in all_file_profiles for p in profs
        )
        has_density = any(
            p.density is not None
            for _, profs in all_file_profiles for p in profs
        )

        prop_mode = "single"
        selected_props = ["vs"]
        user_targets = {}

        if has_vp or has_density:
            canvas_temp = self.sheet_tabs.get_current_canvas()
            subplot_info = canvas_temp.get_subplot_info()
            prop_dlg = _VsPropertyDialog(
                has_vp, has_density,
                subplot_info=subplot_info, parent=self,
            )
            if prop_dlg.exec() != QDialog.DialogCode.Accepted:
                return
            prop_mode = prop_dlg.mode
            selected_props = prop_dlg.selected_properties
            if not selected_props:
                return
            user_targets = prop_dlg.property_targets  # split mode assignments

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

        # Handle split mode: use user-chosen subplot targets
        prop_labels = {"vs": "Vs", "vp": "Vp", "density": "Density"}
        prop_targets = {}
        if prop_mode == "split" and len(selected_props) > 1:
            prop_targets = user_targets
            # Ensure target subplots are vs_profile type and labelled
            for prop, key in prop_targets.items():
                canvas.set_subplot_type(key, "vs_profile")
                canvas.rename_subplot(key, prop_labels.get(prop, prop))
        else:
            for prop in selected_props:
                prop_targets[prop] = target_key

        color_idx = len(canvas._soil_profiles)
        for filepath, profiles in all_file_profiles:
            fname = Path(filepath).name

            if prop_mode == "single":
                prop = selected_props[0]
                for prof in profiles:
                    prof.render_property = prop
                    prof.color = CURVE_COLORS[color_idx % len(CURVE_COLORS)]
                    color_idx += 1
                    prof.subplot_key = target_key
                self._add_profiles_to_canvas(
                    profiles, canvas, group_multi, filepath
                )

            elif prop_mode == "multi":
                # Register multi-property sections on the canvas
                if target_key not in canvas._soil_profile_sections:
                    canvas.set_soil_profile_sections(target_key, selected_props)
                all_clones = []
                for prop in selected_props:
                    for prof in profiles:
                        clone = copy.copy(prof)
                        clone.uid = f"{prof.uid}_{prop}"
                        clone.render_property = prop
                        clone.color = CURVE_COLORS[color_idx % len(CURVE_COLORS)]
                        color_idx += 1
                        clone.subplot_key = target_key
                        clone.custom_name = (
                            f"{prof.custom_name or prof.name} "
                            f"({prop_labels.get(prop, prop)})"
                        )
                        all_clones.append(clone)
                self._add_profiles_to_canvas(
                    all_clones, canvas, group_multi, filepath
                )

            elif prop_mode == "split":
                for prop in selected_props:
                    prop_key = prop_targets[prop]
                    clones = []
                    for prof in profiles:
                        clone = copy.copy(prof)
                        clone.uid = f"{prof.uid}_{prop}"
                        clone.render_property = prop
                        clone.color = CURVE_COLORS[color_idx % len(CURVE_COLORS)]
                        color_idx += 1
                        clone.subplot_key = prop_key
                        clones.append(clone)
                    self._add_profiles_to_canvas(
                        clones, canvas, group_multi, filepath
                    )

            self.log_panel.log_success(
                f"Loaded {len(profiles)} profile(s) from {fname}"
            )

        canvas.auto_range()

    def _add_profiles_to_canvas(self, profiles, canvas, group_multi, filepath):
        """Add profiles to canvas, optionally grouping them."""
        from geo_figure.core.models import SoilProfileGroup

        if len(profiles) > 1 and group_multi:
            group = SoilProfileGroup(
                name=Path(filepath).stem,
                profiles=profiles,
                subplot_key=profiles[0].subplot_key,
                filepath=filepath,
            )
            sd = self._sheet_data.get(self._current_sheet_idx, {})
            sp_dict = sd.setdefault("soil_profiles", {})
            for prof in profiles:
                sp_dict[prof.uid] = prof
            # Store group reference
            grp_dict = sd.setdefault("soil_profile_groups", {})
            grp_dict[group.uid] = group
            self.curve_tree.add_soil_profile_group(group)
            for prof in profiles:
                canvas.add_soil_profile(prof)
        else:
            for prof in profiles:
                self._add_soil_profile(prof, canvas)

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
