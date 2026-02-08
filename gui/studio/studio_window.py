"""Matplotlib Studio — publication-quality figure rendering window.

Opens as a standalone QMainWindow. Receives a FigureState snapshot from the
main app and renders it via MplRenderer.  Settings panels on the right drive
real-time re-renders through a debounced timer.
"""
import os
import traceback
from functools import partial

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
    QStatusBar, QMessageBox, QSplitter, QApplication,
    QScrollArea,
)
from PySide6.QtCore import Qt, QTimer, QSettings
from PySide6.QtGui import QAction, QKeySequence

import matplotlib
matplotlib.use("Agg")
from matplotlib.backends.backend_qtagg import (
    FigureCanvasQTAgg as FigureCanvas,
    NavigationToolbar2QT as NavigationToolbar,
)
from matplotlib.figure import Figure

from geo_figure.core.models import FigureState
from geo_figure.gui.studio.models import StudioSettings
from geo_figure.gui.studio.presets import apply_preset, get_preset_names, get_preset_label
from geo_figure.gui.studio.renderer import MplRenderer
from geo_figure.gui.studio.panels.figure_panel import FigurePanel
from geo_figure.gui.studio.panels.typography_panel import TypographyPanel
from geo_figure.gui.studio.panels.axis_panel import AxisPanel
from geo_figure.gui.studio.panels.legend_panel import LegendPanel
from geo_figure.gui.studio.panels.export_panel import ExportPanel
from geo_figure.gui.studio.panels.layers_panel import LayersPanel


