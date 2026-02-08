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
    QToolBar, QStatusBar, QMessageBox, QSplitter, QApplication,
)
from PySide6.QtCore import Qt, QTimer, QSettings
from PySide6.QtGui import QAction, QKeySequence

import matplotlib
matplotlib.use("Agg")  # non-interactive backend, we render to FigureCanvas
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


class StudioWindow(QMainWindow):
    """Matplotlib Studio — renders a sheet's data as a publication figure."""

    def __init__(self, fig_state: FigureState, sheet_name: str = "",
                 parent=None):
        super().__init__(parent)
        self._state = fig_state
        self._sheet_name = sheet_name or "Sheet"
        self._settings = StudioSettings()
        self._renderer = MplRenderer()
        self._render_timer = QTimer(self)
        self._render_timer.setSingleShot(True)
        self._render_timer.setInterval(100)
        self._render_timer.timeout.connect(self._do_render)
        self._is_rendering = False

        self.setWindowTitle(f"Matplotlib Studio - {self._sheet_name}")
        self.resize(1400, 900)

        self._build_ui()
        self._build_menus()
        self._init_panels_from_state()

        # Resize timer for responsive preview
        self._resize_timer = QTimer(self)
        self._resize_timer.setSingleShot(True)
        self._resize_timer.setInterval(200)
        self._resize_timer.timeout.connect(self._do_render)

        # Initial render
        QTimer.singleShot(50, self._do_render)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._resize_timer.start()

    # ── UI construction ───────────────────────────────────────────

    def _build_ui(self):
        """Build the main layout: canvas (left) + settings tabs (right)."""
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(4, 4, 4, 4)
        main_layout.setSpacing(4)

        splitter = QSplitter(Qt.Horizontal)

        # -- Left: matplotlib canvas + toolbar --
        canvas_container = QWidget()
        canvas_layout = QVBoxLayout(canvas_container)
        canvas_layout.setContentsMargins(0, 0, 0, 0)
        canvas_layout.setSpacing(0)

        self._figure = Figure(figsize=(6.5, 5.0), dpi=100,
                              facecolor="white")
        self._canvas = FigureCanvas(self._figure)
        self._canvas.setMinimumSize(300, 200)
        # Let canvas resize freely within its container
        from PySide6.QtWidgets import QSizePolicy
        self._canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._toolbar = NavigationToolbar(self._canvas, self)

        canvas_layout.addWidget(self._toolbar)
        canvas_layout.addWidget(self._canvas, stretch=1)
        splitter.addWidget(canvas_container)

        # -- Right: settings tabs --
        self._tabs = QTabWidget()
        self._tabs.setMinimumWidth(280)
        self._tabs.setMaximumWidth(380)

        self._figure_panel = FigurePanel()
        self._typography_panel = TypographyPanel()
        self._axis_panel = AxisPanel()
        self._legend_panel = LegendPanel()
        self._export_panel = ExportPanel()

        self._tabs.addTab(self._figure_panel, "Figure")
        self._tabs.addTab(self._typography_panel, "Typography")
        self._tabs.addTab(self._axis_panel, "Axis")
        self._tabs.addTab(self._legend_panel, "Legend")
        self._tabs.addTab(self._export_panel, "Export")

        splitter.addWidget(self._tabs)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 0)
        splitter.setSizes([1000, 320])

        main_layout.addWidget(splitter)

        # Status bar
        self._status = QStatusBar()
        self.setStatusBar(self._status)
        self._status.showMessage("Ready")

        # Connect panel signals
        self._figure_panel.changed.connect(self._schedule_render)
        self._typography_panel.changed.connect(self._schedule_render)
        self._axis_panel.changed.connect(self._schedule_render)
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
            lambda: self._tabs.setCurrentWidget(self._export_panel)
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

    def _init_panels_from_state(self):
        """Initialize panel controls from current settings and state."""
        self._figure_panel.read_from(self._settings.figure)
        self._typography_panel.read_from(self._settings.typography)
        self._legend_panel.read_from(self._settings.legend)

        # Populate axis panel with subplot info
        subplot_info = self._get_subplot_info()
        self._axis_panel.set_subplots(subplot_info, self._settings)

        # Auto-configure axis defaults from state
        self._auto_configure_axes()

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
        """Set sensible axis defaults based on subplot types."""
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

    # ── Rendering ─────────────────────────────────────────────────

    def _schedule_render(self):
        """Schedule a debounced re-render."""
        if not self._is_rendering:
            self._render_timer.start()

    def _do_render(self):
        """Execute the render."""
        self._is_rendering = True
        self._status.showMessage("Rendering...")
        QApplication.processEvents()
        try:
            self._collect_settings()
            # For preview, adapt figure size to fit the canvas widget area
            # while preserving the configured aspect ratio
            cw = self._canvas.width()
            ch = self._canvas.height()
            if cw > 0 and ch > 0:
                screen_dpi = self._canvas.physicalDpiX() or 96
                preview_w = cw / screen_dpi
                preview_h = ch / screen_dpi
                # Scale to fit while preserving settings aspect ratio
                cfg = self._settings.figure
                aspect = cfg.height / cfg.width if cfg.width > 0 else 1.0
                if preview_w * aspect <= preview_h:
                    fit_w, fit_h = preview_w, preview_w * aspect
                else:
                    fit_h, fit_w = preview_h, preview_h / aspect
                self._figure.set_size_inches(fit_w, fit_h)
                self._figure.set_dpi(screen_dpi)

            self._renderer.render(
                self._state, self._settings, self._figure, preview=True
            )
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

    def _reset_settings(self):
        """Reset all settings to defaults."""
        self._settings = StudioSettings()
        self._apply_preset("publication")

    # ── Export ─────────────────────────────────────────────────────

    def _do_export(self, path: str, options: dict):
        """Export current figure to file."""
        try:
            self._collect_settings()
            # Create a fresh high-resolution figure for export
            export_fig = Figure(
                figsize=(self._settings.figure.width,
                         self._settings.figure.height),
                dpi=options.get("dpi", 300),
                facecolor=options.get("facecolor", "white"),
            )
            self._renderer.render(self._state, self._settings, export_fig)
            export_fig.savefig(
                path,
                dpi=options.get("dpi", 300),
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
                export_fig = Figure(
                    figsize=(self._settings.figure.width,
                             self._settings.figure.height),
                    dpi=opts.get("dpi", 300),
                    facecolor=opts.get("facecolor", "white"),
                )
                self._renderer.render(self._state, self._settings, export_fig)
                export_fig.savefig(
                    path,
                    dpi=opts.get("dpi", 300),
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
