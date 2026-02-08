"""Per-sheet data management: curves, ensembles, sheet switching, duplicate, units."""
import warnings


class SheetManagerMixin:
    """Per-sheet data store and sheet operations."""

    def _ensure_sheet_data(self, idx: int):
        """Create sheet data store if it doesn't exist."""
        if idx not in self._sheet_data:
            self._sheet_data[idx] = {
                'curves': {}, 'ensembles': {}, 'vs_profiles': {},
                'selected_uid': None, 'velocity_unit': 'metric'
            }
        elif 'vs_profiles' not in self._sheet_data[idx]:
            self._sheet_data[idx]['vs_profiles'] = {}

    @property
    def _curves(self) -> dict:
        """Curves for the current sheet."""
        self._ensure_sheet_data(self._current_sheet_idx)
        return self._sheet_data[self._current_sheet_idx]['curves']

    @property
    def _ensembles(self) -> dict:
        """Ensembles for the current sheet."""
        self._ensure_sheet_data(self._current_sheet_idx)
        return self._sheet_data[self._current_sheet_idx]['ensembles']

    @property
    def _vs_profiles(self) -> dict:
        """Vs profiles for the current sheet."""
        self._ensure_sheet_data(self._current_sheet_idx)
        return self._sheet_data[self._current_sheet_idx]['vs_profiles']

    @property
    def _selected_uid(self):
        self._ensure_sheet_data(self._current_sheet_idx)
        return self._sheet_data[self._current_sheet_idx]['selected_uid']

    @_selected_uid.setter
    def _selected_uid(self, val):
        self._ensure_sheet_data(self._current_sheet_idx)
        self._sheet_data[self._current_sheet_idx]['selected_uid'] = val

    def _rebuild_tree(self):
        """Rebuild the Data tree from current sheet's curves + ensembles + profiles."""
        canvas = self.sheet_tabs.get_current_canvas()
        subplot_info = canvas.get_subplot_info()
        self.curve_tree.set_subplot_structure(subplot_info)
        for uid, curve in self._curves.items():
            self.curve_tree.add_curve(curve)
        for uid, ens in self._ensembles.items():
            self.curve_tree.add_ensemble(ens)
        for uid, prof in self._vs_profiles.items():
            self.curve_tree.add_vs_profile(prof)
        self.properties.set_available_subplots(subplot_info)

    def _on_sheet_changed(self, index: int):
        """Handle sheet tab switch -- swap tree and properties to this sheet."""
        self._current_sheet_idx = index
        self._ensure_sheet_data(index)
        canvas = self.sheet_tabs.get_current_canvas()

        # Apply this sheet's velocity unit to the canvas
        unit = self._sheet_data[index].get('velocity_unit', 'metric')
        if canvas.velocity_unit != unit:
            canvas.set_velocity_unit(unit)

        # Update dock title
        sheet_name = self.sheet_tabs.tabText(index) if index >= 0 else "Data"
        self.curve_dock.setWindowTitle(f"Data - {sheet_name}")

        # Rebuild the tree for this sheet's curves and ensembles
        self._rebuild_tree()

        # Restore selection
        if self._selected_uid and self._selected_uid in self._curves:
            self.properties.show_curve(
                self._selected_uid, self._curves[self._selected_uid]
            )
            self.curve_tree.select_curve(self._selected_uid)
        else:
            self.properties.clear()

        # Sync legend config from canvas to sheet panel
        self.sheet_panel.set_legend_config(canvas.get_legend_config())
        # Sync column ratios
        cols = canvas._grid_cols if canvas.layout_mode == "grid" else 0
        self.sheet_panel.set_grid_col_ratios(cols, list(canvas._grid_col_ratios))
        # Sync Vs profile layout visibility
        has_vs = any(
            t == "vs_profile" for t in canvas._subplot_types.values()
        ) or canvas.layout_mode == "vs_profile"
        self.sheet_panel.set_vs_visible(has_vs)
        if has_vs:
            self.sheet_panel.set_vs_ratios(*canvas._vs_internal_ratios)
        # Sync sheet info
        sheet_name = self.sheet_tabs.tabText(index) if index >= 0 else ""
        self.sheet_panel.set_sheet_info(
            sheet_name, canvas.get_subplot_keys()
        )

        # Connect canvas signals for this canvas
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            try:
                canvas.curve_clicked.disconnect(self._on_curve_selected)
            except (RuntimeError, TypeError):
                pass
            try:
                canvas.layout_changed.disconnect(self._on_layout_structure_changed)
            except (RuntimeError, TypeError):
                pass
        canvas.curve_clicked.connect(self._on_curve_selected)
        canvas.layout_changed.connect(self._on_layout_structure_changed)

    def _on_duplicate_sheet(self, source_index: int):
        """Duplicate a sheet with all its curves and ensembles."""
        import copy
        import uuid as _uuid
        self._ensure_sheet_data(source_index)
        src = self._sheet_data[source_index]

        # Capture source canvas layout before switching tabs
        src_canvas = self.sheet_tabs.widget(source_index)
        src_layout_cfg = src_canvas.get_layout_config()

        # Create new sheet
        src_name = self.sheet_tabs.tabText(source_index)
        new_name = f"{src_name} (Copy)"
        self.sheet_tabs.add_sheet(new_name)
        new_idx = self.sheet_tabs.count() - 1
        self._ensure_sheet_data(new_idx)

        # Apply source layout to new canvas
        new_canvas = self.sheet_tabs.get_current_canvas()
        new_canvas._subplot_names = dict(src_layout_cfg["subplot_names"])
        new_canvas._subplot_types = dict(src_layout_cfg.get("subplot_types", {}))
        new_canvas._link_y = src_layout_cfg["link_y"]
        new_canvas._link_x = src_layout_cfg["link_x"]
        mode = src_layout_cfg["layout_mode"]
        if mode == "grid":
            new_canvas.set_grid(src_layout_cfg["grid_rows"], src_layout_cfg["grid_cols"])
        elif mode != new_canvas.layout_mode:
            new_canvas.set_layout_mode(mode)

        new_canvas.set_velocity_unit(src.get('velocity_unit', 'metric'))
        self._sheet_data[new_idx]['velocity_unit'] = src.get('velocity_unit', 'metric')

        for uid, curve in src['curves'].items():
            c = copy.copy(curve)
            c.uid = str(_uuid.uuid4())[:8]
            if curve.frequency is not None:
                c.frequency = curve.frequency.copy()
            if curve.velocity is not None:
                c.velocity = curve.velocity.copy()
            if curve.slowness is not None:
                c.slowness = curve.slowness.copy()
            if curve.stddev is not None:
                c.stddev = curve.stddev.copy()
            if curve.point_mask is not None:
                c.point_mask = curve.point_mask.copy()
            self._curves[c.uid] = c
            self.curve_tree.add_curve(c)
            new_canvas.add_curve(c)

        for uid, ens in src['ensembles'].items():
            e = copy.copy(ens)
            e.uid = str(_uuid.uuid4())[:8]
            if ens.freq is not None:
                e.freq = ens.freq.copy()
            if ens.median is not None:
                e.median = ens.median.copy()
            if ens.p_low is not None:
                e.p_low = ens.p_low.copy()
            if ens.p_high is not None:
                e.p_high = ens.p_high.copy()
            if ens.envelope_min is not None:
                e.envelope_min = ens.envelope_min.copy()
            if ens.envelope_max is not None:
                e.envelope_max = ens.envelope_max.copy()
            self._ensembles[e.uid] = e
            self.curve_tree.add_ensemble(e)
            new_canvas.add_ensemble(e)

        for uid, prof in src.get('vs_profiles', {}).items():
            import copy as _copy
            p = _copy.copy(prof)
            p.uid = str(_uuid.uuid4())[:8]
            self._vs_profiles[p.uid] = p
            self.curve_tree.add_vs_profile(p)
            new_canvas.add_vs_profile(p)

        new_canvas.auto_range()
        self.log_panel.log_info(f"Duplicated sheet '{src_name}' -> '{new_name}'")

    def _on_set_units(self, tab_index: int):
        """Set velocity units for a sheet."""
        from PySide6.QtWidgets import QInputDialog
        self._ensure_sheet_data(tab_index)
        current = self._sheet_data[tab_index].get('velocity_unit', 'metric')
        items = ["Metric (m/s)", "Imperial (ft/s)"]
        current_idx = 0 if current == 'metric' else 1
        item, ok = QInputDialog.getItem(
            self, "Velocity Units",
            "Select velocity unit for this sheet:",
            items, current_idx, False
        )
        if ok:
            unit = 'metric' if 'Metric' in item else 'imperial'
            self._sheet_data[tab_index]['velocity_unit'] = unit
            # Apply to canvas if this is the current sheet
            if tab_index == self._current_sheet_idx:
                canvas = self.sheet_tabs.get_current_canvas()
                canvas.set_velocity_unit(unit)
                self.log_panel.log_info(
                    f"Velocity unit set to {'m/s' if unit == 'metric' else 'ft/s'}"
                )
