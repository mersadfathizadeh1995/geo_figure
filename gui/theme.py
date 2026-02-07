"""Dark and light themes using QSS stylesheets."""

DARK_THEME = """
QMainWindow {
    background-color: #1e1e1e;
}
QWidget {
    background-color: #252526;
    color: #cccccc;
}
QMenuBar {
    background-color: #333333;
    color: #cccccc;
    border-bottom: 1px solid #444444;
}
QMenuBar::item:selected {
    background-color: #094771;
}
QMenu {
    background-color: #2d2d2d;
    color: #cccccc;
    border: 1px solid #444444;
}
QMenu::item:selected {
    background-color: #094771;
}
QToolBar {
    background-color: #333333;
    border: none;
    spacing: 4px;
    padding: 2px;
}
QToolButton {
    background-color: transparent;
    color: #cccccc;
    border: 1px solid transparent;
    border-radius: 3px;
    padding: 4px 8px;
    font-size: 13px;
}
QToolButton:hover {
    background-color: #3e3e3e;
    border-color: #555555;
}
QToolButton:pressed, QToolButton:checked {
    background-color: #094771;
    border-color: #1177bb;
}
QDockWidget {
    color: #cccccc;
    titlebar-close-icon: none;
    titlebar-normal-icon: none;
}
QDockWidget::title {
    background-color: #2d2d2d;
    padding: 6px;
    border-bottom: 1px solid #444444;
    font-weight: bold;
}
QTreeWidget {
    background-color: #1e1e1e;
    color: #cccccc;
    border: none;
    outline: none;
}
QTreeWidget::item {
    padding: 3px 0px;
}
QTreeWidget::item:selected {
    background-color: #094771;
}
QTreeWidget::item:hover {
    background-color: #2a2d2e;
}
QTreeWidget::indicator:unchecked {
    border: 1px solid #666666;
    background-color: #1e1e1e;
    width: 13px;
    height: 13px;
    border-radius: 2px;
}
QTreeWidget::indicator:checked {
    border: 1px solid #1177bb;
    background-color: #094771;
    width: 13px;
    height: 13px;
    border-radius: 2px;
}
QHeaderView::section {
    background-color: #2d2d2d;
    color: #cccccc;
    padding: 4px;
    border: none;
    border-right: 1px solid #444444;
}
QTabWidget::pane {
    border: 1px solid #444444;
    background-color: #1e1e1e;
}
QTabBar::tab {
    background-color: #2d2d2d;
    color: #999999;
    padding: 6px 16px;
    border: none;
    border-bottom: 2px solid transparent;
}
QTabBar::tab:selected {
    color: #ffffff;
    border-bottom: 2px solid #1177bb;
    background-color: #1e1e1e;
}
QTabBar::tab:hover {
    color: #cccccc;
    background-color: #333333;
}
QScrollBar:vertical {
    background-color: #1e1e1e;
    width: 10px;
}
QScrollBar::handle:vertical {
    background-color: #555555;
    min-height: 20px;
    border-radius: 5px;
}
QScrollBar::handle:vertical:hover {
    background-color: #777777;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}
QScrollBar:horizontal {
    background-color: #1e1e1e;
    height: 10px;
}
QScrollBar::handle:horizontal {
    background-color: #555555;
    min-width: 20px;
    border-radius: 5px;
}
QPushButton {
    background-color: #0e639c;
    color: white;
    border: none;
    padding: 5px 16px;
    border-radius: 3px;
    font-size: 12px;
}
QPushButton:hover {
    background-color: #1177bb;
}
QPushButton:pressed {
    background-color: #094771;
}
QPushButton:disabled {
    background-color: #3e3e3e;
    color: #666666;
}
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {
    background-color: #3c3c3c;
    color: #cccccc;
    border: 1px solid #555555;
    border-radius: 3px;
    padding: 4px;
}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {
    border-color: #1177bb;
}
QLabel {
    color: #cccccc;
    background: transparent;
}
QGroupBox {
    color: #cccccc;
    border: 1px solid #444444;
    border-radius: 4px;
    margin-top: 8px;
    padding-top: 16px;
    font-weight: bold;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 4px;
}
QTextEdit, QPlainTextEdit {
    background-color: #1e1e1e;
    color: #cccccc;
    border: none;
    font-family: "Cascadia Code", "Consolas", monospace;
    font-size: 12px;
}
QStatusBar {
    background-color: #007acc;
    color: white;
    font-size: 12px;
}
QSplitter::handle {
    background-color: #444444;
}
QSplitter::handle:horizontal { width: 2px; }
QSplitter::handle:vertical { height: 2px; }
QTableWidget {
    background-color: #1e1e1e;
    color: #cccccc;
    gridline-color: #444444;
    border: 1px solid #444444;
}
QCheckBox {
    color: #cccccc;
    background: transparent;
    spacing: 6px;
}
QCheckBox::indicator:unchecked {
    border: 1px solid #666666;
    background-color: #1e1e1e;
    width: 13px; height: 13px; border-radius: 2px;
}
QCheckBox::indicator:checked {
    border: 1px solid #1177bb;
    background-color: #094771;
    width: 13px; height: 13px; border-radius: 2px;
}
"""

