"""Main application window with dockable panels and central canvas.

Refactored version: all handler logic lives in main_window_modules/.
This file contains only __init__, panel/central setup, signal wiring,
and the _add_curve helper.
"""
import os
from pathlib import Path

from PySide6.QtWidgets import QMainWindow, QDockWidget, QStatusBar
from PySide6.QtCore import Qt

from geo_figure.gui.canvas.sheet_tabs import SheetTabs
from geo_figure.gui.panels.curve_tree import CurveTreePanel
from geo_figure.gui.panels.properties_panel import PropertiesPanel
from geo_figure.gui.panels.sheet_panel import SheetPanel
from geo_figure.gui.panels.log_panel import LogPanel
from geo_figure.core.models import CurveData

from geo_figure.gui.main_window_modules import (
    StatePersistenceMixin,
    MenuSetupMixin,
    LayoutActionsMixin,
    FileActionsMixin,
    CurveHandlersMixin,
    EnsembleHandlersMixin,
    SubplotHandlersMixin,
    SheetManagerMixin,
)


class MainWindow(
    StatePersistenceMixin,
    MenuSetupMixin,
    FileActionsMixin,
    CurveHandlersMixin,
    LayoutActionsMixin,
    SubplotHandlersMixin,
    EnsembleHandlersMixin,
    SheetManagerMixin,
    QMainWindow,
):
    """Main application window."""

    def __init__(self, parent=None, project_dir=None, project_name=None):
        super().__init__(parent)
        self.setWindowTitle("GeoFigure -- Geophysical Data Visualization")
        self.setMinimumSize(1100, 700)
        self.resize(1400, 850)

        # Per-sheet data: sheet_index -> {curves, ensembles, selected_uid}
        self._sheet_data = {}
        self._current_sheet_idx = 0

        # Project directory (replaces temp dir)
        if project_dir:
            self._project_dir = Path(project_dir)
            self._project_name = project_name or self._project_dir.name
        else:
            import tempfile
            self._project_dir = Path(tempfile.mkdtemp(prefix="geofigure_"))
            self._project_name = "Untitled"
        # Ensure subdirectories exist
        for sub in ("theoretical", "experimental", "figures", "csv", "session"):
            (self._project_dir / sub).mkdir(parents=True, exist_ok=True)
        # Alias for backward compatibility
        self._temp_dir = str(self._project_dir / "session")

        self._setup_central()
        self._setup_panels()
        self._setup_menubar()
        self._setup_toolbar()
        self._setup_statusbar()
        self._connect_signals()
        self._restore_state()

        # Initialize first sheet data
        self._ensure_sheet_data(0)

        self.setWindowTitle(
            f"GeoFigure -- {self._project_name}"
        )
        self.log_panel.log_info(
            f"Project: {self._project_name} | {self._project_dir}"
        )

    # ── Setup (core) ─────────────────────────────────────────────

    def _setup_central(self):
        """Central widget: tabbed plot canvases."""
        self.sheet_tabs = SheetTabs()
        self.setCentralWidget(self.sheet_tabs)

    def _setup_panels(self):
        """Create dockable side panels."""
        # Left: Data Panel
        self.curve_tree = CurveTreePanel()
        self.curve_dock = QDockWidget("Data", self)
        self.curve_dock.setObjectName("dock_data")
        self.curve_dock.setWidget(self.curve_tree)
        self.curve_dock.setMinimumWidth(200)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.curve_dock)

        # Right: Properties
        self.properties = PropertiesPanel()
        self.props_dock = QDockWidget("Properties", self)
        self.props_dock.setObjectName("dock_properties")
        self.props_dock.setWidget(self.properties)
        self.props_dock.setMinimumWidth(250)
        self.addDockWidget(Qt.RightDockWidgetArea, self.props_dock)

        # Right: Sheet Settings (tabbed with Properties)
        self.sheet_panel = SheetPanel()
        self.sheet_dock = QDockWidget("Sheet", self)
        self.sheet_dock.setObjectName("dock_sheet")
        self.sheet_dock.setWidget(self.sheet_panel)
        self.sheet_dock.setMinimumWidth(250)
        self.addDockWidget(Qt.RightDockWidgetArea, self.sheet_dock)
        self.tabifyDockWidget(self.props_dock, self.sheet_dock)
        # Properties tab should be on top by default
        self.props_dock.raise_()

        # Bottom: Log
        self.log_panel = LogPanel()
        self.log_dock = QDockWidget("Log", self)
        self.log_dock.setObjectName("dock_log")
        self.log_dock.setWidget(self.log_panel)
        self.log_dock.setMaximumHeight(200)
        self.addDockWidget(Qt.BottomDockWidgetArea, self.log_dock)

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
        self.curve_tree.ensemble_subplot_changed.connect(
            self._on_ensemble_subplot_changed
        )
        self.curve_tree.vs_profile_selected.connect(self._on_vs_profile_selected)
        self.curve_tree.vs_profile_layer_toggled.connect(self._on_vs_profile_layer_toggled)
        self.curve_tree.remove_vs_profile_requested.connect(self._on_remove_vs_profile)

        # Properties panel signals
        self.properties.curve_updated.connect(self._on_curve_updated)
        self.properties.subplot_change_requested.connect(
            self._on_curve_subplot_changed
        )
        self.properties.ensemble_updated.connect(self._on_ensemble_updated)
        self.properties.vs_profile_updated.connect(self._on_vs_profile_updated)

        # Sheet panel signals
        self.sheet_panel.legend_changed.connect(self._on_legend_changed)
        self.sheet_panel.sheet_name_changed.connect(self._on_sheet_name_changed)
        self.sheet_panel.col_ratios_changed.connect(self._on_col_ratios_changed)

        # Canvas signals
        canvas = self.sheet_tabs.get_current_canvas()
        canvas.curve_clicked.connect(self._on_curve_selected)
        canvas.layout_changed.connect(self._on_layout_structure_changed)

        # Sheet tab change
        self.sheet_tabs.currentChanged.connect(self._on_sheet_changed)
        self.sheet_tabs.duplicate_requested.connect(self._on_duplicate_sheet)
        self.sheet_tabs.units_requested.connect(self._on_set_units)

    # ── Helpers (core) ───────────────────────────────────────────

    def _add_curve(self, curve: CurveData, canvas):
        """Add a curve to the data store, tree, and canvas."""
        # Assign to the active subplot if the curve has default key
        if curve.subplot_key == "main" and "main" not in canvas._plots:
            curve.subplot_key = canvas.active_subplot
        self._curves[curve.uid] = curve
        self.curve_tree.add_curve(curve)
        canvas.add_curve(curve)
