"""Main application window with dockable panels and central canvas."""
import os
from pathlib import Path
from PySide6.QtWidgets import (
    QMainWindow, QDockWidget, QFileDialog, QToolBar,
    QStatusBar, QMessageBox, QApplication
)
from PySide6.QtCore import Qt, QSettings, QSize
from PySide6.QtGui import QAction, QKeySequence

from geo_figure.gui.canvas.sheet_tabs import SheetTabs
from geo_figure.gui.panels.curve_tree import CurveTreePanel
from geo_figure.gui.panels.properties_panel import PropertiesPanel
from geo_figure.gui.panels.log_panel import LogPanel
from geo_figure.core.models import (
    CurveData, CurveType, WaveType, SourceType, EnsembleData, FigureState
)
from geo_figure.io.curve_reader import read_dispersion_txt, read_theoretical_dc_txt, detect_and_read


class MainWindow(QMainWindow):
    """Main application window."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("GeoFigure -- Geophysical Data Visualization")
        self.setMinimumSize(1100, 700)
        self.resize(1400, 850)

        # Per-sheet data: sheet_index -> {curves, ensembles, selected_uid}
        self._sheet_data = {}
        self._current_sheet_idx = 0

        # Temp directory for session data (ensemble stats, etc.)
        import tempfile
        self._temp_dir = tempfile.mkdtemp(prefix="geofigure_")

        self._setup_central()
        self._setup_panels()
        self._setup_menubar()
        self._setup_toolbar()
        self._setup_statusbar()
        self._connect_signals()
        self._restore_state()

        # Initialize first sheet data
        self._ensure_sheet_data(0)

        self.log_panel.log_info("GeoFigure started. Use File -> Open to load dispersion curves.")

    # ── Setup ────────────────────────────────────────────────────

    def _setup_central(self):
        """Central widget: tabbed plot canvases."""
        self.sheet_tabs = SheetTabs()
        self.setCentralWidget(self.sheet_tabs)

    def _setup_panels(self):
        """Create dockable side panels."""
        # Left: Data Panel (renamed from Curves)
        self.curve_tree = CurveTreePanel()
        self.curve_dock = QDockWidget("Data", self)
        self.curve_dock.setWidget(self.curve_tree)
        self.curve_dock.setMinimumWidth(200)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.curve_dock)

        # Right: Properties
        self.properties = PropertiesPanel()
        self.props_dock = QDockWidget("Properties", self)
        self.props_dock.setWidget(self.properties)
        self.props_dock.setMinimumWidth(250)
        self.addDockWidget(Qt.RightDockWidgetArea, self.props_dock)

        # Bottom: Log
        self.log_panel = LogPanel()
        self.log_dock = QDockWidget("Log", self)
        self.log_dock.setWidget(self.log_panel)
        self.log_dock.setMaximumHeight(200)
        self.addDockWidget(Qt.BottomDockWidgetArea, self.log_dock)

    def _setup_menubar(self):
        menubar = self.menuBar()

        # File menu
        file_menu = menubar.addMenu("&File")
        open_action = file_menu.addAction("&Open Curve File...")
        open_action.setShortcut(QKeySequence.Open)
        open_action.triggered.connect(self._on_open_file)

        open_theo = file_menu.addAction("Open &Theoretical DC...")
        open_theo.triggered.connect(self._on_open_theoretical)

        file_menu.addSeparator()

        settings_action = file_menu.addAction("&Settings...")
        settings_action.triggered.connect(self._on_settings)

        file_menu.addSeparator()

        exit_action = file_menu.addAction("E&xit")
        exit_action.setShortcut(QKeySequence("Alt+F4"))
        exit_action.triggered.connect(self.close)

        # View menu
        view_menu = menubar.addMenu("&View")
        view_menu.addAction(self.curve_dock.toggleViewAction())
        view_menu.addAction(self.props_dock.toggleViewAction())
        view_menu.addAction(self.log_dock.toggleViewAction())
        view_menu.addSeparator()

        fit_action = view_menu.addAction("&Fit to Data")
        fit_action.setShortcut(QKeySequence("Ctrl+0"))
        fit_action.triggered.connect(self._on_fit_to_data)

        new_sheet = view_menu.addAction("&New Sheet")
        new_sheet.setShortcut(QKeySequence("Ctrl+T"))
        new_sheet.triggered.connect(self._on_new_sheet)

        view_menu.addSeparator()

        # Layout submenu
        layout_menu = view_menu.addMenu("Plot Layout")
        self._layout_combined = layout_menu.addAction("Combined (All on One Plot)")
        self._layout_combined.setCheckable(True)
        self._layout_combined.setChecked(True)
        self._layout_combined.triggered.connect(
            lambda: self._set_layout("combined")
        )
        self._layout_split = layout_menu.addAction("Split (Rayleigh | Love)")
        self._layout_split.setCheckable(True)
        self._layout_split.triggered.connect(
            lambda: self._set_layout("split_wave")
        )
        layout_menu.addSeparator()
        grid_action = layout_menu.addAction("Custom Grid...")
        grid_action.triggered.connect(self._on_custom_grid)
        layout_menu.addSeparator()
        self._link_y_action = layout_menu.addAction("Link Y-Axes")
        self._link_y_action.setCheckable(True)
        self._link_y_action.triggered.connect(self._on_toggle_link_y)
        self._link_x_action = layout_menu.addAction("Link X-Axes")
        self._link_x_action.setCheckable(True)
        self._link_x_action.triggered.connect(self._on_toggle_link_x)

        view_menu.addSeparator()

        # Theme submenu
        theme_menu = view_menu.addMenu("Theme")
        self._theme_light = theme_menu.addAction("Light")
        self._theme_light.setCheckable(True)
        self._theme_dark = theme_menu.addAction("Dark")
        self._theme_dark.setCheckable(True)
        # Set check based on saved preference
        saved_theme = QSettings("GeoFigure", "GeoFigure").value("theme", "light")
        self._theme_light.setChecked(saved_theme == "light")
        self._theme_dark.setChecked(saved_theme == "dark")
        self._theme_light.triggered.connect(lambda: self._set_theme("light"))
        self._theme_dark.triggered.connect(lambda: self._set_theme("dark"))

        # Analysis menu
        analysis_menu = menubar.addMenu("&Analysis")
        dc_compare_action = analysis_menu.addAction("DC Compare - Load Report...")
        dc_compare_action.triggered.connect(self._on_dc_compare)
        analysis_menu.addSeparator()
        analysis_menu.addAction("Vs Profile Mode").triggered.connect(
            lambda: self.log_panel.log_info("Vs Profile mode -- coming soon")
        )

        # Help menu
        help_menu = menubar.addMenu("&Help")
        about = help_menu.addAction("&About")
        about.triggered.connect(self._on_about)

    def _setup_toolbar(self):
        toolbar = QToolBar("Main Toolbar")
        toolbar.setMovable(False)
        toolbar.setIconSize(QSize(20, 20))
        toolbar.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.addToolBar(toolbar)

        open_act = toolbar.addAction("Open")
        open_act.setToolTip("Open dispersion curve file (Ctrl+O)")
        open_act.triggered.connect(self._on_open_file)

        theo_act = toolbar.addAction("Theoretical")
        theo_act.setToolTip("Open theoretical DC file")
        theo_act.triggered.connect(self._on_open_theoretical)

        dc_act = toolbar.addAction("DC Compare")
        dc_act.setToolTip("Load .report for DC Compare (Analysis)")
        dc_act.triggered.connect(self._on_dc_compare)

        toolbar.addSeparator()

        fit_act = toolbar.addAction("Fit")
        fit_act.setToolTip("Fit view to data (Ctrl+0)")
        fit_act.triggered.connect(self._on_fit_to_data)

        new_tab = toolbar.addAction("New Sheet")
        new_tab.setToolTip("Add new sheet (Ctrl+T)")
        new_tab.triggered.connect(self._on_new_sheet)

    def _setup_statusbar(self):
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready")

    def _connect_signals(self):
        # Curve tree signals
        self.curve_tree.curve_selected.connect(self._on_curve_selected)
        self.curve_tree.curve_visibility_changed.connect(self._on_curve_visibility)
        self.curve_tree.add_curve_requested.connect(self._on_open_file)
        self.curve_tree.load_target_requested.connect(self._on_load_target)
        self.curve_tree.remove_curve_requested.connect(self._on_remove_curve)
        self.curve_tree.point_visibility_changed.connect(self._on_point_visibility)
        self.curve_tree.curve_subplot_changed.connect(self._on_curve_subplot_changed)
        self.curve_tree.subplot_renamed.connect(self._on_subplot_renamed)
        self.curve_tree.ensemble_selected.connect(self._on_ensemble_selected)
        self.curve_tree.ensemble_layer_toggled.connect(self._on_ensemble_layer_toggled)
        self.curve_tree.remove_ensemble_requested.connect(self._on_remove_ensemble)
        self.curve_tree.subplot_activated.connect(self._on_subplot_activated)
        self.curve_tree.ensemble_subplot_changed.connect(self._on_ensemble_subplot_changed)

        # Properties panel signals
        self.properties.curve_updated.connect(self._on_curve_updated)
        self.properties.subplot_change_requested.connect(self._on_curve_subplot_changed)
        self.properties.ensemble_updated.connect(self._on_ensemble_updated)

        # Canvas signals
        canvas = self.sheet_tabs.get_current_canvas()
        canvas.curve_clicked.connect(self._on_curve_selected)
        canvas.layout_changed.connect(self._on_layout_structure_changed)

        # Sheet tab change
        self.sheet_tabs.currentChanged.connect(self._on_sheet_changed)
        self.sheet_tabs.duplicate_requested.connect(self._on_duplicate_sheet)
        self.sheet_tabs.units_requested.connect(self._on_set_units)

    # ── Per-sheet data helpers ───────────────────────────────────

    def _ensure_sheet_data(self, idx: int):
        """Create sheet data store if it doesn't exist."""
        if idx not in self._sheet_data:
            self._sheet_data[idx] = {
                'curves': {}, 'ensembles': {},
                'selected_uid': None, 'velocity_unit': 'metric'
            }

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
    def _selected_uid(self):
        self._ensure_sheet_data(self._current_sheet_idx)
        return self._sheet_data[self._current_sheet_idx]['selected_uid']

    @_selected_uid.setter
    def _selected_uid(self, val):
        self._ensure_sheet_data(self._current_sheet_idx)
        self._sheet_data[self._current_sheet_idx]['selected_uid'] = val

    def _rebuild_tree(self):
        """Rebuild the Data tree from current sheet's curves + ensembles."""
        canvas = self.sheet_tabs.get_current_canvas()
        subplot_info = canvas.get_subplot_info()
        self.curve_tree.set_subplot_structure(subplot_info)
        for uid, curve in self._curves.items():
            self.curve_tree.add_curve(curve)
        for uid, ens in self._ensembles.items():
            self.curve_tree.add_ensemble(ens)
        self.properties.set_available_subplots(subplot_info)

    def _on_sheet_changed(self, index: int):
        """Handle sheet tab switch — swap tree and properties to this sheet."""
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

        # Connect canvas signals for this canvas
        import warnings
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

    # ── Actions ──────────────────────────────────────────────────

    def _on_open_file(self):
        """Open one or more dispersion curve files (auto-detect format)."""
        files, _ = QFileDialog.getOpenFileNames(
            self, "Open Dispersion Curve Files",
            "",
            "All supported (*.txt *.csv *.target);;Text files (*.txt);;CSV files (*.csv);;Target files (*.target);;All files (*.*)"
        )
        if not files:
            return

        canvas = self.sheet_tabs.get_current_canvas()
        for filepath in files:
            try:
                curves = detect_and_read(filepath)
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

    def _on_curve_selected(self, uid: str):
        """Handle curve selection from tree or canvas."""
        # Unhighlight previous
        if self._selected_uid and self._selected_uid in self._curves:
            canvas = self.sheet_tabs.get_current_canvas()
            canvas.highlight_curve(self._selected_uid, False)

        self._selected_uid = uid
        curve = self._curves.get(uid)
        if curve:
            self.properties.show_curve(uid, curve)
            canvas = self.sheet_tabs.get_current_canvas()
            canvas.highlight_curve(uid, True)
            self.curve_tree.select_curve(uid)
            self.status_bar.showMessage(
                f"Selected: {curve.display_name} | {curve.n_points} pts | "
                f"{curve.freq_min:.2f}–{curve.freq_max:.2f} Hz"
            )

    def _on_curve_visibility(self, uid: str, visible: bool):
        """Toggle curve visibility on canvas."""
        if uid in self._curves:
            self._curves[uid].visible = visible
            canvas = self.sheet_tabs.get_current_canvas()
            canvas.set_curve_visible(uid, visible)

    def _on_point_visibility(self, uid: str, index: int, visible: bool):
        """Toggle individual point visibility and re-plot."""
        curve = self._curves.get(uid)
        if curve and curve.point_mask is not None:
            curve.point_mask[index] = visible
            canvas = self.sheet_tabs.get_current_canvas()
            canvas.add_curve(curve)

    def _on_curve_updated(self, uid: str, curve: CurveData):
        """Handle curve property changes from the properties panel."""
        old_curve = self._curves.get(uid)
        type_changed = (
            old_curve and old_curve.curve_type != curve.curve_type
        )
        self._curves[uid] = curve
        canvas = self.sheet_tabs.get_current_canvas()
        canvas.update_curve_style(uid, curve)
        if type_changed:
            # Re-categorize in tree (remove + re-add)
            self.curve_tree.remove_curve(uid)
            self.curve_tree.add_curve(curve)
        else:
            self.curve_tree.update_curve(uid, curve)

    def _on_remove_curve(self, uid: str):
        """Remove a curve."""
        if uid in self._curves:
            del self._curves[uid]
            self.curve_tree.remove_curve(uid)
            canvas = self.sheet_tabs.get_current_canvas()
            canvas.remove_curve(uid)
            if self._selected_uid == uid:
                self._selected_uid = None
                self.properties.clear()
            self.log_panel.log_info("Curve removed")

    def _on_fit_to_data(self):
        canvas = self.sheet_tabs.get_current_canvas()
        canvas.auto_range()

    def _on_new_sheet(self):
        n = self.sheet_tabs.count() + 1
        self.sheet_tabs.add_sheet(f"Sheet {n}")

    def _set_layout(self, mode: str):
        """Switch canvas layout mode."""
        canvas = self.sheet_tabs.get_current_canvas()
        canvas.set_layout_mode(mode)
        self._layout_combined.setChecked(mode == "combined")
        self._layout_split.setChecked(mode == "split_wave")
        self.log_panel.log_info(
            f"Layout: {'Combined' if mode == 'combined' else 'Split (Rayleigh | Love)'}"
        )

    def _on_custom_grid(self):
        """Prompt for rows x columns grid layout."""
        from PySide6.QtWidgets import QInputDialog
        text, ok = QInputDialog.getText(
            self, "Custom Grid Layout",
            "Enter rows x columns (e.g. 2x2):",
            text="1x2"
        )
        if ok and text:
            try:
                parts = text.lower().replace(',', 'x').split('x')
                rows, cols = int(parts[0].strip()), int(parts[1].strip())
                canvas = self.sheet_tabs.get_current_canvas()
                canvas.set_grid(rows, cols)
                self._layout_combined.setChecked(False)
                self._layout_split.setChecked(False)
                self.log_panel.log_info(f"Layout: {rows}x{cols} grid")
            except (ValueError, IndexError):
                self.log_panel.log_error("Invalid grid format. Use NxM (e.g. 2x2)")

    def _on_toggle_link_y(self):
        """Toggle Y-axis linking across subplots."""
        canvas = self.sheet_tabs.get_current_canvas()
        linked = self._link_y_action.isChecked()
        canvas.set_link_y(linked)
        self.log_panel.log_info(
            f"Y-axes {'linked' if linked else 'independent'}"
        )

    def _on_toggle_link_x(self):
        """Toggle X-axis linking across subplots."""
        canvas = self.sheet_tabs.get_current_canvas()
        linked = self._link_x_action.isChecked()
        canvas.set_link_x(linked)
        self.log_panel.log_info(
            f"X-axes {'linked' if linked else 'independent'}"
        )

    def _on_curve_subplot_changed(self, uid: str, new_key: str):
        """Move a curve to a different subplot."""
        curve = self._curves.get(uid)
        if not curve:
            return
        old_key = curve.subplot_key
        if old_key == new_key:
            return
        curve.subplot_key = new_key
        # Re-plot: remove from old subplot, add to new
        canvas = self.sheet_tabs.get_current_canvas()
        canvas.remove_curve(uid)
        canvas.add_curve(curve)
        canvas.auto_range()
        # Rebuild tree (block signals to prevent visibility toggle during removal)
        self.curve_tree.tree.blockSignals(True)
        self.curve_tree.remove_curve(uid)
        self.curve_tree.add_curve(curve)
        self.curve_tree.tree.blockSignals(False)
        self.log_panel.log_info(f"Moved '{curve.display_name}' to subplot '{new_key}'")

    def _on_subplot_activated(self, key: str):
        """Set the active subplot when user clicks a subplot root in the tree."""
        canvas = self.sheet_tabs.get_current_canvas()
        canvas._active_subplot = key
        name = canvas._subplot_names.get(key, key)
        self.status_bar.showMessage(f"Active subplot: {name}")

    def _on_ensemble_subplot_changed(self, uid: str, new_key: str):
        """Move an ensemble (with all layers) to a different subplot."""
        ens = self._ensembles.get(uid)
        if not ens:
            return
        if ens.subplot_key == new_key:
            return
        ens.subplot_key = new_key
        canvas = self.sheet_tabs.get_current_canvas()
        canvas.remove_ensemble(uid)
        canvas.add_ensemble(ens)
        canvas.auto_range()
        # Rebuild tree items (block signals to avoid toggle side-effects)
        self.curve_tree.tree.blockSignals(True)
        self.curve_tree.remove_ensemble(uid)
        self.curve_tree.add_ensemble(ens)
        self.curve_tree.tree.blockSignals(False)
        self.log_panel.log_info(
            f"Moved '{ens.display_name}' to subplot '{new_key}'"
        )

    def _on_subplot_renamed(self, key: str, new_name: str):
        """Rename a subplot on the canvas and refresh tree."""
        canvas = self.sheet_tabs.get_current_canvas()
        canvas.rename_subplot(key, new_name)
        self._rebuild_tree()
        self.log_panel.log_info(f"Renamed subplot to '{new_name}'")

    def _on_layout_structure_changed(self, subplot_info: list):
        """Canvas layout changed — migrate curves and update tree."""
        valid_keys = {k for k, _ in subplot_info}
        first_key = subplot_info[0][0] if subplot_info else "main"

        canvas = self.sheet_tabs.get_current_canvas()
        layout_mode = canvas.layout_mode

        for uid, curve in self._curves.items():
            if curve.subplot_key not in valid_keys:
                if layout_mode == "split_wave":
                    curve.subplot_key = (
                        "love" if curve.wave_type == WaveType.LOVE else "rayleigh"
                    )
                else:
                    curve.subplot_key = first_key

        for uid, ens in self._ensembles.items():
            if ens.subplot_key not in valid_keys:
                ens.subplot_key = first_key

        self._rebuild_tree()

    def _on_dc_compare(self):
        """Open DC Compare dialog to extract theoretical curves from .report."""
        from geo_figure.gui.dialogs.dc_compare_dialog import DCCompareDialog
        dlg = DCCompareDialog(self)
        dlg.extraction_complete.connect(self._on_extraction_complete)
        dlg.exec()

    def _on_extraction_complete(self, results: dict):
        """Handle completed DC Compare extraction — create EnsembleData with layers."""
        from geo_figure.io.report_reader import compute_ensemble_statistics
        results.pop("__include_individual", False)
        canvas = self.sheet_tabs.get_current_canvas()
        target_key = canvas.active_subplot

        for wave_key, parsed in results.items():
            n_profiles = parsed.get("n_profiles", 0)
            modes = parsed.get("modes", {0})
            wave_type_str = parsed.get("wave_type", "Rayleigh")
            wt = WaveType.LOVE if "love" in wave_key else WaveType.RAYLEIGH

            for mode in sorted(modes):
                try:
                    stats = compute_ensemble_statistics(parsed, mode=mode)
                except ValueError as e:
                    self.log_panel.log_error(f"Stats failed for {wave_key} M{mode}: {e}")
                    continue

                mode_label = f" M{mode}" if mode > 0 else ""
                ens = EnsembleData.from_stats(
                    stats, parsed=parsed,
                    name=f"Theoretical {wave_type_str}{mode_label}",
                    wave_type=wt,
                    mode=mode,
                    subplot_key=target_key,
                )

                # Store and render
                self._ensembles[ens.uid] = ens
                canvas.add_ensemble(ens)
                self.curve_tree.add_ensemble(ens)
                self._save_ensemble_temp(ens)

                self.log_panel.log_success(
                    f"DC Compare: {wave_type_str}{mode_label} -- "
                    f"{n_profiles} profiles, median + percentile bands"
                )

        canvas.auto_range()

    def _on_ensemble_selected(self, uid: str):
        """Handle ensemble selection from tree."""
        ens = self._ensembles.get(uid)
        if ens:
            self.properties.show_ensemble(uid, ens)
            self.status_bar.showMessage(
                f"Selected: {ens.display_name} | {ens.n_profiles} models"
            )

    def _on_ensemble_layer_toggled(self, uid: str, layer_name: str, visible: bool):
        """Toggle visibility of an ensemble layer."""
        ens = self._ensembles.get(uid)
        if not ens:
            return
        layer = getattr(ens, f"{layer_name}_layer", None)
        if layer:
            layer.visible = visible
        canvas = self.sheet_tabs.get_current_canvas()
        canvas.set_ensemble_layer_visible(uid, layer_name, visible)

    def _on_remove_ensemble(self, uid: str):
        """Remove an ensemble from data and canvas."""
        if uid in self._ensembles:
            del self._ensembles[uid]
        canvas = self.sheet_tabs.get_current_canvas()
        canvas.remove_ensemble(uid)
        self.curve_tree.remove_ensemble(uid)
        self.log_panel.log_info("Removed ensemble")

    def _on_ensemble_updated(self, uid: str, ens: EnsembleData):
        """Handle ensemble style changes from properties panel — re-render."""
        self._ensembles[uid] = ens
        canvas = self.sheet_tabs.get_current_canvas()
        canvas.update_ensemble(ens)

    def _on_about(self):
        QMessageBox.about(
            self, "About GeoFigure",
            "GeoFigure v0.1.0\n\n"
            "Geophysical Data Visualization Studio\n"
            "Built with PySide6 + PyQtGraph"
        )

    def _on_duplicate_sheet(self, source_index: int):
        """Duplicate a sheet with all its curves and ensembles."""
        import copy
        self._ensure_sheet_data(source_index)
        src = self._sheet_data[source_index]

        # Create new sheet
        src_name = self.sheet_tabs.tabText(source_index)
        new_name = f"{src_name} (Copy)"
        self.sheet_tabs.add_sheet(new_name)
        new_idx = self.sheet_tabs.count() - 1
        self._ensure_sheet_data(new_idx)

        # Deep copy curves
        new_canvas = self.sheet_tabs.get_current_canvas()
        new_canvas.set_velocity_unit(src.get('velocity_unit', 'metric'))
        self._sheet_data[new_idx]['velocity_unit'] = src.get('velocity_unit', 'metric')

        for uid, curve in src['curves'].items():
            c = copy.copy(curve)
            c.uid = str(__import__('uuid').uuid4())[:8]
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
            e.uid = str(__import__('uuid').uuid4())[:8]
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

    def _on_settings(self):
        """Open settings dialog."""
        from geo_figure.gui.dialogs.settings_dialog import SettingsDialog
        dlg = SettingsDialog(self)
        if dlg.exec():
            self.log_panel.log_info("Settings saved")

    def _set_theme(self, theme_name: str):
        """Switch application theme."""
        from geo_figure.gui.theme import apply_theme
        app = QApplication.instance()
        apply_theme(app, theme_name)
        settings = QSettings("GeoFigure", "GeoFigure")
        settings.setValue("theme", theme_name)
        self._theme_light.setChecked(theme_name == "light")
        self._theme_dark.setChecked(theme_name == "dark")
        # Rebuild canvases to pick up new pyqtgraph colors
        for i in range(self.sheet_tabs.count()):
            canvas = self.sheet_tabs.widget(i)
            if hasattr(canvas, 'set_layout_mode'):
                canvas.rebuild()
        self.log_panel.log_info(f"Theme: {theme_name.title()}")

    # ── Helpers ──────────────────────────────────────────────────

    def _add_curve(self, curve: CurveData, canvas):
        """Add a curve to the data store, tree, and canvas."""
        # Assign to the active subplot if the curve has default key
        if curve.subplot_key == "main" and "main" not in canvas._plots:
            curve.subplot_key = canvas.active_subplot
        self._curves[curve.uid] = curve
        self.curve_tree.add_curve(curve)
        canvas.add_curve(curve)

    def capture_figure_state(self) -> FigureState:
        """Build a FigureState snapshot of the current sheet.

        This is the single source of truth that any renderer (PyQtGraph
        interactive view, Matplotlib publication export) reads from.
        """
        canvas = self.sheet_tabs.get_current_canvas()
        cfg = canvas.get_layout_config()
        theme = QSettings("GeoFigure", "GeoFigure").value("theme", "light")
        self._ensure_sheet_data(self._current_sheet_idx)
        vel_unit = self._sheet_data[self._current_sheet_idx].get('velocity_unit', 'metric')
        return FigureState(
            layout_mode=cfg["layout_mode"],
            grid_rows=cfg["grid_rows"],
            grid_cols=cfg["grid_cols"],
            link_y=cfg["link_y"],
            link_x=cfg["link_x"],
            subplot_names=cfg["subplot_names"],
            curves=list(self._curves.values()),
            ensembles=list(self._ensembles.values()),
            theme=theme,
            velocity_unit=vel_unit,
        )

    @property
    def figure_state(self) -> FigureState:
        """Current figure state (always up-to-date, rebuilt on access)."""
        return self.capture_figure_state()

    # ── State persistence ────────────────────────────────────────

    def _restore_state(self):
        settings = QSettings("GeoFigure", "GeoFigure")
        geo = settings.value("geometry")
        if geo:
            self.restoreGeometry(geo)
        state = settings.value("windowState")
        if state:
            self.restoreState(state)

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
        # Clean up temp directory
        import shutil
        try:
            shutil.rmtree(self._temp_dir, ignore_errors=True)
        except Exception:
            pass
        event.accept()
