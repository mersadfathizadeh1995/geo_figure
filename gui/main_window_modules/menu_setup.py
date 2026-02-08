"""Menu bar and toolbar construction."""
from PySide6.QtCore import Qt, QSettings, QSize
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import QToolBar


class MenuSetupMixin:
    """Creates menu bar and toolbar for the main window."""

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

        project_action = file_menu.addAction("&Project Directory...")
        project_action.triggered.connect(self._on_change_project)

        settings_action = file_menu.addAction("&Settings...")
        settings_action.triggered.connect(self._on_settings)

        file_menu.addSeparator()

        export_csv_action = file_menu.addAction("Export Data as &CSV...")
        export_csv_action.triggered.connect(self._on_export_csv)

        file_menu.addSeparator()

        exit_action = file_menu.addAction("E&xit")
        exit_action.setShortcut(QKeySequence("Alt+F4"))
        exit_action.triggered.connect(self.close)

        # Edit menu
        edit_menu = menubar.addMenu("&Edit")

        fit_action = edit_menu.addAction("&Fit to Data")
        fit_action.setShortcut(QKeySequence("Ctrl+0"))
        fit_action.triggered.connect(self._on_fit_to_data)

        new_sheet = edit_menu.addAction("&New Sheet")
        new_sheet.setShortcut(QKeySequence("Ctrl+T"))
        new_sheet.triggered.connect(self._on_new_sheet)

        edit_menu.addSeparator()

        # Layout submenu
        layout_menu = edit_menu.addMenu("Plot Layout")
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

        # View menu
        view_menu = menubar.addMenu("&View")
        view_menu.addAction(self.curve_dock.toggleViewAction())
        view_menu.addAction(self.props_dock.toggleViewAction())
        view_menu.addAction(self.sheet_dock.toggleViewAction())
        view_menu.addAction(self.log_dock.toggleViewAction())
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
        dc_template = analysis_menu.addAction("New DC Compare Sheet")
        dc_template.triggered.connect(self._on_new_dc_compare_sheet)
        analysis_menu.addSeparator()
        misfit_action = analysis_menu.addAction("Compute Misfit Residual...")
        misfit_action.triggered.connect(self._on_compute_misfit)
        analysis_menu.addSeparator()
        vs_profile_action = analysis_menu.addAction("Extract Vs Profile...")
        vs_profile_action.triggered.connect(self._on_vs_profile)
        analysis_menu.addSeparator()
        studio_action = analysis_menu.addAction("Render to Matplotlib...")
        studio_action.setShortcut("Ctrl+M")
        studio_action.triggered.connect(self._on_open_studio)

        # Help menu
        help_menu = menubar.addMenu("&Help")
        about = help_menu.addAction("&About")
        about.triggered.connect(self._on_about)

    def _setup_toolbar(self):
        toolbar = QToolBar("Main Toolbar")
        toolbar.setObjectName("toolbar_main")
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

        vs_act = toolbar.addAction("Vs Profile")
        vs_act.setToolTip("Extract Vs profiles from .report")
        vs_act.triggered.connect(self._on_vs_profile)

        toolbar.addSeparator()

        fit_act = toolbar.addAction("Fit")
        fit_act.setToolTip("Fit view to data (Ctrl+0)")
        fit_act.triggered.connect(self._on_fit_to_data)

        new_tab = toolbar.addAction("New Sheet")
        new_tab.setToolTip("Add new sheet (Ctrl+T)")
        new_tab.triggered.connect(self._on_new_sheet)

        toolbar.addSeparator()

        studio_act = toolbar.addAction("Matplotlib")
        studio_act.setToolTip("Render current sheet in Matplotlib Studio (Ctrl+M)")
        studio_act.triggered.connect(self._on_open_studio)
