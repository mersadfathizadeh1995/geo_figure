"""Tab management for multiple plot sheets."""
from PySide6.QtWidgets import QTabWidget, QWidget, QVBoxLayout, QMenu, QTabBar, QInputDialog
from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QAction
from typing import Dict
from geo_figure.gui.canvas.plot_canvas import PlotCanvas


class SheetTabs(QTabWidget):
    """Manages multiple plot canvas sheets as tabs."""

    sheet_changed = Signal(str)  # sheet name
    duplicate_requested = Signal(int)  # tab index
    units_requested = Signal(int)  # tab index

    def __init__(self, parent=None):
        super().__init__(parent)
        self._sheets: Dict[str, PlotCanvas] = {}
        self.setTabsClosable(True)
        self.setMovable(True)
        self.tabCloseRequested.connect(self._on_tab_close)
        self.currentChanged.connect(self._on_current_changed)
        # Tab bar context menu
        self.tabBar().setContextMenuPolicy(Qt.CustomContextMenu)
        self.tabBar().customContextMenuRequested.connect(self._on_tab_context_menu)
        # Double-click to rename
        self.tabBar().setTabsClosable(True)
        self.tabBarDoubleClicked.connect(self._on_tab_double_clicked)

        # Create default sheet
        self.add_sheet("DC Compare")

    def add_sheet(self, name: str) -> PlotCanvas:
        """Add a new sheet tab with a plot canvas."""
        canvas = PlotCanvas()
        self._sheets[name] = canvas
        self.addTab(canvas, name)
        self.setCurrentWidget(canvas)
        return canvas

    def get_current_canvas(self) -> PlotCanvas:
        """Get the currently active canvas."""
        widget = self.currentWidget()
        if isinstance(widget, PlotCanvas):
            return widget
        # Fallback: create one
        return self.add_sheet("Sheet 1")

    def get_canvas(self, name: str) -> PlotCanvas:
        """Get canvas by sheet name."""
        return self._sheets.get(name)

    def _on_tab_close(self, index: int):
        """Handle tab close. Keep at least one tab."""
        if self.count() <= 1:
            return
        widget = self.widget(index)
        for name, canvas in self._sheets.items():
            if canvas is widget:
                del self._sheets[name]
                break
        self.removeTab(index)

    def _on_current_changed(self, index: int):
        widget = self.widget(index)
        for name, canvas in self._sheets.items():
            if canvas is widget:
                self.sheet_changed.emit(name)
                break

    def _on_tab_context_menu(self, pos):
        """Right-click on a tab: rename, duplicate, set units."""
        index = self.tabBar().tabAt(pos)
        if index < 0:
            return
        menu = QMenu(self)
        rename_action = menu.addAction("Rename Sheet...")
        rename_action.triggered.connect(lambda: self._rename_tab(index))
        dup_action = menu.addAction("Duplicate Sheet")
        dup_action.triggered.connect(lambda: self.duplicate_requested.emit(index))
        menu.addSeparator()
        units_action = menu.addAction("Set Velocity Units...")
        units_action.triggered.connect(lambda: self.units_requested.emit(index))
        menu.exec(self.tabBar().mapToGlobal(pos))

    def _on_tab_double_clicked(self, index: int):
        """Double-click on a tab to rename it."""
        if index >= 0:
            self._rename_tab(index)

    def _rename_tab(self, index: int):
        """Prompt user to rename a tab."""
        old_name = self.tabText(index)
        new_name, ok = QInputDialog.getText(
            self, "Rename Sheet", "New name:", text=old_name
        )
        if ok and new_name.strip():
            new_name = new_name.strip()
            # Update internal _sheets dict key
            widget = self.widget(index)
            for key, canvas in list(self._sheets.items()):
                if canvas is widget:
                    del self._sheets[key]
                    self._sheets[new_name] = canvas
                    break
            self.setTabText(index, new_name)
