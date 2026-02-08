"""Properties panel - right dock showing selected curve/ensemble controls.

Refactored version: each section lives in properties_modules/.
This file provides only the thin shell class and signal wiring.
"""
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QScrollArea
from PySide6.QtCore import Signal, Qt
from typing import Optional

from geo_figure.core.models import CurveData, EnsembleData, VsProfileData
from geo_figure.gui.panels.properties_modules import (
    CollapsibleSection,
    CurveInfoMixin,
    StyleSectionMixin,
    ProcessingSectionMixin,
    EnsembleSectionMixin,
)


class PropertiesPanel(
    CurveInfoMixin,
    StyleSectionMixin,
    ProcessingSectionMixin,
    EnsembleSectionMixin,
    QWidget,
):
    """Panel showing editable properties for the selected curve or ensemble."""

    curve_updated = Signal(str, CurveData)
    subplot_change_requested = Signal(str, str)
    ensemble_updated = Signal(str, EnsembleData)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_uid: Optional[str] = None
        self._current_curve: Optional[CurveData] = None
        self._current_ensemble: Optional[EnsembleData] = None
        self._current_profile: Optional[VsProfileData] = None
        self._updating = False
        self._setup_ui()

    # ── Collapsible group helper ─────────────────────────────────

    @staticmethod
    def _make_section(title: str, expanded: bool = True):
        """Create a CollapsibleSection with arrow-based toggle."""
        section = CollapsibleSection(title, expanded=expanded)
        return section, section.content, section.form

    # ── UI setup ─────────────────────────────────────────────────

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(4, 4, 4, 4)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setSpacing(8)

        # Empty state
        self.empty_label = QLabel("Select a curve to view properties")
        self.empty_label.setAlignment(Qt.AlignCenter)
        self.empty_label.setStyleSheet("color: #666666; font-style: italic;")
        layout.addWidget(self.empty_label)

        # Delegate section building to each mixin
        self._build_curve_info(layout)
        self._build_style(layout)
        self._build_processing(layout)
        self._build_ensemble_info(layout)
        self._build_ensemble_styles(layout)
        self._build_vs_profile_info(layout)

        layout.addStretch()
        scroll.setWidget(container)
        main_layout.addWidget(scroll)

    # ── Public API ───────────────────────────────────────────────

    def show_curve(self, uid: str, curve: CurveData):
        """Display properties for the given curve."""
        self._updating = True
        self._current_uid = uid
        self._current_curve = curve
        self._current_ensemble = None
        self._current_profile = None

        self.empty_label.setVisible(False)
        self.info_group.setVisible(True)
        self.style_group.setVisible(True)
        self.proc_group.setVisible(True)
        self.ens_group.setVisible(False)
        self.ens_style_group.setVisible(False)
        self.vs_prof_group.setVisible(False)

        self._populate_curve_info(curve)
        self._populate_style(curve)
        self._populate_processing(curve)

        self._updating = False

    def show_ensemble(self, uid: str, ens: EnsembleData):
        """Display properties for the given ensemble."""
        self._updating = True
        self._current_uid = uid
        self._current_curve = None
        self._current_ensemble = ens
        self._current_profile = None

        self.empty_label.setVisible(False)
        self.info_group.setVisible(False)
        self.style_group.setVisible(False)
        self.proc_group.setVisible(False)
        self.ens_group.setVisible(True)
        self.ens_style_group.setVisible(True)
        self.vs_prof_group.setVisible(False)

        self._populate_ensemble(ens)

        self._updating = False

    def show_vs_profile(self, uid: str, prof, layer_name: str = None):
        """Display properties for the given Vs profile."""
        self._updating = True
        self._current_uid = uid
        self._current_curve = None
        self._current_ensemble = None
        self._current_profile = prof

        self.empty_label.setVisible(False)
        self.info_group.setVisible(False)
        self.style_group.setVisible(False)
        self.proc_group.setVisible(False)
        self.ens_group.setVisible(False)
        self.ens_style_group.setVisible(False)
        self.vs_prof_group.setVisible(True)
        self.vs_disp_group.setVisible(True)

        self._populate_vs_profile(prof, layer_name)

        self._updating = False

    def clear(self):
        """Clear the panel."""
        self._current_uid = None
        self._current_curve = None
        self._current_ensemble = None
        self._current_profile = None
        self.empty_label.setVisible(True)
        self.info_group.setVisible(False)
        self.style_group.setVisible(False)
        self.proc_group.setVisible(False)
        self.ens_group.setVisible(False)
        self.ens_style_group.setVisible(False)
        self.vs_prof_group.setVisible(False)
        self.vs_disp_group.setVisible(False)
        self.vs_layer_group.setVisible(False)

    # ── Emit helpers ─────────────────────────────────────────────

    def _emit_update(self):
        if self._current_uid and self._current_curve:
            self.curve_updated.emit(self._current_uid, self._current_curve)

    # ── Vs Profile section ───────────────────────────────────────

    vs_profile_updated = Signal(str, object)  # uid, VsProfileData

    def _build_vs_profile_info(self, parent_layout):
        """Build the Vs profile info + display settings + layer style sections."""
        from PySide6.QtWidgets import (
            QCheckBox, QDoubleSpinBox, QSpinBox, QPushButton, QHBoxLayout,
        )
        from PySide6.QtGui import QColor, QPixmap

        # Info section
        self.vs_prof_group, content, form = self._make_section(
            "Vs Profile Info", expanded=True
        )
        self.vs_prof_group.setVisible(False)

        self.vs_name_label = QLabel("-")
        form.addRow("Name:", self.vs_name_label)
        self.vs_type_label = QLabel("-")
        form.addRow("Type:", self.vs_type_label)
        self.vs_models_label = QLabel("-")
        form.addRow("Models:", self.vs_models_label)
        self.vs_depth_label = QLabel("-")
        form.addRow("Max Depth:", self.vs_depth_label)
        self.vsn_label = QLabel("-")
        form.addRow("VsN:", self.vsn_label)

        parent_layout.addWidget(self.vs_prof_group)

        # Display settings section
        self.vs_disp_group, disp_content, disp_form = self._make_section(
            "Vs Display Settings", expanded=False
        )
        self.vs_disp_group.setVisible(False)

        self.vs_show_median = QCheckBox("Show Median")
        self.vs_show_median.setChecked(True)
        self.vs_show_median.toggled.connect(self._on_vs_display_changed)
        disp_form.addRow(self.vs_show_median)

        self.vs_show_percentile = QCheckBox("Show Percentile Band")
        self.vs_show_percentile.setChecked(True)
        self.vs_show_percentile.toggled.connect(self._on_vs_display_changed)
        disp_form.addRow(self.vs_show_percentile)

        self.vs_show_individual = QCheckBox("Show Individual Profiles")
        self.vs_show_individual.setChecked(False)
        self.vs_show_individual.toggled.connect(self._on_vs_display_changed)
        disp_form.addRow(self.vs_show_individual)

        self.vs_show_sigma = QCheckBox("Show Sigma_ln")
        self.vs_show_sigma.setChecked(True)
        self.vs_show_sigma.toggled.connect(self._on_vs_display_changed)
        disp_form.addRow(self.vs_show_sigma)

        parent_layout.addWidget(self.vs_disp_group)

        # Layer style section (shows when a specific layer is clicked)
        self.vs_layer_group, layer_content, layer_form = self._make_section(
            "Layer Style", expanded=True
        )
        self.vs_layer_group.setVisible(False)

        self.vs_layer_name_label = QLabel("-")
        layer_form.addRow("Layer:", self.vs_layer_name_label)

        color_row = QHBoxLayout()
        self.vs_layer_color_btn = QPushButton()
        self.vs_layer_color_btn.setFixedSize(28, 28)
        self.vs_layer_color_btn.clicked.connect(self._pick_vs_layer_color)
        color_row.addWidget(self.vs_layer_color_btn)
        self.vs_layer_color_hex = QLabel("#000000")
        color_row.addWidget(self.vs_layer_color_hex)
        color_row.addStretch()
        layer_form.addRow("Color:", color_row)

        self.vs_layer_width_spin = QDoubleSpinBox()
        self.vs_layer_width_spin.setRange(0.5, 10.0)
        self.vs_layer_width_spin.setValue(2.0)
        self.vs_layer_width_spin.setSingleStep(0.5)
        self.vs_layer_width_spin.valueChanged.connect(self._on_vs_layer_style_changed)
        layer_form.addRow("Width:", self.vs_layer_width_spin)

        self.vs_layer_alpha_spin = QSpinBox()
        self.vs_layer_alpha_spin.setRange(0, 100)
        self.vs_layer_alpha_spin.setValue(100)
        self.vs_layer_alpha_spin.setSuffix("%")
        self.vs_layer_alpha_spin.valueChanged.connect(self._on_vs_layer_style_changed)
        layer_form.addRow("Opacity:", self.vs_layer_alpha_spin)

        parent_layout.addWidget(self.vs_layer_group)

        self._vs_selected_layer = None  # "median", "percentile", "individual", "sigma"

    def _populate_vs_profile(self, prof, layer_name=None):
        """Fill Vs profile info fields."""
        self.vs_name_label.setText(prof.display_name)
        ptype = {"vs": "Vs (Shear Wave)", "vp": "Vp (Compression)", "rho": "Density"}.get(
            prof.profile_type, prof.profile_type
        )
        self.vs_type_label.setText(ptype)
        self.vs_models_label.setText(str(prof.n_profiles))

        # Compute actual data depth from profiles
        data_depth = 0.0
        if prof.profiles:
            import numpy as np
            for d, v in prof.profiles:
                finite = d[np.isfinite(d) & (d > 0)]
                if len(finite) > 0:
                    data_depth = max(data_depth, float(np.max(finite)))
        if data_depth <= 0:
            data_depth = prof.depth_max_plot
        self.vs_depth_label.setText(f"{data_depth:.1f} m")

        # Show VsN based on unit context (default metric -> Vs30)
        if prof.vs30_mean is not None:
            vsn_txt = f"Vs30 = {prof.vs30_mean:.1f} m/s"
            if prof.vs30_std is not None:
                vsn_txt += f" (std={prof.vs30_std:.1f})"
            self.vsn_label.setText(vsn_txt)
        elif prof.vs100_mean is not None:
            vsn_txt = f"Vs100 = {prof.vs100_mean:.1f} ft/s"
            if prof.vs100_std is not None:
                vsn_txt += f" (std={prof.vs100_std:.1f})"
            self.vsn_label.setText(vsn_txt)
        else:
            self.vsn_label.setText("N/A")

        # Sync display toggles
        self._updating = True
        self.vs_show_median.setChecked(prof.median_layer.visible)
        self.vs_show_percentile.setChecked(prof.percentile_layer.visible)
        self.vs_show_individual.setChecked(prof.individual_layer.visible)
        self.vs_show_sigma.setChecked(prof.sigma_layer.visible)
        self._updating = False

        # Layer style section
        if layer_name:
            self._vs_selected_layer = layer_name
            layer = getattr(prof, f"{layer_name}_layer", None)
            if layer:
                self.vs_layer_group.setVisible(True)
                labels = {
                    "median": "Median",
                    "percentile": "Percentile Band",
                    "individual": "Individual Profiles",
                    "sigma": "Sigma_ln",
                }
                self.vs_layer_name_label.setText(labels.get(layer_name, layer_name))
                self._updating = True
                self._update_vs_layer_color_btn(layer.color)
                self.vs_layer_width_spin.setValue(layer.line_width)
                self.vs_layer_alpha_spin.setValue(round(layer.alpha * 100 / 255))
                self._updating = False
        else:
            self._vs_selected_layer = None
            self.vs_layer_group.setVisible(False)

    def _update_vs_layer_color_btn(self, color_str: str):
        """Update the color button appearance."""
        from PySide6.QtGui import QColor, QPixmap
        pixmap = QPixmap(24, 24)
        pixmap.fill(QColor(color_str))
        self.vs_layer_color_btn.setIcon(pixmap)
        self.vs_layer_color_btn.setStyleSheet(
            f"background-color: {color_str}; border: 1px solid #555555;"
        )
        self.vs_layer_color_hex.setText(color_str)

    def _pick_vs_layer_color(self):
        """Open color dialog for the selected Vs layer."""
        from PySide6.QtWidgets import QColorDialog
        from PySide6.QtGui import QColor
        if not self._current_profile or not self._vs_selected_layer:
            return
        layer = getattr(self._current_profile, f"{self._vs_selected_layer}_layer", None)
        if not layer:
            return
        color = QColorDialog.getColor(QColor(layer.color), self, "Pick Layer Color")
        if color.isValid():
            layer.color = color.name()
            self._update_vs_layer_color_btn(color.name())
            self.vs_profile_updated.emit(self._current_uid, self._current_profile)

    def _on_vs_display_changed(self):
        """Handle Vs profile display settings change."""
        if self._updating or not self._current_profile:
            return
        prof = self._current_profile
        prof.median_layer.visible = self.vs_show_median.isChecked()
        prof.percentile_layer.visible = self.vs_show_percentile.isChecked()
        prof.individual_layer.visible = self.vs_show_individual.isChecked()
        prof.sigma_layer.visible = self.vs_show_sigma.isChecked()
        self.vs_profile_updated.emit(self._current_uid, prof)

    def _on_vs_layer_style_changed(self):
        """Handle layer style change from width/alpha controls."""
        if self._updating or not self._current_profile or not self._vs_selected_layer:
            return
        prof = self._current_profile
        layer = getattr(prof, f"{self._vs_selected_layer}_layer", None)
        if not layer:
            return
        layer.line_width = self.vs_layer_width_spin.value()
        layer.alpha = round(self.vs_layer_alpha_spin.value() * 255 / 100)
        self.vs_profile_updated.emit(self._current_uid, prof)
