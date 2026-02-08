"""Legend settings panel — position, frame, columns, size."""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout, QDoubleSpinBox, QSpinBox,
    QComboBox, QCheckBox, QGroupBox,
)
from PySide6.QtCore import Signal


LEGEND_LOCATIONS = [
    "upper right", "upper left", "lower left", "lower right",
    "right", "center left", "center right",
    "lower center", "upper center", "center", "best",
]


class LegendPanel(QWidget):
    """Controls for legend appearance and positioning."""

    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(6)

        grp = QGroupBox("Legend")
        form = QFormLayout(grp)
        form.setSpacing(4)

        self.show_check = QCheckBox("Show Legend")
        self.show_check.setChecked(True)
        form.addRow(self.show_check)

        self.location_combo = QComboBox()
        self.location_combo.addItems(LEGEND_LOCATIONS)
        form.addRow("Position:", self.location_combo)

        self.outside_check = QCheckBox("Place Outside Plot")
        form.addRow(self.outside_check)

        self.ncol_spin = QSpinBox()
        self.ncol_spin.setRange(1, 6)
        self.ncol_spin.setValue(1)
        form.addRow("Columns:", self.ncol_spin)

        self.fontsize_spin = QDoubleSpinBox()
        self.fontsize_spin.setRange(4.0, 30.0)
        self.fontsize_spin.setValue(9.0)
        self.fontsize_spin.setSingleStep(0.5)
        self.fontsize_spin.setSuffix(" pt")
        form.addRow("Font Size:", self.fontsize_spin)

        self.frame_check = QCheckBox("Frame")
        self.frame_check.setChecked(True)
        form.addRow(self.frame_check)

        self.frame_alpha = QDoubleSpinBox()
        self.frame_alpha.setRange(0.0, 1.0)
        self.frame_alpha.setValue(0.9)
        self.frame_alpha.setSingleStep(0.05)
        form.addRow("Frame Opacity:", self.frame_alpha)

        self.shadow_check = QCheckBox("Shadow")
        form.addRow(self.shadow_check)

        layout.addWidget(grp)
        layout.addStretch()

        # Connect signals
        self.show_check.stateChanged.connect(self.changed)
        self.location_combo.currentIndexChanged.connect(self.changed)
        self.outside_check.stateChanged.connect(self.changed)
        self.ncol_spin.valueChanged.connect(self.changed)
        self.fontsize_spin.valueChanged.connect(self.changed)
        self.frame_check.stateChanged.connect(self.changed)
        self.frame_alpha.valueChanged.connect(self.changed)
        self.shadow_check.stateChanged.connect(self.changed)

    def write_to(self, cfg):
        """Write current values into a LegendConfig."""
        cfg.show = self.show_check.isChecked()
        cfg.location = self.location_combo.currentText()
        cfg.outside = self.outside_check.isChecked()
        cfg.ncol = self.ncol_spin.value()
        cfg.fontsize = self.fontsize_spin.value()
        cfg.frame_on = self.frame_check.isChecked()
        cfg.frame_alpha = self.frame_alpha.value()
        cfg.shadow = self.shadow_check.isChecked()

    def read_from(self, cfg):
        """Populate controls from a LegendConfig."""
        self.blockSignals(True)
        self.show_check.setChecked(cfg.show)
        idx = self.location_combo.findText(cfg.location)
        if idx >= 0:
            self.location_combo.setCurrentIndex(idx)
        self.outside_check.setChecked(cfg.outside)
        self.ncol_spin.setValue(cfg.ncol)
        self.fontsize_spin.setValue(cfg.fontsize or 9.0)
        self.frame_check.setChecked(cfg.frame_on)
        self.frame_alpha.setValue(cfg.frame_alpha)
        self.shadow_check.setChecked(cfg.shadow)
        self.blockSignals(False)
