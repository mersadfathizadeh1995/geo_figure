"""Application entry point."""
import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("GeoFigure")
    app.setOrganizationName("GeoFigure")
    app.setApplicationVersion("0.1.0")

    # Default font
    font = QFont("Segoe UI", 9)
    app.setFont(font)

    # Import here to avoid circular
    from geo_figure.gui.main_window import MainWindow
    from geo_figure.gui.theme import apply_theme
    from geo_figure.gui.dialogs.project_dialog import ProjectDialog

    # Load saved theme preference, default to light
    from PySide6.QtCore import QSettings
    settings = QSettings("GeoFigure", "GeoFigure")
    theme_name = settings.value("theme", "light")
    apply_theme(app, theme_name)

    # Show project setup dialog
    dlg = ProjectDialog()
    if dlg.exec():
        project_dir = dlg.get_project_dir()
        project_name = dlg.get_project_name()
    else:
        sys.exit(0)

    window = MainWindow(
        project_dir=project_dir,
        project_name=project_name,
    )
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