class StudioWindow(QMainWindow):
    """Matplotlib Studio — renders a sheet's data as a publication figure."""

    def __init__(self, fig_state: FigureState, sheet_name: str = "",
                 canvas_ranges: dict = None, parent=None):
        """
        Parameters
        ----------
        fig_state : FigureState
            Snapshot of the sheet's data (curves, ensembles, vs_profiles).
        sheet_name : str
            Display name for the sheet.
        canvas_ranges : dict, optional
            Per-subplot axis ranges from the PyQtGraph canvas.
            Format: {subplot_key: ((xmin, xmax), (ymin, ymax))}.
        """
        super().__init__(parent)
        self._state = fig_state
        self._sheet_name = sheet_name or "Sheet"
        self._settings = StudioSettings()
        self._renderer = MplRenderer()
        self._canvas_ranges = canvas_ranges or {}
        self._render_timer = QTimer(self)
        self._render_timer.setSingleShot(True)
        self._render_timer.setInterval(120)
        self._render_timer.timeout.connect(self._do_render)
        self._is_rendering = False

        self.setWindowTitle(f"Matplotlib Studio - {self._sheet_name}")
        self.resize(1300, 850)

        self._build_ui()
        self._build_menus()
        self._init_panels_from_state()

        # Initial render after the window is laid out
        QTimer.singleShot(100, self._do_render)

    # ── UI construction ───────────────────────────────────────────

    def _build_ui(self):
        """Build the main layout: layers (left) + canvas (center) + settings (right)."""
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(4, 4, 4, 4)
        main_layout.setSpacing(4)

        splitter = QSplitter(Qt.Horizontal)

        # -- Left: layers panel --
        self._layers_panel = LayersPanel()
        self._layers_panel.setMinimumWidth(180)
        self._layers_panel.setMaximumWidth(260)
        self._layers_panel.visibility_changed.connect(self._schedule_render)
        self._layers_panel.axis_label_toggled.connect(self._on_axis_label_toggled)
        splitter.addWidget(self._layers_panel)

        # -- Center: matplotlib canvas + toolbar --
        canvas_container = QWidget()
        canvas_layout = QVBoxLayout(canvas_container)
        canvas_layout.setContentsMargins(0, 0, 0, 0)
        canvas_layout.setSpacing(0)

        # Create figure at configured size with screen-resolution DPI
        w_in = self._settings.figure.width
        h_in = self._settings.figure.height
        self._figure = Figure(figsize=(w_in, h_in), dpi=self.PREVIEW_DPI,
                              facecolor="white")
        self._canvas = FigureCanvas(self._figure)
        self._canvas.setFixedSize(int(w_in * self.PREVIEW_DPI),
                                  int(h_in * self.PREVIEW_DPI))
        self._toolbar = NavigationToolbar(self._canvas, self)

        # Scroll area so the exact-size canvas can be scrolled if needed
        self._canvas_scroll = QScrollArea()
        self._canvas_scroll.setWidget(self._canvas)
        self._canvas_scroll.setWidgetResizable(False)
        self._canvas_scroll.setAlignment(Qt.AlignCenter)

        canvas_layout.addWidget(self._toolbar)
        canvas_layout.addWidget(self._canvas_scroll, stretch=1)
        splitter.addWidget(canvas_container)

        # -- Right: settings tabs (scrollable) --
        self._tabs = QTabWidget()
        self._tabs.setMinimumWidth(270)
        self._tabs.setMaximumWidth(360)

        self._figure_panel = FigurePanel()
        self._typography_panel = TypographyPanel()
        self._axis_panel = AxisPanel()
        self._legend_panel = LegendPanel()
        self._export_panel = ExportPanel()

        # Wrap each panel in a scroll area for long content
        for panel, label in [
            (self._figure_panel, "Figure"),
            (self._typography_panel, "Typography"),
            (self._axis_panel, "Axis"),
            (self._legend_panel, "Legend"),
            (self._export_panel, "Export"),
        ]:
            scroll = QScrollArea()
            scroll.setWidget(panel)
            scroll.setWidgetResizable(True)
            scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            self._tabs.addTab(scroll, label)

        splitter.addWidget(self._tabs)

        # Stretch factors: layers fixed, canvas expands, tabs fixed
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setStretchFactor(2, 0)
        splitter.setSizes([210, 780, 310])

        main_layout.addWidget(splitter)

        # Status bar
        self._status = QStatusBar()
        self.setStatusBar(self._status)
        self._status.showMessage("Ready")

        # Connect panel signals
        self._figure_panel.changed.connect(self._schedule_render)
        self._typography_panel.changed.connect(self._schedule_render)
        self._axis_panel.changed.connect(self._schedule_render)
        self._axis_panel.use_canvas_limits.connect(self._on_use_view_limits)
        self._legend_panel.changed.connect(self._schedule_render)
        self._typography_panel.preset_requested.connect(self._apply_preset)
        self._export_panel.export_requested.connect(self._do_export)
        self._export_panel.batch_requested.connect(self._do_batch_export)

    def _build_menus(self):
        """Build menu bar."""
        menu_bar = self.menuBar()

        # File menu
        file_menu = menu_bar.addMenu("File")
        export_act = QAction("Export...", self)
        export_act.setShortcut(QKeySequence("Ctrl+E"))
        export_act.triggered.connect(
            lambda: self._tabs.setCurrentIndex(4)  # Export tab
        )
        file_menu.addAction(export_act)
        file_menu.addSeparator()
        close_act = QAction("Close", self)
        close_act.setShortcut(QKeySequence("Ctrl+W"))
        close_act.triggered.connect(self.close)
        file_menu.addAction(close_act)

        # Presets menu
        presets_menu = menu_bar.addMenu("Presets")
        for name in get_preset_names():
            act = QAction(get_preset_label(name), self)
            act.triggered.connect(partial(self._apply_preset, name))
            presets_menu.addAction(act)

        # View menu
        view_menu = menu_bar.addMenu("View")
        refresh_act = QAction("Refresh", self)
        refresh_act.setShortcut(QKeySequence("F5"))
        refresh_act.triggered.connect(self._do_render)
        view_menu.addAction(refresh_act)
        reset_act = QAction("Reset to Defaults", self)
        reset_act.triggered.connect(self._reset_settings)
        view_menu.addAction(reset_act)

    # ── Initialization from canvas data ───────────────────────────

    def _init_panels_from_state(self):
        """Initialize all panels from FigureState + canvas ranges."""
        # Auto-configure axis defaults from state + canvas ranges
        self._auto_configure_axes()

        # Build subplot info for panels
        subplot_info = self._get_subplot_info()

        # Populate layers grouped by subplot
        self._layers_panel.populate(
            self._state, subplot_info, self._settings
        )

        # Read settings into panels
        self._figure_panel.read_from(self._settings.figure)
        self._typography_panel.read_from(self._settings.typography)
        self._legend_panel.read_from(self._settings.legend)

        # Show Vs Profile layout controls if Vs data exists
        has_vs = bool(getattr(self._state, "vs_profiles", []))
        self._figure_panel.set_vs_visible(has_vs)
        if has_vs:
            self._figure_panel.read_vs_from(self._settings)

        # Populate axis panel with subplot info and canvas ranges
        self._axis_panel.set_subplots(subplot_info, self._settings)
        self._axis_panel.set_canvas_ranges(self._canvas_ranges)

    def _get_subplot_info(self) -> list:
        """Return [(key, display_name), ...] for all subplots."""
        st = self._state
        info = []
        if st.layout_mode == "vs_profile":
            info.append(("vs_profile", st.subplot_names.get("vs_profile", "Vs Profile")))
        elif st.layout_mode == "split_wave":
            info.append(("rayleigh", st.subplot_names.get("rayleigh", "Rayleigh")))
            info.append(("love", st.subplot_names.get("love", "Love")))
        elif st.layout_mode == "grid":
            for r in range(st.grid_rows):
                for c in range(st.grid_cols):
                    key = f"cell_{r}_{c}"
                    name = st.subplot_names.get(key, key)
                    info.append((key, name))
        else:
            info.append(("main", st.subplot_names.get("main", "Main")))
        return info

    def _auto_configure_axes(self):
        """Set axis defaults from subplot types and canvas ranges."""
        st = self._state
        for key, _ in self._get_subplot_info():
            acfg = self._settings.axis_for(key)
            cell_type = st.subplot_types.get(key, "dc")
            if cell_type == "vs_profile" or key == "vs_profile":
                acfg.invert_y = True
                acfg.x_scale = "linear"
                acfg.y_scale = "linear"
            else:
                acfg.x_scale = "log"

            # Transfer canvas axis ranges if available
            if key in self._canvas_ranges:
                (xmin, xmax), (ymin, ymax) = self._canvas_ranges[key]
                acfg.auto_x = False
                acfg.auto_y = False
                acfg.x_min = xmin
                acfg.x_max = xmax
                acfg.y_min = ymin
                acfg.y_max = ymax

    # ── Rendering ─────────────────────────────────────────────────

    PREVIEW_DPI = 100

    def _schedule_render(self):
        """Schedule a debounced re-render."""
        if not self._is_rendering:
            self._render_timer.start()

    def _do_render(self):
        """Render preview at exact configured figsize.

        The canvas widget is set to the exact pixel size corresponding
        to the configured figure dimensions at screen DPI. This ensures
        the preview shows the identical layout, margins, and font
        proportions as the final export.
        """
        self._is_rendering = True
        self._status.showMessage("Rendering...")
        QApplication.processEvents()
        try:
            self._collect_settings()
            w = self._settings.figure.width
            h = self._settings.figure.height
            w_px = max(int(w * self.PREVIEW_DPI), 200)
            h_px = max(int(h * self.PREVIEW_DPI), 150)

            # Size the canvas to match the exact figure dimensions
            self._canvas.setFixedSize(w_px, h_px)
            self._figure.set_dpi(self.PREVIEW_DPI)

            self._renderer.render(self._state, self._settings, self._figure)
            self._canvas.draw_idle()
            self._status.showMessage("Ready", 3000)
        except Exception as e:
            self._status.showMessage(f"Render error: {e}")
            traceback.print_exc()
        finally:
            self._is_rendering = False

    def _collect_settings(self):
        """Read all panel values into self._settings."""
        self._figure_panel.write_to(self._settings.figure)
        self._figure_panel.write_vs_to(self._settings)
        self._typography_panel.write_to(self._settings.typography)
        self._axis_panel.sync_all()
        self._legend_panel.write_to(self._settings.legend)

    # ── Presets ────────────────────────────────────────────────────

    def _apply_preset(self, name: str):
        """Apply a named preset and update all panels."""
        apply_preset(self._settings, name)
        self._figure_panel.read_from(self._settings.figure)
        self._typography_panel.read_from(self._settings.typography)
        self._legend_panel.read_from(self._settings.legend)
        self._auto_configure_axes()
        subplot_info = self._get_subplot_info()
        self._axis_panel.set_subplots(subplot_info, self._settings)
        self._schedule_render()
        self._status.showMessage(f"Applied preset: {get_preset_label(name)}", 3000)

    def _on_axis_label_toggled(self, subplot_key: str, axis_id: str,
                                visible: bool):
        """Handle axis label toggle from layers panel."""
        acfg = self._settings.axis_for(subplot_key)
        if axis_id == "x":
            acfg.show_x_label = visible
        elif axis_id == "y":
            acfg.show_y_label = visible
        self._schedule_render()

    def _on_use_view_limits(self, subplot_key: str):
        """Read current matplotlib axes limits and push to axis panel."""
        axes_map = getattr(self._renderer, '_axes_map', {})
        ax = axes_map.get(subplot_key)
        if ax is None:
            return
        xlim = ax.get_xlim()
        ylim = ax.get_ylim()
        self._axis_panel.apply_view_limits(xlim, ylim)

    def _reset_settings(self):
        """Reset all settings to defaults."""
        self._settings = StudioSettings()
        self._apply_preset("publication")

    # ── Export ─────────────────────────────────────────────────────

    def _do_export(self, path: str, options: dict):
        """Export current figure to file at exact configured size + DPI."""
        try:
            self._collect_settings()
            export_dpi = options.get("dpi", self._settings.figure.dpi)
            export_fig = Figure(
                figsize=(self._settings.figure.width,
                         self._settings.figure.height),
                dpi=export_dpi,
                facecolor=options.get("facecolor", "white"),
            )
            self._renderer.render(
                self._state, self._settings, export_fig
            )
            export_fig.savefig(
                path,
                dpi=export_dpi,
                transparent=options.get("transparent", False),
                bbox_inches=options.get("bbox_inches", "tight"),
                pad_inches=options.get("pad_inches", 0.1),
                facecolor=options.get("facecolor", "white"),
            )
            self._export_panel.set_status(f"Exported: {os.path.basename(path)}")
            self._status.showMessage(f"Exported to {path}", 5000)
        except Exception as e:
            self._export_panel.set_status(f"Error: {e}")
            QMessageBox.warning(self, "Export Error", str(e))

    def _do_batch_export(self, directory: str, options: dict):
        """Export to all formats in a directory."""
        base_name = self._sheet_name.replace(" ", "_").lower()
        formats = ["png", "pdf", "svg", "eps"]
        exported = []
        for fmt in formats:
            path = os.path.join(directory, f"{base_name}.{fmt}")
            opts = dict(options)
            opts["format"] = fmt
            if fmt != "png":
                opts["transparent"] = False
            try:
                export_dpi = opts.get("dpi", self._settings.figure.dpi)
                export_fig = Figure(
                    figsize=(self._settings.figure.width,
                             self._settings.figure.height),
                    dpi=export_dpi,
                    facecolor=opts.get("facecolor", "white"),
                )
                self._renderer.render(
                    self._state, self._settings, export_fig
                )
                export_fig.savefig(
                    path, dpi=export_dpi,
                    transparent=opts.get("transparent", False),
                    bbox_inches=opts.get("bbox_inches", "tight"),
                    pad_inches=opts.get("pad_inches", 0.1),
                    facecolor=opts.get("facecolor", "white"),
                )
                exported.append(fmt.upper())
            except Exception as e:
                self._status.showMessage(f"Error exporting {fmt}: {e}")
        msg = f"Batch export: {', '.join(exported)}"
        self._export_panel.set_status(msg)
        self._status.showMessage(msg, 5000)

