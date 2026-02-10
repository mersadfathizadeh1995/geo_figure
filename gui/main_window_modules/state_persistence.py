"""State persistence: save/restore, temp files, figure state, settings, theme."""
import os

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox


class StatePersistenceMixin:
    """Persistence, settings, theme, and figure-state capture."""

    _STATE_VERSION = 2  # bump when dock layout changes

    def _restore_state(self):
        settings = QSettings("GeoFigure", "GeoFigure")
        version = settings.value("state_version", 0)
        try:
            version = int(version)
        except (TypeError, ValueError):
            version = 0
        if version != self._STATE_VERSION:
            # Stale state from older layout — skip restore
            settings.remove("geometry")
            settings.remove("windowState")
            settings.setValue("state_version", self._STATE_VERSION)
            return
        geo = settings.value("geometry")
        if geo:
            self.restoreGeometry(geo)
        state = settings.value("windowState")
        if state:
            try:
                self.restoreState(state)
            except Exception:
                pass

    def _save_ensemble_temp(self, ens):
        """Save ensemble stats to temp directory for session persistence."""
        import pickle
        fpath = os.path.join(self._temp_dir, f"ens_{ens.uid}.pkl")
        try:
            data = {
                'uid': ens.uid, 'name': ens.name, 'custom_name': ens.custom_name,
                'wave_type': ens.wave_type, 'mode': ens.mode,
                'n_profiles': ens.n_profiles, 'subplot_key': ens.subplot_key,
                'freq': ens.freq, 'median': ens.median,
                'p_low': ens.p_low, 'p_high': ens.p_high,
                'envelope_min': ens.envelope_min, 'envelope_max': ens.envelope_max,
                'sigma_ln': ens.sigma_ln,
                'individual_freqs': ens.individual_freqs,
                'individual_vels': ens.individual_vels,
            }
            with open(fpath, 'wb') as f:
                pickle.dump(data, f)
        except Exception as e:
            self.log_panel.log_error(f"Failed to save ensemble temp: {e}")

    def closeEvent(self, event):
        settings = QSettings("GeoFigure", "GeoFigure")
        settings.setValue("geometry", self.saveGeometry())
        settings.setValue("windowState", self.saveState())
        settings.setValue("state_version", self._STATE_VERSION)
        # Auto-save figure state for each sheet
        self._save_all_sheet_states()
        event.accept()

    def _save_all_sheet_states(self):
        """Persist FigureState for every sheet to the project session dir."""
        session_dir = os.path.join(str(self._project_dir), "session")
        os.makedirs(session_dir, exist_ok=True)
        for i in range(self.sheet_tabs.count()):
            self._current_sheet_idx = i
            self._ensure_sheet_data(i)
            try:
                state = self.capture_figure_state_for_sheet(i)
                sheet_name = self.sheet_tabs.tabText(i)
                safe_name = "".join(
                    c if c.isalnum() or c in (' ', '_', '-') else '_'
                    for c in sheet_name
                ).strip()
                fpath = os.path.join(session_dir, f"sheet_{i}_{safe_name}.state")
                state.save(fpath)
            except Exception:
                pass

    def capture_figure_state_for_sheet(self, sheet_index: int):
        """Build a FigureState for a specific sheet index."""
        from geo_figure.core.models import FigureState
        canvas = self.sheet_tabs.widget(sheet_index)
        cfg = canvas.get_layout_config()
        theme = QSettings("GeoFigure", "GeoFigure").value("theme", "light")
        sd = self._sheet_data.get(sheet_index, {})
        vel_unit = sd.get('velocity_unit', 'metric')
        curves = list(sd.get('curves', {}).values())
        ensembles = list(sd.get('ensembles', {}).values())
        vs_profiles = list(sd.get('vs_profiles', {}).values())
        return FigureState(
            layout_mode=cfg["layout_mode"],
            grid_rows=cfg["grid_rows"],
            grid_cols=cfg["grid_cols"],
            grid_col_ratios=cfg.get("grid_col_ratios", []),
            link_y=cfg["link_y"],
            link_x=cfg["link_x"],
            subplot_names=cfg["subplot_names"],
            subplot_types=cfg.get("subplot_types", {}),
            curves=curves,
            ensembles=ensembles,
            vs_profiles=vs_profiles,
            theme=theme,
            velocity_unit=vel_unit,
        )

    def capture_figure_state(self):
        """Build a FigureState snapshot of the current sheet."""
        from geo_figure.core.models import FigureState
        canvas = self.sheet_tabs.get_current_canvas()
        cfg = canvas.get_layout_config()
        theme = QSettings("GeoFigure", "GeoFigure").value("theme", "light")
        self._ensure_sheet_data(self._current_sheet_idx)
        vel_unit = self._sheet_data[self._current_sheet_idx].get(
            'velocity_unit', 'metric'
        )
        return FigureState(
            layout_mode=cfg["layout_mode"],
            grid_rows=cfg["grid_rows"],
            grid_cols=cfg["grid_cols"],
            grid_col_ratios=cfg.get("grid_col_ratios", []),
            link_y=cfg["link_y"],
            link_x=cfg["link_x"],
            subplot_names=cfg["subplot_names"],
            subplot_types=cfg.get("subplot_types", {}),
            curves=list(self._curves.values()),
            ensembles=list(self._ensembles.values()),
            vs_profiles=list(self._vs_profiles.values()),
            theme=theme,
            velocity_unit=vel_unit,
        )

    @property
    def figure_state(self):
        """Current figure state (always up-to-date, rebuilt on access)."""
        return self.capture_figure_state()

    def _on_open_studio(self):
        """Open Matplotlib Studio for the current sheet."""
        from PySide6.QtCore import Qt as QtCore_Qt
        from geo_figure.gui.studio.studio_window import StudioWindow
        try:
            fig_state = self.capture_figure_state()
            sheet_name = self.sheet_tabs.tabText(self._current_sheet_idx)

            # Collect current axis ranges from the PyQtGraph canvas
            canvas_ranges = {}
            canvas = self.sheet_tabs.get_current_canvas()
            if canvas and hasattr(canvas, '_plots'):
                for key, plot_item in canvas._plots.items():
                    if key.endswith("_sigma"):
                        continue
                    try:
                        vb = plot_item.vb
                        x_range, y_range = vb.viewRange()
                        canvas_ranges[key] = (
                            (x_range[0], x_range[1]),
                            (y_range[0], y_range[1]),
                        )
                    except Exception:
                        pass

            studio = StudioWindow(
                fig_state, sheet_name=sheet_name,
                canvas_ranges=canvas_ranges,
                project_dir=str(getattr(self, '_project_dir', '')),
                parent=self,
            )
            studio.setAttribute(QtCore_Qt.WA_DeleteOnClose)
            studio.show()
            self.log_panel.log_info(
                f"Matplotlib Studio opened for '{sheet_name}'"
            )
        except Exception as e:
            QMessageBox.warning(self, "Studio Error", str(e))

    def _on_settings(self):
        """Open settings dialog."""
        from geo_figure.gui.dialogs.settings_dialog import SettingsDialog
        dlg = SettingsDialog(self)
        if dlg.exec():
            self.log_panel.log_info("Settings saved")

    def _on_change_project(self):
        """Change the project directory."""
        from geo_figure.gui.dialogs.project_dialog import ProjectDialog
        dlg = ProjectDialog(self)
        if dlg.exec():
            from pathlib import Path
            self._project_dir = dlg.get_project_dir()
            self._project_name = dlg.get_project_name()
            for sub in ("theoretical", "experimental", "figures", "csv", "session"):
                (self._project_dir / sub).mkdir(parents=True, exist_ok=True)
            self._temp_dir = str(self._project_dir / "session")
            self.setWindowTitle(f"GeoFigure -- {self._project_name}")
            self.log_panel.log_info(
                f"Project changed: {self._project_name} | {self._project_dir}"
            )

    def _set_theme(self, theme_name: str):
        """Switch application theme."""
        from geo_figure.gui.theme import apply_theme
        app = QApplication.instance()
        apply_theme(app, theme_name)
        settings = QSettings("GeoFigure", "GeoFigure")
        settings.setValue("theme", theme_name)
        self._theme_light.setChecked(theme_name == "light")
        self._theme_dark.setChecked(theme_name == "dark")
        for i in range(self.sheet_tabs.count()):
            canvas = self.sheet_tabs.widget(i)
            if hasattr(canvas, 'set_layout_mode'):
                canvas.rebuild()
        self.log_panel.log_info(f"Theme: {theme_name.title()}")

    def _on_about(self):
        QMessageBox.about(
            self, "About GeoFigure",
            "GeoFigure v0.1.0\n\n"
            "Geophysical Data Visualization Studio\n"
            "Built with PySide6 + PyQtGraph"
        )

    # ── Sheet save/load ───────────────────────────────────────

    def _on_save_sheet(self):
        """Save the current sheet to the project sheets directory."""
        from geo_figure.io.sheet_persistence import save_sheet
        try:
            canvas = self.sheet_tabs.get_current_canvas()
            fig_state = self.capture_figure_state()
            sheet_name = self.sheet_tabs.tabText(self._current_sheet_idx)
            path = save_sheet(
                str(self._project_dir), sheet_name, fig_state, canvas
            )
            self.log_panel.log_info(f"Sheet saved: {path}")
        except Exception as e:
            QMessageBox.warning(self, "Save Error", str(e))

    def _on_save_all_sheets(self):
        """Save every sheet tab to the project sheets directory."""
        from geo_figure.io.sheet_persistence import save_sheet
        saved = 0
        for i in range(self.sheet_tabs.count()):
            try:
                canvas = self.sheet_tabs.widget(i)
                fig_state = self.capture_figure_state_for_sheet(i)
                sheet_name = self.sheet_tabs.tabText(i)
                save_sheet(str(self._project_dir), sheet_name, fig_state, canvas)
                saved += 1
            except Exception:
                pass
        self.log_panel.log_info(f"Saved {saved} sheet(s)")

    def _on_load_sheet(self):
        """Load a sheet from the project sheets directory or browse for one."""
        from geo_figure.io.sheet_persistence import list_saved_sheets, load_sheet
        sheets = list_saved_sheets(str(self._project_dir))
        if sheets:
            from PySide6.QtWidgets import QInputDialog
            names = [s[0] for s in sheets]
            name, ok = QInputDialog.getItem(
                self, "Load Sheet",
                "Select a saved sheet to load:", names, 0, False
            )
            if not ok:
                return
            sheet_path = next(s[1] for s in sheets if s[0] == name)
        else:
            sheet_path = QFileDialog.getExistingDirectory(
                self, "Select Sheet Folder",
                str(self._project_dir),
            )
            if not sheet_path:
                return
        try:
            self._restore_sheet_from_file(sheet_path)
        except Exception as e:
            QMessageBox.warning(self, "Load Error", str(e))

    def _restore_sheet_from_file(self, filepath: str):
        """Restore a full sheet from a saved sheet folder."""
        from geo_figure.io.sheet_persistence import load_sheet
        sheet_name, fig_state, canvas_config = load_sheet(filepath)

        # Create new sheet tab
        self.sheet_tabs.add_sheet(sheet_name)
        new_idx = self.sheet_tabs.count() - 1
        self._current_sheet_idx = new_idx
        self._ensure_sheet_data(new_idx)
        canvas = self.sheet_tabs.get_current_canvas()

        # Apply layout
        canvas._subplot_names = dict(fig_state.subplot_names)
        canvas._subplot_types = dict(fig_state.subplot_types)
        canvas._link_y = fig_state.link_y
        canvas._link_x = fig_state.link_x
        if fig_state.layout_mode == "grid":
            canvas._grid_rows = fig_state.grid_rows
            canvas._grid_cols = fig_state.grid_cols
            canvas._grid_col_ratios = list(fig_state.grid_col_ratios) or [1.0] * fig_state.grid_cols
            canvas._layout_mode = "grid"
            canvas.rebuild()
        elif fig_state.layout_mode != canvas.layout_mode:
            canvas.set_layout_mode(fig_state.layout_mode)

        # Set velocity unit
        vel_unit = fig_state.velocity_unit or "metric"
        self._sheet_data[new_idx]['velocity_unit'] = vel_unit
        canvas.set_velocity_unit(vel_unit)

        # Populate data
        for curve in fig_state.curves:
            self._curves[curve.uid] = curve
            canvas.add_curve(curve)

        for ens in fig_state.ensembles:
            self._ensembles[ens.uid] = ens
            canvas.add_ensemble(ens)

        for prof in fig_state.vs_profiles:
            self._vs_profiles[prof.uid] = prof
            canvas.add_vs_profile(prof)

        # Apply canvas display config (legend, axis ranges)
        canvas.apply_canvas_config(canvas_config)

        # Rebuild tree and auto-range
        self._rebuild_tree()
        canvas.auto_range()

        self.log_panel.log_info(f"Sheet loaded: {sheet_name}")
