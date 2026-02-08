"""Figure settings panel — size, DPI, margins, spacing."""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout, QDoubleSpinBox, QSpinBox,
    QCheckBox, QLabel, QGroupBox, QComboBox,
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
        spacing_form.addRow("Between Rows:", self.hspace_spin)
        self.vspace_spin = self._margin_spin(0.40)
        spacing_form.addRow("Between Columns:", self.vspace_spin)

        self.tight_check = QCheckBox("Tight Layout")
        spacing_form.addRow(self.tight_check)

        layout.addWidget(spacing_grp)

        # -- Vs Profile layout group (shown only when Vs data present) --
        self._vs_grp = QGroupBox("Vs Profile Layout")
        vs_form = QFormLayout(self._vs_grp)
        vs_form.setSpacing(4)

        self.vs_gap_spin = QDoubleSpinBox()
        self.vs_gap_spin.setRange(0.0, 1.0)
        self.vs_gap_spin.setValue(0.12)
        self.vs_gap_spin.setSingleStep(0.02)
        vs_form.addRow("Vs / Sigma Gap:", self.vs_gap_spin)

        self.vs_ratio_spin = QDoubleSpinBox()
        self.vs_ratio_spin.setRange(1.0, 10.0)
        self.vs_ratio_spin.setValue(3.0)
        self.vs_ratio_spin.setSingleStep(0.5)
        vs_form.addRow("Vs Width Ratio:", self.vs_ratio_spin)

        self.sig_ratio_spin = QDoubleSpinBox()
        self.sig_ratio_spin.setRange(0.5, 5.0)
        self.sig_ratio_spin.setValue(1.0)
        self.sig_ratio_spin.setSingleStep(0.25)
        vs_form.addRow("Sigma Width Ratio:", self.sig_ratio_spin)

        self._vs_grp.setVisible(False)
        layout.addWidget(self._vs_grp)

        # -- Subplot Ratios (grid mode only) --
        self._ratio_grp = QGroupBox("Subplot Width Ratios")
        ratio_form = QFormLayout(self._ratio_grp)
        ratio_form.setSpacing(4)

        self.ratio_subplot_combo = QComboBox()
        self.ratio_subplot_combo.currentIndexChanged.connect(
            self._on_ratio_subplot_changed
        )
        ratio_form.addRow("Subplot:", self.ratio_subplot_combo)

        self.ratio_spin = QDoubleSpinBox()
        self.ratio_spin.setRange(0.1, 10.0)
        self.ratio_spin.setSingleStep(0.1)
        self.ratio_spin.setDecimals(1)
        self.ratio_spin.setValue(1.0)
        self.ratio_spin.valueChanged.connect(self._on_ratio_value_changed)
        ratio_form.addRow("Width Ratio:", self.ratio_spin)

        self._ratio_grp.setVisible(False)
        self._ratio_data = {}  # col_index -> ratio value
        self._ratio_updating = False
        layout.addWidget(self._ratio_grp)

        layout.addStretch()

        # Connect all signals
        for w in (
            self.width_spin, self.height_spin, self.dpi_spin,
            self.margin_left, self.margin_right,
            self.margin_top, self.margin_bottom,
            self.hspace_spin, self.vspace_spin,
            self.vs_gap_spin, self.vs_ratio_spin, self.sig_ratio_spin,
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

    def write_vs_to(self, settings):
        """Write Vs Profile layout values into StudioSettings."""
        settings.vs_wspace = self.vs_gap_spin.value()
        settings.vs_width_ratios = (
            self.vs_ratio_spin.value(),
            self.sig_ratio_spin.value(),
        )

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

    def read_vs_from(self, settings):
        """Populate Vs Profile controls from StudioSettings."""
        self.blockSignals(True)
        self.vs_gap_spin.setValue(settings.vs_wspace)
        self.vs_ratio_spin.setValue(settings.vs_width_ratios[0])
        self.sig_ratio_spin.setValue(settings.vs_width_ratios[1])
        self.blockSignals(False)

    def set_vs_visible(self, visible: bool):
        """Show/hide the Vs Profile layout group."""
        self._vs_grp.setVisible(visible)

    # -- Subplot ratio controls -------------------------------------------

    def set_ratio_subplots(self, subplot_info: list, col_ratios: list):
        """Populate subplot ratio dropdown from [(key, name), ...] list.
        Only shown when grid_cols >= 2."""
        self._ratio_updating = True
        self.ratio_subplot_combo.clear()
        self._ratio_data.clear()

        # Determine unique columns from subplot keys (cell_R_C pattern)
        col_names = []
        for key, name in subplot_info:
            if key.startswith("cell_"):
                parts = key.split("_")
                if len(parts) >= 3:
                    c = int(parts[2])
                    if c not in self._ratio_data:
                        col_names.append((c, name))
                        idx = len(col_ratios) > c
                        self._ratio_data[c] = col_ratios[c] if c < len(col_ratios) else 1.0

        if len(self._ratio_data) < 2:
            self._ratio_grp.setVisible(False)
            self._ratio_updating = False
            return

        self._ratio_grp.setVisible(True)
        for c, name in sorted(col_names):
            self.ratio_subplot_combo.addItem(
                f"Column {c + 1}: {name}", c
            )

        if self.ratio_subplot_combo.count() > 0:
            self.ratio_subplot_combo.setCurrentIndex(0)
            c = self.ratio_subplot_combo.currentData()
            self.ratio_spin.setValue(self._ratio_data.get(c, 1.0))

        self._ratio_updating = False

    def _on_ratio_subplot_changed(self, index):
        if self._ratio_updating or index < 0:
            return
        c = self.ratio_subplot_combo.itemData(index)
        if c is not None:
            self._ratio_updating = True
            self.ratio_spin.setValue(self._ratio_data.get(c, 1.0))
            self._ratio_updating = False

    def _on_ratio_value_changed(self, value):
        if self._ratio_updating:
            return
        c = self.ratio_subplot_combo.currentData()
        if c is not None:
            self._ratio_data[c] = value
            self.changed.emit()

    def get_col_ratios(self) -> list:
        """Return column ratios as a list ordered by column index."""
        if not self._ratio_data:
            return []
        max_col = max(self._ratio_data.keys())
        return [self._ratio_data.get(c, 1.0) for c in range(max_col + 1)]

    def write_ratios_to(self, state):
        """Write ratio overrides into FigureState."""
        ratios = self.get_col_ratios()
        if ratios:
            state.grid_col_ratios = ratios
