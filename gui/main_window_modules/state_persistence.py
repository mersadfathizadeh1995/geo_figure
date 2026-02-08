"""State persistence: save/restore, temp files, figure state, settings, theme."""
import os

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication, QMessageBox


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
        return FigureState(
            layout_mode=cfg["layout_mode"],
            grid_rows=cfg["grid_rows"],
            grid_cols=cfg["grid_cols"],
            link_y=cfg["link_y"],
            link_x=cfg["link_x"],
            subplot_names=cfg["subplot_names"],
            subplot_types=cfg.get("subplot_types", {}),
            curves=curves,
            ensembles=ensembles,
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
            link_y=cfg["link_y"],
            link_x=cfg["link_x"],
            subplot_names=cfg["subplot_names"],
            subplot_types=cfg.get("subplot_types", {}),
            curves=list(self._curves.values()),
            ensembles=list(self._ensembles.values()),
            theme=theme,
            velocity_unit=vel_unit,
        )

    @property
    def figure_state(self):
        """Current figure state (always up-to-date, rebuilt on access)."""
        return self.capture_figure_state()

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
