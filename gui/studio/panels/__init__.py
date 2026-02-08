"""Studio control panels."""
from PySide6.QtWidgets import QWidget, QVBoxLayout, QToolButton
from PySide6.QtCore import Qt


class CollapsibleSection(QWidget):
    """Arrow-toggle collapsible section matching the main app style."""

    def __init__(self, title: str, expanded: bool = True, parent=None):
        super().__init__(parent)
        self._toggle = QToolButton()
        self._toggle.setStyleSheet(
            "QToolButton { border: none; font-weight: bold; padding: 2px 0px; }"
        )
        self._toggle.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self._toggle.setArrowType(Qt.DownArrow if expanded else Qt.RightArrow)
        self._toggle.setText(f" {title}")
        self._toggle.setCheckable(True)
        self._toggle.setChecked(expanded)

        self.content = QWidget()
        self.content.setVisible(expanded)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.addWidget(self._toggle)
        lay.addWidget(self.content)
        self._toggle.toggled.connect(self._on_toggle)

    def _on_toggle(self, checked: bool):
        self._toggle.setArrowType(Qt.DownArrow if checked else Qt.RightArrow)
        self.content.setVisible(checked)
