"""Legend settings panel — single control set applied to checked subplots."""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout, QDoubleSpinBox, QSpinBox,
    QComboBox, QCheckBox, QScrollArea, QToolButton, QHBoxLayout,
)
from PySide6.QtCore import Signal, Qt
from geo_figure.gui.studio.models import LegendConfig
from geo_figure.gui.studio.panels import CollapsibleSection


LEGEND_LOCATIONS = [
    "upper right", "upper left", "lower left", "lower right",
    "right", "center left", "center right",
    "lower center", "upper center", "center", "best",
]

PLACEMENT_OPTIONS = ["Inside", "Outside Left", "Outside Right", "Outside Top", "Outside Bottom"]
_PLACEMENT_MAP = {
    "Inside": "inside",
    "Outside Left": "outside_left",
    "Outside Right": "outside_right",
    "Outside Top": "outside_top",
    "Outside Bottom": "outside_bottom",
}
_PLACEMENT_REVERSE = {v: k for k, v in _PLACEMENT_MAP.items()}


class LegendPanel(QWidget):
    """Single legend control set applied to all checked subplots."""

    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(scroll.Shape.NoFrame)
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)
        scroll.setWidget(content)
        outer.addWidget(scroll)

        # -- Subplot selector with checkboxes --
        sel_sec = CollapsibleSection("Subplots")
        sel_lay = QVBoxLayout(sel_sec.content)
        sel_lay.setContentsMargins(8, 2, 4, 2)
        sel_lay.setSpacing(2)

        btn_row = QHBoxLayout()
        btn_row.setContentsMargins(0, 0, 0, 0)
        self._sel_all_btn = QToolButton()
        self._sel_all_btn.setText("All")
        self._sel_all_btn.setStyleSheet(
            "QToolButton { border: 1px solid #999; padding: 1px 6px; }"
        )
        self._sel_all_btn.clicked.connect(self._select_all)
        self._desel_all_btn = QToolButton()
        self._desel_all_btn.setText("None")
        self._desel_all_btn.setStyleSheet(
            "QToolButton { border: 1px solid #999; padding: 1px 6px; }"
        )
        self._desel_all_btn.clicked.connect(self._deselect_all)
        btn_row.addWidget(self._sel_all_btn)
        btn_row.addWidget(self._desel_all_btn)
        btn_row.addStretch()
        sel_lay.addLayout(btn_row)

        self._check_container = QVBoxLayout()
        self._check_container.setSpacing(1)
        sel_lay.addLayout(self._check_container)
        layout.addWidget(sel_sec)

        # -- Legend settings (single set) --
        legend_sec = CollapsibleSection("Legend")
        form = QFormLayout(legend_sec.content)
        form.setContentsMargins(8, 2, 4, 2)
        form.setSpacing(4)

        self.show_check = QCheckBox("Show Legend")
        self.show_check.setChecked(True)
        form.addRow(self.show_check)

        self.placement_combo = QComboBox()
        self.placement_combo.addItems(PLACEMENT_OPTIONS)
        form.addRow("Placement:", self.placement_combo)

        self.location_combo = QComboBox()
        self.location_combo.addItems(LEGEND_LOCATIONS)
        form.addRow("Position:", self.location_combo)

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

        self.markerscale_spin = QDoubleSpinBox()
        self.markerscale_spin.setRange(0.2, 5.0)
        self.markerscale_spin.setValue(1.0)
        self.markerscale_spin.setSingleStep(0.1)
        form.addRow("Marker Scale:", self.markerscale_spin)

        layout.addWidget(legend_sec)

        # -- Frame settings --
        frame_sec = CollapsibleSection("Frame")
        frame_form = QFormLayout(frame_sec.content)
        frame_form.setContentsMargins(8, 2, 4, 2)
        frame_form.setSpacing(4)

        self.frame_check = QCheckBox("Frame")
        self.frame_check.setChecked(True)
        frame_form.addRow(self.frame_check)

        self.frame_alpha = QDoubleSpinBox()
        self.frame_alpha.setRange(0.0, 1.0)
        self.frame_alpha.setValue(0.9)
        self.frame_alpha.setSingleStep(0.05)
        frame_form.addRow("Frame Opacity:", self.frame_alpha)

        self.shadow_check = QCheckBox("Shadow")
        frame_form.addRow(self.shadow_check)

        layout.addWidget(frame_sec)

        # -- Figure-level scale --
        scale_sec = CollapsibleSection("Overall Scale")
        scale_form = QFormLayout(scale_sec.content)
        scale_form.setContentsMargins(8, 2, 4, 2)
        scale_form.setSpacing(4)

        self.legend_scale_spin = QDoubleSpinBox()
        self.legend_scale_spin.setRange(0.3, 3.0)
        self.legend_scale_spin.setValue(1.0)
        self.legend_scale_spin.setSingleStep(0.1)
        self.legend_scale_spin.setToolTip(
            "Scale applied to all legend text and markers"
        )
        scale_form.addRow("Legend Scale:", self.legend_scale_spin)

        layout.addWidget(scale_sec)
        layout.addStretch()

        # Connect value-change signals
        for w in (self.show_check, self.frame_check, self.shadow_check):
            w.stateChanged.connect(self._on_value_changed)
        self.placement_combo.currentIndexChanged.connect(self._on_value_changed)
        self.location_combo.currentIndexChanged.connect(self._on_value_changed)
        for w in (self.ncol_spin, self.fontsize_spin, self.markerscale_spin,
                  self.frame_alpha, self.legend_scale_spin):
            w.valueChanged.connect(self._on_value_changed)

        self._subplot_checks: list[tuple[str, QCheckBox]] = []
        self._settings = None
        self._updating = False
        self._active_key = ""  # key currently loaded into controls

    # -- Public API -----------------------------------------------------------

    def set_subplots(self, subplot_info: list, settings):
        """Populate subplot checkboxes and load first subplot's config."""
        self._settings = settings
        self._updating = True

        # Clear old checkboxes
        for _key, cb in self._subplot_checks:
            self._check_container.removeWidget(cb)
            cb.deleteLater()
        self._subplot_checks.clear()

        # Create checkbox per subplot
        for key, name in subplot_info:
            label = name if name else key
            cb = QCheckBox(label)
            cb.setChecked(True)
            cb.setProperty("subplot_key", key)
            cb.stateChanged.connect(self._on_check_toggled)
            self._check_container.addWidget(cb)
            self._subplot_checks.append((key, cb))

        self.legend_scale_spin.setValue(settings.legend_scale)

        # Load first subplot's config into controls
        if self._subplot_checks:
            self._load_config(self._subplot_checks[0][0])

        self._updating = False

    def sync_all(self):
        """Save current control values to all checked subplots."""
        self._save_to_checked()

    # -- Internal -------------------------------------------------------------

    def _load_config(self, key: str):
        """Load a subplot's legend config into the controls."""
        self._active_key = key
        if not self._settings:
            return
        lc = self._settings.legend_for(key)
        self._updating = True
        self.show_check.setChecked(lc.show)

        pl_text = _PLACEMENT_REVERSE.get(lc.placement, "Inside")
        idx = self.placement_combo.findText(pl_text)
        if idx >= 0:
            self.placement_combo.setCurrentIndex(idx)

        idx = self.location_combo.findText(lc.location)
        if idx >= 0:
            self.location_combo.setCurrentIndex(idx)
        self.ncol_spin.setValue(lc.ncol)
        self.fontsize_spin.setValue(lc.fontsize or 9.0)
        self.markerscale_spin.setValue(lc.markerscale)
        self.frame_check.setChecked(lc.frame_on)
        self.frame_alpha.setValue(lc.frame_alpha)
        self.shadow_check.setChecked(lc.shadow)
        self._updating = False

    def _read_controls(self) -> dict:
        """Read current control values into a dict."""
        return {
            "show": self.show_check.isChecked(),
            "placement": _PLACEMENT_MAP.get(
                self.placement_combo.currentText(), "inside"
            ),
            "location": self.location_combo.currentText(),
            "ncol": self.ncol_spin.value(),
            "fontsize": self.fontsize_spin.value(),
            "markerscale": self.markerscale_spin.value(),
            "frame_on": self.frame_check.isChecked(),
            "frame_alpha": self.frame_alpha.value(),
            "shadow": self.shadow_check.isChecked(),
        }

    def _save_to_checked(self):
        """Write current control values to all checked subplots."""
        if not self._settings:
            return
        vals = self._read_controls()
        for key, cb in self._subplot_checks:
            if cb.isChecked():
                lc = self._settings.legend_for(key)
                for attr, val in vals.items():
                    setattr(lc, attr, val)
        self._settings.legend_scale = self.legend_scale_spin.value()

    def _on_value_changed(self):
        if self._updating:
            return
        self._save_to_checked()
        self.changed.emit()

    def _on_check_toggled(self, state):
        """When a subplot checkbox is toggled, load its config if checked."""
        if self._updating:
            return
        cb = self.sender()
        if not cb:
            return
        key = cb.property("subplot_key")
        if state and key:
            # Apply current controls to newly checked subplot too
            self._save_to_checked()
            self.changed.emit()

    def _select_all(self):
        self._updating = True
        for _key, cb in self._subplot_checks:
            cb.setChecked(True)
        self._updating = False
        self._save_to_checked()
        self.changed.emit()

    def _deselect_all(self):
        self._updating = True
        for _key, cb in self._subplot_checks:
            cb.setChecked(False)
        self._updating = False

    # -- Legacy compat (global write/read for presets) ------------------------

    def write_to(self, cfg):
        """Save all checked subplots. Also writes global cfg."""
        self._save_to_checked()
        if self._settings and self._subplot_checks:
            first = self._settings.legend_for(self._subplot_checks[0][0])
            for attr in ("show", "location", "placement", "ncol", "fontsize",
                         "markerscale", "frame_on", "frame_alpha", "shadow"):
                setattr(cfg, attr, getattr(first, attr))

    def read_from(self, cfg):
        """Populate controls from global LegendConfig (used for presets)."""
        self._updating = True
        self.show_check.setChecked(cfg.show)
        pl_text = _PLACEMENT_REVERSE.get(cfg.placement, "Inside")
        idx = self.placement_combo.findText(pl_text)
        if idx >= 0:
            self.placement_combo.setCurrentIndex(idx)
        idx = self.location_combo.findText(cfg.location)
        if idx >= 0:
            self.location_combo.setCurrentIndex(idx)
        self.ncol_spin.setValue(cfg.ncol)
        self.fontsize_spin.setValue(cfg.fontsize or 9.0)
        self.markerscale_spin.setValue(getattr(cfg, "markerscale", 1.0))
        self.frame_check.setChecked(cfg.frame_on)
        self.frame_alpha.setValue(cfg.frame_alpha)
        self.shadow_check.setChecked(cfg.shadow)
        self._updating = False
