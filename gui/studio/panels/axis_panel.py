"""Per-subplot axis settings panel — limits, scale, ticks, grid."""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout, QDoubleSpinBox, QComboBox,
    QCheckBox, QLabel, QGroupBox, QHBoxLayout,
)
from PySide6.QtCore import Signal
from geo_figure.gui.studio.models import AxisConfig, GridConfig, TickConfig


class AxisPanel(QWidget):
    """Per-subplot axis configuration controls."""

    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(6)

        # -- Subplot selector --
        sel_grp = QGroupBox("Subplot")
        sel_form = QFormLayout(sel_grp)
        self.subplot_combo = QComboBox()
        self.subplot_combo.currentIndexChanged.connect(self._on_subplot_changed)
        sel_form.addRow("Subplot:", self.subplot_combo)
        layout.addWidget(sel_grp)

        # -- Limits group --
        limits_grp = QGroupBox("Axis Limits")
        limits_form = QFormLayout(limits_grp)
        limits_form.setSpacing(4)

        self.auto_x = QCheckBox("Auto X")
        self.auto_x.setChecked(True)
        self.auto_y = QCheckBox("Auto Y")
        self.auto_y.setChecked(True)
        limits_form.addRow(self.auto_x)
        limits_form.addRow(self.auto_y)

        self.x_min = self._limit_spin(0.0)
        self.x_max = self._limit_spin(100.0)
        row_x = QHBoxLayout()
        row_x.addWidget(QLabel("X:"))
        row_x.addWidget(self.x_min)
        row_x.addWidget(QLabel("-"))
        row_x.addWidget(self.x_max)
        limits_form.addRow(row_x)

        self.y_min = self._limit_spin(0.0)
        self.y_max = self._limit_spin(1000.0)
        row_y = QHBoxLayout()
        row_y.addWidget(QLabel("Y:"))
        row_y.addWidget(self.y_min)
        row_y.addWidget(QLabel("-"))
        row_y.addWidget(self.y_max)
        limits_form.addRow(row_y)

        layout.addWidget(limits_grp)

        # -- Scale group --
        scale_grp = QGroupBox("Scale")
        scale_form = QFormLayout(scale_grp)
        scale_form.setSpacing(4)

        self.x_scale = QComboBox()
        self.x_scale.addItems(["linear", "log"])
        scale_form.addRow("X Scale:", self.x_scale)

        self.y_scale = QComboBox()
        self.y_scale.addItems(["linear", "log"])
        scale_form.addRow("Y Scale:", self.y_scale)

        self.invert_y = QCheckBox("Invert Y (depth)")
        scale_form.addRow(self.invert_y)

        layout.addWidget(scale_grp)

        # -- Ticks group --
        tick_grp = QGroupBox("Ticks")
        tick_form = QFormLayout(tick_grp)
        tick_form.setSpacing(4)

        self.tick_dir = QComboBox()
        self.tick_dir.addItems(["in", "out", "inout"])
        tick_form.addRow("Direction:", self.tick_dir)

        self.show_top = QCheckBox("Top")
        self.show_top.setChecked(True)
        self.show_right = QCheckBox("Right")
        self.show_right.setChecked(True)
        self.show_minor = QCheckBox("Minor Ticks")
        self.show_minor.setChecked(True)
        ticks_row = QHBoxLayout()
        ticks_row.addWidget(self.show_top)
        ticks_row.addWidget(self.show_right)
        ticks_row.addWidget(self.show_minor)
        tick_form.addRow(ticks_row)

        layout.addWidget(tick_grp)

        # -- Grid group --
        grid_grp = QGroupBox("Grid")
        grid_form = QFormLayout(grid_grp)
        grid_form.setSpacing(4)

        self.grid_show = QCheckBox("Show Grid")
        self.grid_show.setChecked(True)
        grid_form.addRow(self.grid_show)

        self.grid_which = QComboBox()
        self.grid_which.addItems(["both", "major", "minor"])
        grid_form.addRow("Apply to:", self.grid_which)

        self.grid_style = QComboBox()
        self.grid_style.addItems([":", "-", "--", "-."])
        grid_form.addRow("Style:", self.grid_style)

        self.grid_alpha = QDoubleSpinBox()
        self.grid_alpha.setRange(0.0, 1.0)
        self.grid_alpha.setValue(0.4)
        self.grid_alpha.setSingleStep(0.05)
        grid_form.addRow("Opacity:", self.grid_alpha)

        layout.addWidget(grid_grp)
        layout.addStretch()

        # Connect signals
        for w in (self.auto_x, self.auto_y, self.invert_y,
                  self.show_top, self.show_right, self.show_minor,
                  self.grid_show):
            w.stateChanged.connect(self.changed)
        for w in (self.x_min, self.x_max, self.y_min, self.y_max,
                  self.grid_alpha):
            w.valueChanged.connect(self.changed)
        for w in (self.x_scale, self.y_scale, self.tick_dir,
                  self.grid_which, self.grid_style):
            w.currentIndexChanged.connect(self.changed)

        self._subplot_keys = []
        self._current_key = ""
        self._settings = None

    def _limit_spin(self, default: float) -> QDoubleSpinBox:
        spin = QDoubleSpinBox()
        spin.setRange(-1e6, 1e6)
        spin.setValue(default)
        spin.setSingleStep(10.0)
        spin.setDecimals(2)
        return spin

    def set_subplots(self, subplot_info: list, settings):
        """Populate subplot selector. subplot_info = [(key, name), ...]."""
        self._settings = settings
        self._subplot_keys = [k for k, _ in subplot_info]
        self.subplot_combo.blockSignals(True)
        self.subplot_combo.clear()
        for key, name in subplot_info:
            label = name if name else key
            self.subplot_combo.addItem(label, key)
        self.subplot_combo.blockSignals(False)
        if self._subplot_keys:
            self._load_axis_config(self._subplot_keys[0])

    def _on_subplot_changed(self, idx):
        if idx < 0 or not self._settings:
            return
        key = self.subplot_combo.itemData(idx)
        if key:
            self._save_current()
            self._load_axis_config(key)

    def _load_axis_config(self, key: str):
        """Load axis config for a subplot key into the UI."""
        self._current_key = key
        if not self._settings:
            return
        acfg = self._settings.axis_for(key)
        self.blockSignals(True)
        self.auto_x.setChecked(acfg.auto_x)
        self.auto_y.setChecked(acfg.auto_y)
        if acfg.x_min is not None:
            self.x_min.setValue(acfg.x_min)
        if acfg.x_max is not None:
            self.x_max.setValue(acfg.x_max)
        if acfg.y_min is not None:
            self.y_min.setValue(acfg.y_min)
        if acfg.y_max is not None:
            self.y_max.setValue(acfg.y_max)
        idx = self.x_scale.findText(acfg.x_scale)
        if idx >= 0:
            self.x_scale.setCurrentIndex(idx)
        idx = self.y_scale.findText(acfg.y_scale)
        if idx >= 0:
            self.y_scale.setCurrentIndex(idx)
        self.invert_y.setChecked(acfg.invert_y)
        idx = self.tick_dir.findText(acfg.ticks.direction)
        if idx >= 0:
            self.tick_dir.setCurrentIndex(idx)
        self.show_top.setChecked(acfg.ticks.show_top)
        self.show_right.setChecked(acfg.ticks.show_right)
        self.show_minor.setChecked(acfg.ticks.show_minor)
        self.grid_show.setChecked(acfg.grid.show)
        idx = self.grid_which.findText(acfg.grid.which)
        if idx >= 0:
            self.grid_which.setCurrentIndex(idx)
        idx = self.grid_style.findText(acfg.grid.linestyle)
        if idx >= 0:
            self.grid_style.setCurrentIndex(idx)
        self.grid_alpha.setValue(acfg.grid.alpha)
        self.blockSignals(False)

    def _save_current(self):
        """Save current UI values to the current subplot's AxisConfig."""
        if not self._current_key or not self._settings:
            return
        self.write_to(self._settings.axis_for(self._current_key))

    def write_to(self, acfg: AxisConfig):
        """Write current UI values into an AxisConfig."""
        acfg.auto_x = self.auto_x.isChecked()
        acfg.auto_y = self.auto_y.isChecked()
        acfg.x_min = self.x_min.value()
        acfg.x_max = self.x_max.value()
        acfg.y_min = self.y_min.value()
        acfg.y_max = self.y_max.value()
        acfg.x_scale = self.x_scale.currentText()
        acfg.y_scale = self.y_scale.currentText()
        acfg.invert_y = self.invert_y.isChecked()
        acfg.ticks.direction = self.tick_dir.currentText()
        acfg.ticks.show_top = self.show_top.isChecked()
        acfg.ticks.show_right = self.show_right.isChecked()
        acfg.ticks.show_minor = self.show_minor.isChecked()
        acfg.grid.show = self.grid_show.isChecked()
        acfg.grid.which = self.grid_which.currentText()
        acfg.grid.linestyle = self.grid_style.currentText()
        acfg.grid.alpha = self.grid_alpha.value()

    def sync_all(self):
        """Save the currently shown axis config."""
        self._save_current()
