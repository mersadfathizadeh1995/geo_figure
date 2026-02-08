"""Style section — mixin providing build + populate + handlers."""
from PySide6.QtWidgets import (
    QHBoxLayout, QPushButton, QDoubleSpinBox, QCheckBox, QLabel,
    QColorDialog,
)
from PySide6.QtGui import QColor, QPixmap


class StyleSectionMixin:
    """Builds and manages the Style collapsible section."""

    def _build_style(self, layout):
        self.style_group, _sc, style_layout = self._make_section(
            "Style", expanded=False
        )

        color_row = QHBoxLayout()
        self.color_btn = QPushButton()
        self.color_btn.setFixedSize(28, 28)
        self.color_btn.clicked.connect(self._pick_color)
        color_row.addWidget(self.color_btn)
        self.color_hex = QLabel("#2196F3")
        color_row.addWidget(self.color_hex)
        color_row.addStretch()
        style_layout.addRow("Color:", color_row)

        self.width_spin = QDoubleSpinBox()
        self.width_spin.setRange(0.5, 10.0)
        self.width_spin.setSingleStep(0.5)
        self.width_spin.setValue(1.5)
        self.width_spin.valueChanged.connect(self._on_style_changed)
        style_layout.addRow("Line Width:", self.width_spin)

        self.marker_spin = QDoubleSpinBox()
        self.marker_spin.setRange(1, 20)
        self.marker_spin.setSingleStep(1)
        self.marker_spin.setValue(6)
        self.marker_spin.valueChanged.connect(self._on_style_changed)
        style_layout.addRow("Marker Size:", self.marker_spin)

        self.errbar_cb = QCheckBox("Show Error Bars")
        self.errbar_cb.setChecked(True)
        self.errbar_cb.stateChanged.connect(self._on_style_changed)
        style_layout.addRow(self.errbar_cb)

        self.style_group.setVisible(False)
        layout.addWidget(self.style_group)

    def _populate_style(self, curve):
        """Fill the Style section from a CurveData object."""
        self._update_color_button(curve.color)
        self.width_spin.setValue(curve.line_width)
        self.marker_spin.setValue(curve.marker_size)
        self.errbar_cb.setChecked(curve.show_error_bars)

    def _update_color_button(self, color_str: str):
        pixmap = QPixmap(24, 24)
        pixmap.fill(QColor(color_str))
        self.color_btn.setIcon(pixmap)
        self.color_btn.setStyleSheet(
            f"background-color: {color_str}; border: 1px solid #555555;"
            " border-radius: 3px;"
        )
        self.color_hex.setText(color_str)

    def _pick_color(self):
        if not self._current_curve:
            return
        color = QColorDialog.getColor(
            QColor(self._current_curve.color), self, "Pick Curve Color"
        )
        if color.isValid():
            self._current_curve.color = color.name()
            self._update_color_button(color.name())
            self._emit_update()

    def _on_style_changed(self):
        if self._updating or not self._current_curve:
            return
        self._current_curve.line_width = self.width_spin.value()
        self._current_curve.marker_size = self.marker_spin.value()
        self._current_curve.show_error_bars = self.errbar_cb.isChecked()
        self._emit_update()