LIGHT_THEME = """
QMainWindow {
    background-color: #f5f5f5;
}
QWidget {
    background-color: #ffffff;
    color: #1e1e1e;
}
QMenuBar {
    background-color: #f0f0f0;
    color: #1e1e1e;
    border-bottom: 1px solid #d0d0d0;
}
QMenuBar::item:selected {
    background-color: #c8ddf0;
}
QMenu {
    background-color: #ffffff;
    color: #1e1e1e;
    border: 1px solid #d0d0d0;
}
QMenu::item:selected {
    background-color: #c8ddf0;
}
QToolBar {
    background-color: #f0f0f0;
    border: none;
    spacing: 4px;
    padding: 2px;
}
QToolButton {
    background-color: transparent;
    color: #1e1e1e;
    border: 1px solid transparent;
    border-radius: 3px;
    padding: 4px 8px;
    font-size: 13px;
}
QToolButton:hover {
    background-color: #e0e0e0;
    border-color: #c0c0c0;
}
QToolButton:pressed, QToolButton:checked {
    background-color: #c8ddf0;
    border-color: #0078d4;
}
QDockWidget {
    color: #1e1e1e;
    titlebar-close-icon: none;
    titlebar-normal-icon: none;
}
QDockWidget::title {
    background-color: #f0f0f0;
    padding: 6px;
    border-bottom: 1px solid #d0d0d0;
    font-weight: bold;
}
QTreeWidget {
    background-color: #ffffff;
    color: #1e1e1e;
    border: none;
    outline: none;
}
QTreeWidget::item {
    padding: 3px 0px;
}
QTreeWidget::item:selected {
    background-color: #c8ddf0;
    color: #1e1e1e;
}
QTreeWidget::item:hover {
    background-color: #e8e8e8;
}
QTreeWidget::indicator:unchecked {
    border: 1px solid #999999;
    background-color: #ffffff;
    width: 13px; height: 13px; border-radius: 2px;
}
QTreeWidget::indicator:checked {
    border: 1px solid #0078d4;
    background-color: #0078d4;
    width: 13px; height: 13px; border-radius: 2px;
}
QHeaderView::section {
    background-color: #f0f0f0;
    color: #1e1e1e;
    padding: 4px;
    border: none;
    border-right: 1px solid #d0d0d0;
}
QTabWidget::pane {
    border: 1px solid #d0d0d0;
    background-color: #ffffff;
}
QTabBar::tab {
    background-color: #f0f0f0;
    color: #666666;
    padding: 6px 16px;
    border: none;
    border-bottom: 2px solid transparent;
}
QTabBar::tab:selected {
    color: #1e1e1e;
    border-bottom: 2px solid #0078d4;
    background-color: #ffffff;
}
QTabBar::tab:hover {
    color: #333333;
    background-color: #e0e0e0;
}
QScrollBar:vertical {
    background-color: #f5f5f5;
    width: 10px;
}
QScrollBar::handle:vertical {
    background-color: #c0c0c0;
    min-height: 20px;
    border-radius: 5px;
}
QScrollBar::handle:vertical:hover {
    background-color: #a0a0a0;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}
QScrollBar:horizontal {
    background-color: #f5f5f5;
    height: 10px;
}
QScrollBar::handle:horizontal {
    background-color: #c0c0c0;
    min-width: 20px;
    border-radius: 5px;
}
QPushButton {
    background-color: #0078d4;
    color: white;
    border: none;
    padding: 5px 16px;
    border-radius: 3px;
    font-size: 12px;
}
QPushButton:hover {
    background-color: #1a8ae8;
}
QPushButton:pressed {
    background-color: #005a9e;
}
QPushButton:disabled {
    background-color: #e0e0e0;
    color: #999999;
}
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {
    background-color: #ffffff;
    color: #1e1e1e;
    border: 1px solid #c0c0c0;
    border-radius: 3px;
    padding: 4px;
}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {
    border-color: #0078d4;
}
QComboBox::drop-down {
    border: none;
}
QLabel {
    color: #1e1e1e;
    background: transparent;
}
QGroupBox {
    color: #1e1e1e;
    border: 1px solid #d0d0d0;
    border-radius: 4px;
    margin-top: 8px;
    padding-top: 16px;
    font-weight: bold;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 4px;
}
QTextEdit, QPlainTextEdit {
    background-color: #ffffff;
    color: #1e1e1e;
    border: none;
    font-family: "Cascadia Code", "Consolas", monospace;
    font-size: 12px;
}
QStatusBar {
    background-color: #0078d4;
    color: white;
    font-size: 12px;
}
QSplitter::handle {
    background-color: #d0d0d0;
}
QSplitter::handle:horizontal { width: 2px; }
QSplitter::handle:vertical { height: 2px; }
QTableWidget {
    background-color: #ffffff;
    color: #1e1e1e;
    gridline-color: #d0d0d0;
    border: 1px solid #d0d0d0;
}
QCheckBox {
    color: #1e1e1e;
    background: transparent;
    spacing: 6px;
}
QCheckBox::indicator:unchecked {
    border: 1px solid #999999;
    background-color: #ffffff;
    width: 13px; height: 13px; border-radius: 2px;
}
QCheckBox::indicator:checked {
    border: 1px solid #0078d4;
    background-color: #0078d4;
    width: 13px; height: 13px; border-radius: 2px;
}
"""

# PyQtGraph color presets per theme
PYQTGRAPH_DARK = {'background': '#1e1e1e', 'foreground': '#cccccc'}
PYQTGRAPH_LIGHT = {'background': '#ffffff', 'foreground': '#1e1e1e'}


def apply_theme(app, theme_name: str = "light"):
    """Apply a theme to the application."""
    import pyqtgraph as pg
    if theme_name == "dark":
        app.setStyleSheet(DARK_THEME)
        pg.setConfigOptions(**PYQTGRAPH_DARK, antialias=True)
    else:
        app.setStyleSheet(LIGHT_THEME)
        pg.setConfigOptions(**PYQTGRAPH_LIGHT, antialias=True)
