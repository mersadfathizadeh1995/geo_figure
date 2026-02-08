"""Typography settings panel — fonts, sizes, weights, presets."""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout, QDoubleSpinBox, QComboBox,
    QCheckBox, QLabel, QGroupBox, QHBoxLayout, QPushButton,
)
from PySide6.QtCore import Signal

from geo_figure.gui.studio.presets import get_preset_names, get_preset_label

# Font families commonly available across platforms
FONT_FAMILIES = [
    "Times New Roman", "Arial", "Helvetica", "DejaVu Sans",
    "DejaVu Serif", "Calibri", "Cambria", "Georgia",
    "Verdana", "Tahoma", "Segoe UI", "Courier New",
]


class TypographyPanel(QWidget):
    """Controls for font family, sizes, weights, and presets."""

    changed = Signal()
    preset_requested = Signal(str)  # preset name

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(6)

        # -- Font group --
        font_grp = QGroupBox("Font")
        font_form = QFormLayout(font_grp)
        font_form.setSpacing(4)

        self.family_combo = QComboBox()
        self.family_combo.addItems(FONT_FAMILIES)
        self.family_combo.setEditable(True)
        font_form.addRow("Family:", self.family_combo)

        self.bold_check = QCheckBox("Bold")
        font_form.addRow("Weight:", self.bold_check)

        layout.addWidget(font_grp)

        # -- Sizes group --
        sizes_grp = QGroupBox("Font Sizes (pt)")
        sizes_form = QFormLayout(sizes_grp)
        sizes_form.setSpacing(4)

        self.title_size = self._size_spin(14.0)
        sizes_form.addRow("Title:", self.title_size)
        self.label_size = self._size_spin(11.0)
        sizes_form.addRow("Axis Labels:", self.label_size)
        self.tick_size = self._size_spin(10.0)
        sizes_form.addRow("Tick Labels:", self.tick_size)
        self.legend_size = self._size_spin(9.0)
        sizes_form.addRow("Legend:", self.legend_size)
        self.annotation_size = self._size_spin(9.0)
        sizes_form.addRow("Annotations:", self.annotation_size)

        layout.addWidget(sizes_grp)

        # -- Presets group --
        presets_grp = QGroupBox("Presets")
        presets_layout = QVBoxLayout(presets_grp)
        presets_layout.setSpacing(4)

        btn_row = QHBoxLayout()
        for name in get_preset_names():
            btn = QPushButton(get_preset_label(name))
            btn.setToolTip(f"Apply {get_preset_label(name)} preset")
            btn.clicked.connect(lambda checked, n=name: self.preset_requested.emit(n))
            btn_row.addWidget(btn)
        presets_layout.addLayout(btn_row)

        layout.addWidget(presets_grp)
        layout.addStretch()

        # Connect signals
        self.family_combo.currentTextChanged.connect(self.changed)
        self.bold_check.stateChanged.connect(self.changed)
        for w in (self.title_size, self.label_size, self.tick_size,
                  self.legend_size, self.annotation_size):
            w.valueChanged.connect(self.changed)

    def _size_spin(self, default: float) -> QDoubleSpinBox:
        spin = QDoubleSpinBox()
        spin.setRange(4.0, 48.0)
        spin.setValue(default)
        spin.setSingleStep(0.5)
        spin.setSuffix(" pt")
        return spin

    def write_to(self, cfg):
        """Write current values into a TypographyConfig."""
        cfg.font_family = self.family_combo.currentText()
        cfg.font_weight = "bold" if self.bold_check.isChecked() else "normal"
        cfg.title_size = self.title_size.value()
        cfg.axis_label_size = self.label_size.value()
        cfg.tick_label_size = self.tick_size.value()
        cfg.legend_size = self.legend_size.value()
        cfg.annotation_size = self.annotation_size.value()

    def read_from(self, cfg):
        """Populate controls from a TypographyConfig."""
        self.blockSignals(True)
        idx = self.family_combo.findText(cfg.font_family)
        if idx >= 0:
            self.family_combo.setCurrentIndex(idx)
        else:
            self.family_combo.setEditText(cfg.font_family)
        self.bold_check.setChecked(cfg.font_weight == "bold")
        self.title_size.setValue(cfg.title_size)
        self.label_size.setValue(cfg.axis_label_size)
        self.tick_size.setValue(cfg.tick_label_size)
        self.legend_size.setValue(cfg.legend_size)
        self.annotation_size.setValue(cfg.annotation_size)
        self.blockSignals(False)
