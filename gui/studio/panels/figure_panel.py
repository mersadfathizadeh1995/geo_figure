"""Figure settings panel — size, DPI, margins, spacing."""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout, QDoubleSpinBox, QSpinBox,
    QCheckBox, QLabel, QGroupBox,
)
from PySide6.QtCore import Signal


class FigurePanel(QWidget):
    """Controls for figure dimensions and layout spacing."""

    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(6)

        # -- Size group --
        size_grp = QGroupBox("Figure Size")
        size_form = QFormLayout(size_grp)
        size_form.setSpacing(4)

        self.width_spin = QDoubleSpinBox()
        self.width_spin.setRange(2.0, 24.0)
        self.width_spin.setValue(6.5)
        self.width_spin.setSingleStep(0.5)
        self.width_spin.setSuffix(" in")
        size_form.addRow("Width:", self.width_spin)

        self.height_spin = QDoubleSpinBox()
        self.height_spin.setRange(2.0, 24.0)
        self.height_spin.setValue(5.0)
        self.height_spin.setSingleStep(0.5)
        self.height_spin.setSuffix(" in")
        size_form.addRow("Height:", self.height_spin)

        self.dpi_spin = QSpinBox()
        self.dpi_spin.setRange(72, 1200)
        self.dpi_spin.setValue(300)
        self.dpi_spin.setSingleStep(50)
        size_form.addRow("DPI:", self.dpi_spin)

        layout.addWidget(size_grp)

        # -- Margins group --
        margin_grp = QGroupBox("Margins (inches)")
        margin_form = QFormLayout(margin_grp)
        margin_form.setSpacing(4)

        self.margin_left = self._margin_spin(0.70)
        margin_form.addRow("Left:", self.margin_left)
        self.margin_right = self._margin_spin(0.25)
        margin_form.addRow("Right:", self.margin_right)
        self.margin_top = self._margin_spin(0.50)
        margin_form.addRow("Top:", self.margin_top)
        self.margin_bottom = self._margin_spin(0.55)
        margin_form.addRow("Bottom:", self.margin_bottom)

        layout.addWidget(margin_grp)

        # -- Spacing group --
        spacing_grp = QGroupBox("Subplot Spacing (inches)")
        spacing_form = QFormLayout(spacing_grp)
        spacing_form.setSpacing(4)

        self.hspace_spin = self._margin_spin(0.40)
        spacing_form.addRow("Horizontal:", self.hspace_spin)
        self.vspace_spin = self._margin_spin(0.40)
        spacing_form.addRow("Vertical:", self.vspace_spin)

        self.tight_check = QCheckBox("Tight Layout")
        spacing_form.addRow(self.tight_check)

        layout.addWidget(spacing_grp)
        layout.addStretch()

        # Connect all signals
        for w in (
            self.width_spin, self.height_spin, self.dpi_spin,
            self.margin_left, self.margin_right,
            self.margin_top, self.margin_bottom,
            self.hspace_spin, self.vspace_spin,
        ):
            w.valueChanged.connect(self.changed)
        self.tight_check.stateChanged.connect(self.changed)

    def _margin_spin(self, default: float) -> QDoubleSpinBox:
        spin = QDoubleSpinBox()
        spin.setRange(0.0, 3.0)
        spin.setValue(default)
        spin.setSingleStep(0.05)
        spin.setSuffix(" in")
        return spin

    def write_to(self, cfg):
        """Write current values into a FigureConfig."""
        cfg.width = self.width_spin.value()
        cfg.height = self.height_spin.value()
        cfg.dpi = self.dpi_spin.value()
        cfg.margin_left = self.margin_left.value()
        cfg.margin_right = self.margin_right.value()
        cfg.margin_top = self.margin_top.value()
        cfg.margin_bottom = self.margin_bottom.value()
        cfg.hspace = self.hspace_spin.value()
        cfg.vspace = self.vspace_spin.value()
        cfg.tight_layout = self.tight_check.isChecked()

    def read_from(self, cfg):
        """Populate controls from a FigureConfig."""
        self.blockSignals(True)
        self.width_spin.setValue(cfg.width)
        self.height_spin.setValue(cfg.height)
        self.dpi_spin.setValue(cfg.dpi)
        self.margin_left.setValue(cfg.margin_left)
        self.margin_right.setValue(cfg.margin_right)
        self.margin_top.setValue(cfg.margin_top)
        self.margin_bottom.setValue(cfg.margin_bottom)
        self.hspace_spin.setValue(cfg.hspace)
        self.vspace_spin.setValue(cfg.vspace)
        self.tight_check.setChecked(cfg.tight_layout)
        self.blockSignals(False)
