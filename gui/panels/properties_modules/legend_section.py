"""Legend section — mixin providing build + populate + handlers."""
from PySide6.QtWidgets import QCheckBox, QComboBox, QSpinBox


class LegendSectionMixin:
    """Builds and manages the Legend collapsible section."""

    def _build_legend(self, layout):
        self.legend_group, _lc, legend_layout = self._make_section(
            "Legend", expanded=False
        )

        self.legend_visible_cb = QCheckBox("Show Legend")
        self.legend_visible_cb.setChecked(True)
        self.legend_visible_cb.stateChanged.connect(self._on_legend_changed)
        legend_layout.addRow(self.legend_visible_cb)

        self.legend_pos_combo = QComboBox()
        self.legend_pos_combo.addItems([
            "top-right", "top-left", "bottom-right", "bottom-left"
        ])
        self.legend_pos_combo.currentIndexChanged.connect(self._on_legend_changed)
        legend_layout.addRow("Position:", self.legend_pos_combo)

        self.legend_offset_x = QSpinBox()
        self.legend_offset_x.setRange(-500, 500)
        self.legend_offset_x.setValue(-10)
        self.legend_offset_x.valueChanged.connect(self._on_legend_changed)
        legend_layout.addRow("Offset X:", self.legend_offset_x)

        self.legend_offset_y = QSpinBox()
        self.legend_offset_y.setRange(-500, 500)
        self.legend_offset_y.setValue(10)
        self.legend_offset_y.valueChanged.connect(self._on_legend_changed)
        legend_layout.addRow("Offset Y:", self.legend_offset_y)

        self.legend_font_size = QSpinBox()
        self.legend_font_size.setRange(6, 24)
        self.legend_font_size.setValue(9)
        self.legend_font_size.valueChanged.connect(self._on_legend_changed)
        legend_layout.addRow("Font Size:", self.legend_font_size)

        self.legend_group.setVisible(False)
        layout.addWidget(self.legend_group)

    def set_legend_config(self, config: dict):
        """Populate legend controls from a config dict."""
        self._updating = True
        self.legend_visible_cb.setChecked(config.get("visible", True))
        pos = config.get("position", "top-right")
        idx = self.legend_pos_combo.findText(pos)
        if idx >= 0:
            self.legend_pos_combo.setCurrentIndex(idx)
        offset = config.get("offset", (-10, 10))
        self.legend_offset_x.setValue(offset[0])
        self.legend_offset_y.setValue(offset[1])
        self.legend_font_size.setValue(config.get("font_size", 9))
        self._updating = False

    def _on_legend_changed(self):
        if self._updating:
            return
        config = {
            "visible": self.legend_visible_cb.isChecked(),
            "position": self.legend_pos_combo.currentText(),
            "offset": (
                self.legend_offset_x.value(),
                self.legend_offset_y.value(),
            ),
            "font_size": self.legend_font_size.value(),
        }
        self.legend_changed.emit(config)
