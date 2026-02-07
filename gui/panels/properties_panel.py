"""Properties panel - right dock showing selected curve info and controls."""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout, QLabel, QLineEdit,
    QComboBox, QDoubleSpinBox, QSpinBox, QCheckBox,
    QPushButton, QGroupBox, QColorDialog, QHBoxLayout,
    QScrollArea, QTableWidget, QTableWidgetItem, QHeaderView,
    QToolButton
)
from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QColor, QPixmap, QPainter, QBrush
from typing import Optional
from geo_figure.core.models import CurveData, WaveType, SourceType, EnsembleData


class CollapsibleSection(QWidget):
    """A section with a clickable arrow header that expands/collapses content."""

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
        self.form = QFormLayout(self.content)
        self.form.setContentsMargins(8, 2, 4, 2)
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

    def set_expanded(self, expanded: bool):
        self._toggle.setChecked(expanded)


class PropertiesPanel(QWidget):
    """Panel showing editable properties for the selected curve or ensemble."""

    curve_updated = Signal(str, CurveData)  # uid, updated data
    subplot_change_requested = Signal(str, str)  # uid, new_subplot_key
    ensemble_updated = Signal(str, EnsembleData)  # uid, updated ensemble
    legend_changed = Signal(dict)  # legend config dict

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_uid: Optional[str] = None
        self._current_curve: Optional[CurveData] = None
        self._current_ensemble: Optional[EnsembleData] = None
        self._updating = False  # prevent signal loops
        self._setup_ui()

    # ── Collapsible group helper ─────────────────────────────────

    @staticmethod
    def _make_section(title: str, expanded: bool = True):
        """Create a CollapsibleSection with arrow-based toggle."""
        section = CollapsibleSection(title, expanded=expanded)
        return section, section.content, section.form

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(4, 4, 4, 4)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setSpacing(8)

        # -- Empty state --
        self.empty_label = QLabel("Select a curve to view properties")
        self.empty_label.setAlignment(Qt.AlignCenter)
        self.empty_label.setStyleSheet("color: #666666; font-style: italic;")
        layout.addWidget(self.empty_label)

        # -- Info group (collapsible, expanded by default) --
        self.info_group, _ic, info_layout = self._make_section("Curve Info", expanded=True)

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Custom display name")
        self.name_edit.editingFinished.connect(self._on_name_changed)
        info_layout.addRow("Name:", self.name_edit)

        self.wave_combo = QComboBox()
        self.wave_combo.addItems(["Rayleigh", "Love"])
        self.wave_combo.currentIndexChanged.connect(self._on_wave_type_changed)
        info_layout.addRow("Wave Type:", self.wave_combo)

        self.source_combo = QComboBox()
        self.source_combo.addItems(["Passive", "Active"])
        self.source_combo.currentIndexChanged.connect(self._on_source_type_changed)
        info_layout.addRow("Source:", self.source_combo)

        self.mode_label = QLabel("-")
        info_layout.addRow("Mode:", self.mode_label)
        self.points_label = QLabel("-")
        info_layout.addRow("Points:", self.points_label)
        self.freq_label = QLabel("-")
        info_layout.addRow("Freq Range:", self.freq_label)
        self.active_range_label = QLabel("-")
        info_layout.addRow("Active Range:", self.active_range_label)
        self.active_pts_label = QLabel("-")
        info_layout.addRow("Active Points:", self.active_pts_label)
        self.file_label = QLabel("-")
        self.file_label.setWordWrap(True)
        info_layout.addRow("File:", self.file_label)

        self.subplot_combo = QComboBox()
        self.subplot_combo.currentIndexChanged.connect(self._on_subplot_changed)
        info_layout.addRow("Subplot:", self.subplot_combo)

        self.info_group.setVisible(False)
        layout.addWidget(self.info_group)

        # -- Style group (collapsible, collapsed by default) --
        self.style_group, _sc, style_layout = self._make_section("Style", expanded=False)

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

        # -- Processing group (collapsible, collapsed by default) --
        self.proc_group, _pc, proc_layout = self._make_section("Processing", expanded=False)

        self.stddev_combo = QComboBox()
        self.stddev_combo.addItems([
            "From File", "Fixed LogStd", "Fixed CoV", "Range-based"
        ])
        self.stddev_combo.currentIndexChanged.connect(self._on_stddev_mode_changed)
        proc_layout.addRow("StdDev:", self.stddev_combo)

        self.fixed_value_spin = QDoubleSpinBox()
        self.fixed_value_spin.setRange(0.001, 10.0)
        self.fixed_value_spin.setDecimals(3)
        self.fixed_value_spin.setValue(0.1)
        self.fixed_value_spin.setVisible(False)
        self.fixed_value_spin.valueChanged.connect(self._on_proc_changed)
        self.fixed_value_label = QLabel("Value:")
        self.fixed_value_label.setVisible(False)
        proc_layout.addRow(self.fixed_value_label, self.fixed_value_spin)

        # Range-based deviation table
        self.range_group = QWidget()
        range_layout = QVBoxLayout(self.range_group)
        range_layout.setContentsMargins(0, 0, 0, 0)
        range_layout.setSpacing(4)

        self.range_table = QTableWidget(0, 3)
        self.range_table.setHorizontalHeaderLabels(["From (Hz)", "To (Hz)", "StdDev"])
        self.range_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.range_table.setMaximumHeight(150)
        self.range_table.cellChanged.connect(self._on_range_table_changed)
        range_layout.addWidget(self.range_table)

        range_btn_row = QHBoxLayout()
        add_range_btn = QPushButton("+ Add Range")
        add_range_btn.clicked.connect(self._add_range_row)
        range_btn_row.addWidget(add_range_btn)
        del_range_btn = QPushButton("- Remove")
        del_range_btn.clicked.connect(self._remove_range_row)
        range_btn_row.addWidget(del_range_btn)
        range_layout.addLayout(range_btn_row)

        self.range_group.setVisible(False)
        proc_layout.addRow(self.range_group)

        self.resample_cb = QCheckBox("Enable Resample")
        self.resample_cb.stateChanged.connect(self._on_proc_changed)
        proc_layout.addRow(self.resample_cb)

        self.resample_n = QSpinBox()
        self.resample_n.setRange(10, 500)
        self.resample_n.setValue(50)
        self.resample_n.setVisible(False)
        self.resample_n.valueChanged.connect(self._on_proc_changed)
        self.resample_n_label = QLabel("N Points:")
        self.resample_n_label.setVisible(False)
        proc_layout.addRow(self.resample_n_label, self.resample_n)

        self.resample_method = QComboBox()
        self.resample_method.addItems(["Logarithmic", "Linear"])
        self.resample_method.setVisible(False)
        self.resample_method.currentIndexChanged.connect(self._on_proc_changed)
        self.resample_method_label = QLabel("Method:")
        self.resample_method_label.setVisible(False)
        proc_layout.addRow(self.resample_method_label, self.resample_method)

        self.proc_group.setVisible(False)
        layout.addWidget(self.proc_group)

        # -- Ensemble group (collapsible, shown when ensemble is selected) --
        self.ens_group, _ec, ens_layout = self._make_section("Ensemble Info", expanded=True)

        self.ens_name_edit = QLineEdit()
        self.ens_name_edit.setPlaceholderText("Ensemble display name")
        self.ens_name_edit.editingFinished.connect(self._on_ens_changed)
        ens_layout.addRow("Name:", self.ens_name_edit)

        self.ens_models_label = QLabel("-")
        ens_layout.addRow("Models:", self.ens_models_label)
        self.ens_wave_label = QLabel("-")
        ens_layout.addRow("Wave Type:", self.ens_wave_label)
        self.ens_mode_label = QLabel("-")
        ens_layout.addRow("Mode:", self.ens_mode_label)

        self.ens_sigma_label = QLabel("-")
        ens_layout.addRow("Sigma_ln (mean):", self.ens_sigma_label)
        self.ens_sigma_max_label = QLabel("-")
        ens_layout.addRow("Sigma_ln (max):", self.ens_sigma_max_label)

        self.ens_group.setVisible(False)
        layout.addWidget(self.ens_group)

        # -- Ensemble Layer Style group (collapsible, collapsed by default) --
        self.ens_style_group, _esc, ens_style_layout = self._make_section("Layer Styles", expanded=False)

        # Median layer
        ens_style_layout.addRow(QLabel("-- Median --"))
        med_row = QHBoxLayout()
        self.ens_med_color_btn = QPushButton()
        self.ens_med_color_btn.setFixedSize(28, 28)
        self.ens_med_color_btn.clicked.connect(
            lambda: self._pick_ens_layer_color("median")
        )
        med_row.addWidget(self.ens_med_color_btn)
        self.ens_med_width = QDoubleSpinBox()
        self.ens_med_width.setRange(0.5, 10)
        self.ens_med_width.setSingleStep(0.5)
        self.ens_med_width.setValue(2.5)
        self.ens_med_width.valueChanged.connect(self._on_ens_changed)
        med_row.addWidget(QLabel("Width:"))
        med_row.addWidget(self.ens_med_width)
        ens_style_layout.addRow("Color:", med_row)

        # Percentile band
        ens_style_layout.addRow(QLabel("-- 16-84 Percentile --"))
        pct_row = QHBoxLayout()
        self.ens_pct_color_btn = QPushButton()
        self.ens_pct_color_btn.setFixedSize(28, 28)
        self.ens_pct_color_btn.clicked.connect(
            lambda: self._pick_ens_layer_color("percentile")
        )
        pct_row.addWidget(self.ens_pct_color_btn)
        self.ens_pct_alpha = QSpinBox()
        self.ens_pct_alpha.setRange(5, 255)
        self.ens_pct_alpha.setValue(50)
        self.ens_pct_alpha.valueChanged.connect(self._on_ens_changed)
        pct_row.addWidget(QLabel("Alpha:"))
        pct_row.addWidget(self.ens_pct_alpha)
        ens_style_layout.addRow("Color:", pct_row)

        # Envelope
        ens_style_layout.addRow(QLabel("-- Envelope --"))
        env_row = QHBoxLayout()
        self.ens_env_color_btn = QPushButton()
        self.ens_env_color_btn.setFixedSize(28, 28)
        self.ens_env_color_btn.clicked.connect(
            lambda: self._pick_ens_layer_color("envelope")
        )
        env_row.addWidget(self.ens_env_color_btn)
        self.ens_env_alpha = QSpinBox()
        self.ens_env_alpha.setRange(5, 255)
        self.ens_env_alpha.setValue(80)
        self.ens_env_alpha.valueChanged.connect(self._on_ens_changed)
        env_row.addWidget(QLabel("Alpha:"))
        env_row.addWidget(self.ens_env_alpha)
        ens_style_layout.addRow("Color:", env_row)

        # Individual curves
        ens_style_layout.addRow(QLabel("-- Individual Curves --"))
        ind_row = QHBoxLayout()
        self.ens_ind_color_btn = QPushButton()
        self.ens_ind_color_btn.setFixedSize(28, 28)
        self.ens_ind_color_btn.clicked.connect(
            lambda: self._pick_ens_layer_color("individual")
        )
        ind_row.addWidget(self.ens_ind_color_btn)
        self.ens_ind_alpha = QSpinBox()
        self.ens_ind_alpha.setRange(5, 255)
        self.ens_ind_alpha.setValue(25)
        self.ens_ind_alpha.valueChanged.connect(self._on_ens_changed)
        ind_row.addWidget(QLabel("Alpha:"))
        ind_row.addWidget(self.ens_ind_alpha)
        ens_style_layout.addRow("Color:", ind_row)

        self.ens_max_ind = QSpinBox()
        self.ens_max_ind.setRange(10, 5000)
        self.ens_max_ind.setValue(200)
        self.ens_max_ind.valueChanged.connect(self._on_ens_changed)
        ens_style_layout.addRow("Max Curves:", self.ens_max_ind)

        self.ens_style_group.setVisible(False)
        layout.addWidget(self.ens_style_group)

        # -- Legend group (always accessible when curve/ensemble visible) --
        self.legend_group, _lc, legend_layout = self._make_section("Legend", expanded=False)

        self.legend_visible_cb = QCheckBox("Show Legend")
        self.legend_visible_cb.setChecked(True)
        self.legend_visible_cb.stateChanged.connect(self._on_legend_changed)
        legend_layout.addRow(self.legend_visible_cb)

        self.legend_pos_combo = QComboBox()
        self.legend_pos_combo.addItems(["top-right", "top-left", "bottom-right", "bottom-left"])
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

        layout.addStretch()
        scroll.setWidget(container)
        main_layout.addWidget(scroll)

    def show_curve(self, uid: str, curve: CurveData):
        """Display properties for the given curve."""
        self._updating = True
        self._current_uid = uid
        self._current_curve = curve
        self._current_ensemble = None

        self.empty_label.setVisible(False)
        self.info_group.setVisible(True)
        self.style_group.setVisible(True)
        self.proc_group.setVisible(True)
        self.ens_group.setVisible(False)
        self.ens_style_group.setVisible(False)
        self.legend_group.setVisible(True)

        # Info
        self.name_edit.setText(curve.custom_name or curve.name)
        wave_idx = 0 if curve.wave_type == WaveType.RAYLEIGH else 1
        self.wave_combo.setCurrentIndex(wave_idx)
        source_idx = 0 if curve.source_type == SourceType.PASSIVE else 1
        self.source_combo.setCurrentIndex(source_idx)
        self.mode_label.setText(str(curve.mode))
        self.points_label.setText(str(curve.n_points))
        self.freq_label.setText(f"{curve.freq_min:.2f} - {curve.freq_max:.2f} Hz")
        self._update_active_range(curve)
        self.file_label.setText(curve.filepath or "-")
        # Subplot combo — select current subplot_key
        idx = self.subplot_combo.findData(curve.subplot_key)
        if idx >= 0:
            self.subplot_combo.setCurrentIndex(idx)

        # Style
        self._update_color_button(curve.color)
        self.width_spin.setValue(curve.line_width)
        self.marker_spin.setValue(curve.marker_size)
        self.errbar_cb.setChecked(curve.show_error_bars)

        # Processing
        mode_map = {"file": 0, "fixed_logstd": 1, "fixed_cov": 2, "range": 3}
        self.stddev_combo.setCurrentIndex(mode_map.get(curve.stddev_mode, 0))
        self._update_stddev_visibility(self.stddev_combo.currentIndex())
        # Populate fixed value spin based on current mode
        if curve.stddev_mode == "fixed_logstd":
            self.fixed_value_spin.setValue(curve.fixed_logstd)
        elif curve.stddev_mode == "fixed_cov":
            self.fixed_value_spin.setValue(curve.fixed_cov)
        self.resample_cb.setChecked(curve.resample_enabled)
        self.resample_n.setValue(curve.resample_n_points)
        method_idx = 0 if curve.resample_method == "log" else 1
        self.resample_method.setCurrentIndex(method_idx)
        # Restore resample controls visibility
        show_resample = curve.resample_enabled
        self.resample_n.setVisible(show_resample)
        self.resample_n_label.setVisible(show_resample)
        self.resample_method.setVisible(show_resample)
        self.resample_method_label.setVisible(show_resample)

        # Range table
        self._populate_range_table(curve.stddev_ranges)

        self._updating = False

    def show_ensemble(self, uid: str, ens: EnsembleData):
        """Display properties for the given ensemble."""
        self._updating = True
        self._current_uid = uid
        self._current_curve = None
        self._current_ensemble = ens

        self.empty_label.setVisible(False)
        self.info_group.setVisible(False)
        self.style_group.setVisible(False)
        self.proc_group.setVisible(False)
        self.ens_group.setVisible(True)
        self.ens_style_group.setVisible(True)
        self.legend_group.setVisible(True)

        # Ensemble info
        self.ens_name_edit.setText(ens.custom_name or ens.name)
        self.ens_models_label.setText(str(ens.n_profiles))
        self.ens_wave_label.setText(ens.wave_type.value)
        self.ens_mode_label.setText(str(ens.mode))

        # Sigma_ln summary
        import numpy as np
        if ens.sigma_ln is not None and len(ens.sigma_ln) > 0:
            valid = ens.sigma_ln[~np.isnan(ens.sigma_ln)]
            if len(valid) > 0:
                self.ens_sigma_label.setText(f"{np.mean(valid):.4f}")
                self.ens_sigma_max_label.setText(f"{np.max(valid):.4f}")
            else:
                self.ens_sigma_label.setText("-")
                self.ens_sigma_max_label.setText("-")
        else:
            self.ens_sigma_label.setText("-")
            self.ens_sigma_max_label.setText("-")

        # Layer styles
        self._set_ens_color_btn(self.ens_med_color_btn, ens.median_layer.color)
        self.ens_med_width.setValue(ens.median_layer.line_width)

        self._set_ens_color_btn(self.ens_pct_color_btn, ens.percentile_layer.color)
        self.ens_pct_alpha.setValue(ens.percentile_layer.alpha)

        self._set_ens_color_btn(self.ens_env_color_btn, ens.envelope_layer.color)
        self.ens_env_alpha.setValue(ens.envelope_layer.alpha)

        self._set_ens_color_btn(self.ens_ind_color_btn, ens.individual_layer.color)
        self.ens_ind_alpha.setValue(ens.individual_layer.alpha)
        self.ens_max_ind.setValue(ens.max_individual)

        self._updating = False

    def clear(self):
        """Clear the panel."""
        self._current_uid = None
        self._current_curve = None
        self._current_ensemble = None
        self.empty_label.setVisible(True)
        self.info_group.setVisible(False)
        self.style_group.setVisible(False)
        self.proc_group.setVisible(False)
        self.ens_group.setVisible(False)
        self.ens_style_group.setVisible(False)
        self.legend_group.setVisible(False)

    # ── Internal helpers ─────────────────────────────────────────

    def _update_active_range(self, curve):
        """Compute and display the range of active (ON) points."""
        import numpy as np
        if curve.frequency is not None and curve.point_mask is not None:
            active_freq = curve.frequency[curve.point_mask]
            n_active = len(active_freq)
            if n_active > 0:
                self.active_range_label.setText(
                    f"{active_freq.min():.2f} - {active_freq.max():.2f} Hz"
                )
            else:
                self.active_range_label.setText("(none)")
            self.active_pts_label.setText(f"{n_active} / {curve.n_points}")
        else:
            self.active_range_label.setText("-")
            self.active_pts_label.setText("-")

    def set_available_subplots(self, subplots: list):
        """Update the subplot combo options. subplots = [(key, name), ...]."""
        self._updating = True
        self.subplot_combo.clear()
        for key, name in subplots:
            self.subplot_combo.addItem(name, key)
        self._updating = False

    def _on_subplot_changed(self, index):
        if self._updating or not self._current_curve:
            return
        new_key = self.subplot_combo.itemData(index)
        if new_key and new_key != self._current_curve.subplot_key:
            self.subplot_change_requested.emit(self._current_uid, new_key)

    def _update_color_button(self, color_str: str):
        pixmap = QPixmap(24, 24)
        pixmap.fill(QColor(color_str))
        self.color_btn.setIcon(pixmap)
        self.color_btn.setStyleSheet(
            f"background-color: {color_str}; border: 1px solid #555555; border-radius: 3px;"
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

    def _on_name_changed(self):
        if self._updating or not self._current_curve:
            return
        new_name = self.name_edit.text().strip()
        self._current_curve.custom_name = new_name
        self._emit_update()

    def _on_wave_type_changed(self, index):
        if self._updating or not self._current_curve:
            return
        self._current_curve.wave_type = WaveType.RAYLEIGH if index == 0 else WaveType.LOVE
        # Also update curve_type to match
        from geo_figure.core.models import CurveType
        if self._current_curve.curve_type != CurveType.THEORETICAL:
            self._current_curve.curve_type = (
                CurveType.RAYLEIGH if index == 0 else CurveType.LOVE
            )
        self._emit_update()

    def _on_source_type_changed(self, index):
        if self._updating or not self._current_curve:
            return
        self._current_curve.source_type = (
            SourceType.PASSIVE if index == 0 else SourceType.ACTIVE
        )
        self._emit_update()

    def _on_style_changed(self):
        if self._updating or not self._current_curve:
            return
        self._current_curve.line_width = self.width_spin.value()
        self._current_curve.marker_size = self.marker_spin.value()
        self._current_curve.show_error_bars = self.errbar_cb.isChecked()
        self._emit_update()

    def _on_stddev_mode_changed(self, index):
        self._update_stddev_visibility(index)
        if not self._updating:
            self._on_proc_changed()

    def _update_stddev_visibility(self, index):
        show_fixed = index in (1, 2)
        show_range = index == 3
        self.fixed_value_spin.setVisible(show_fixed)
        self.fixed_value_label.setVisible(show_fixed)
        self.range_group.setVisible(show_range)
        # Update label text based on mode
        if index == 1:
            self.fixed_value_label.setText("LogStd:")
        elif index == 2:
            self.fixed_value_label.setText("CoV:")

    def _on_proc_changed(self):
        if self._updating or not self._current_curve:
            return
        modes = ["file", "fixed_logstd", "fixed_cov", "range"]
        idx = self.stddev_combo.currentIndex()
        self._current_curve.stddev_mode = modes[idx]
        if idx == 1:
            self._current_curve.fixed_logstd = self.fixed_value_spin.value()
        elif idx == 2:
            self._current_curve.fixed_cov = self.fixed_value_spin.value()
        elif idx == 3:
            self._current_curve.stddev_ranges = self._read_range_table()

        self._current_curve.resample_enabled = self.resample_cb.isChecked()
        show_resample = self._current_curve.resample_enabled
        self.resample_n.setVisible(show_resample)
        self.resample_n_label.setVisible(show_resample)
        self.resample_method.setVisible(show_resample)
        self.resample_method_label.setVisible(show_resample)
        self._current_curve.resample_n_points = self.resample_n.value()
        self._current_curve.resample_method = (
            "log" if self.resample_method.currentIndex() == 0 else "linear"
        )
        self._emit_update()

    # ── Range-based deviation table ──────────────────────────────

    def _populate_range_table(self, ranges: list):
        """Fill range table from list of (fmin, fmax, value) tuples."""
        self.range_table.blockSignals(True)
        self.range_table.setRowCount(0)
        for fmin, fmax, val in ranges:
            row = self.range_table.rowCount()
            self.range_table.insertRow(row)
            self.range_table.setItem(row, 0, QTableWidgetItem(f"{fmin:.2f}"))
            self.range_table.setItem(row, 1, QTableWidgetItem(f"{fmax:.2f}"))
            self.range_table.setItem(row, 2, QTableWidgetItem(f"{val:.3f}"))
        self.range_table.blockSignals(False)

    def _add_range_row(self):
        """Add a new empty row to the range table."""
        row = self.range_table.rowCount()
        # Default: start from previous end, or 0
        fmin = 0.0
        if row > 0:
            prev_to = self.range_table.item(row - 1, 1)
            if prev_to:
                try:
                    fmin = float(prev_to.text())
                except ValueError:
                    pass
        self.range_table.insertRow(row)
        self.range_table.setItem(row, 0, QTableWidgetItem(f"{fmin:.2f}"))
        self.range_table.setItem(row, 1, QTableWidgetItem(f"{fmin + 5:.2f}"))
        self.range_table.setItem(row, 2, QTableWidgetItem("0.100"))

    def _remove_range_row(self):
        """Remove the selected row from the range table."""
        row = self.range_table.currentRow()
        if row >= 0:
            self.range_table.removeRow(row)
            self._on_range_table_changed()

    def _read_range_table(self) -> list:
        """Read all rows as list of (fmin, fmax, value) tuples."""
        ranges = []
        for row in range(self.range_table.rowCount()):
            try:
                fmin = float(self.range_table.item(row, 0).text())
                fmax = float(self.range_table.item(row, 1).text())
                val = float(self.range_table.item(row, 2).text())
                ranges.append((fmin, fmax, val))
            except (ValueError, AttributeError):
                continue
        return ranges

    def _on_range_table_changed(self):
        if self._updating or not self._current_curve:
            return
        self._current_curve.stddev_ranges = self._read_range_table()
        self._emit_update()

    def _emit_update(self):
        if self._current_uid and self._current_curve:
            self.curve_updated.emit(self._current_uid, self._current_curve)

    # ── Ensemble helpers ─────────────────────────────────────────

    @staticmethod
    def _set_ens_color_btn(btn, color_str: str):
        """Set a small color swatch on a button."""
        pix = QPixmap(28, 28)
        pix.fill(QColor(color_str))
        btn.setIcon(pix)
        btn.setProperty("_color", color_str)

    def _pick_ens_layer_color(self, layer_name: str):
        """Open color picker for an ensemble layer."""
        ens = self._current_ensemble
        if not ens:
            return
        layer = getattr(ens, f"{layer_name}_layer", None)
        if not layer:
            return
        color = QColorDialog.getColor(QColor(layer.color), self, f"Pick {layer_name} color")
        if color.isValid():
            layer.color = color.name()
            btn_map = {
                "median": self.ens_med_color_btn,
                "percentile": self.ens_pct_color_btn,
                "envelope": self.ens_env_color_btn,
                "individual": self.ens_ind_color_btn,
            }
            btn = btn_map.get(layer_name)
            if btn:
                self._set_ens_color_btn(btn, color.name())
            self._emit_ens_update()

    def _on_ens_changed(self):
        """Handle any change in ensemble properties."""
        if self._updating or not self._current_ensemble:
            return
        ens = self._current_ensemble
        ens.custom_name = self.ens_name_edit.text().strip()
        ens.median_layer.line_width = self.ens_med_width.value()
        ens.percentile_layer.alpha = self.ens_pct_alpha.value()
        ens.envelope_layer.alpha = self.ens_env_alpha.value()
        ens.individual_layer.alpha = self.ens_ind_alpha.value()
        ens.max_individual = self.ens_max_ind.value()
        self._emit_ens_update()

    def _emit_ens_update(self):
        if self._current_uid and self._current_ensemble:
            self.ensemble_updated.emit(self._current_uid, self._current_ensemble)

    # ── Legend helpers ────────────────────────────────────────────

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
            "offset": (self.legend_offset_x.value(), self.legend_offset_y.value()),
            "font_size": self.legend_font_size.value(),
        }
        self.legend_changed.emit(config)
