"""Properties panel - right dock showing selected curve/ensemble controls.

Refactored version: each section lives in properties_modules/.
This file provides only the thin shell class and signal wiring.
"""
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QScrollArea
from PySide6.QtCore import Signal, Qt
from typing import Optional

from geo_figure.core.models import CurveData, EnsembleData, VsProfileData, SoilProfile
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
        self._current_soil_profile: Optional[SoilProfile] = None
        self._current_group_uid: Optional[str] = None
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
        self._build_soil_profile_info(layout)

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
        self._current_soil_profile = None

        self.empty_label.setVisible(False)
        self.info_group.setVisible(True)
        self.style_group.setVisible(True)
        self.proc_group.setVisible(True)
        self.ens_group.setVisible(False)
        self.ens_style_group.setVisible(False)
        self.vs_prof_group.setVisible(False)
        self.sp_info_group.setVisible(False)
        self.sp_style_group.setVisible(False)

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
        self._current_soil_profile = None

        self.empty_label.setVisible(False)
        self.info_group.setVisible(False)
        self.style_group.setVisible(False)
        self.proc_group.setVisible(False)
        self.ens_group.setVisible(True)
        self.ens_style_group.setVisible(True)
        self.vs_prof_group.setVisible(False)
        self.sp_info_group.setVisible(False)
        self.sp_style_group.setVisible(False)

        self._populate_ensemble(ens)

        self._updating = False

    def show_vs_profile(self, uid: str, prof, layer_name: str = None):
        """Display properties for the given Vs profile."""
        self._updating = True
        self._current_uid = uid
        self._current_curve = None
        self._current_ensemble = None
        self._current_profile = prof
        self._current_soil_profile = None

        self.empty_label.setVisible(False)
        self.info_group.setVisible(False)
        self.style_group.setVisible(False)
        self.proc_group.setVisible(False)
        self.ens_group.setVisible(False)
        self.ens_style_group.setVisible(False)
        self.vs_prof_group.setVisible(True)
        self.vs_disp_group.setVisible(True)
        self.sp_info_group.setVisible(False)
        self.sp_style_group.setVisible(False)

        self._populate_vs_profile(prof, layer_name)

        self._updating = False

    def show_soil_profile(self, uid: str, profile: SoilProfile, group=None):
        """Display properties for a loaded soil profile."""
        self._updating = True
        self._current_uid = uid
        self._current_curve = None
        self._current_ensemble = None
        self._current_profile = None
        self._current_soil_profile = profile
        self._current_group_uid = None

        self.empty_label.setVisible(False)
        self.info_group.setVisible(False)
        self.style_group.setVisible(False)
        self.proc_group.setVisible(False)
        self.ens_group.setVisible(False)
        self.ens_style_group.setVisible(False)
        self.vs_prof_group.setVisible(False)
        self.vs_disp_group.setVisible(False)
        self.vs_layer_group.setVisible(False)
        self.sp_info_group.setVisible(True)
        self.sp_style_group.setVisible(True)
        self.sp_stats_group.setVisible(False)

        self._populate_soil_profile(profile)

        # Show group stats section if this profile belongs to a group with multiple profiles
        if group is not None and len(group.profiles) > 1:
            self.show_soil_profile_group(group.uid, group)

        self._updating = False

    def clear(self):
        """Clear the panel."""
        self._current_uid = None
        self._current_curve = None
        self._current_ensemble = None
        self._current_profile = None
        self._current_soil_profile = None
        self._current_group_uid = None
        self.empty_label.setVisible(True)
        self.info_group.setVisible(False)
        self.style_group.setVisible(False)
        self.proc_group.setVisible(False)
        self.ens_group.setVisible(False)
        self.ens_style_group.setVisible(False)
        self.vs_prof_group.setVisible(False)
        self.vs_disp_group.setVisible(False)
        self.vs_layer_group.setVisible(False)
        self.sp_info_group.setVisible(False)
        self.sp_style_group.setVisible(False)
        self.sp_stats_group.setVisible(False)

    # ── Emit helpers ─────────────────────────────────────────────

    def _emit_update(self):
        if self._current_uid and self._current_curve:
            self.curve_updated.emit(self._current_uid, self._current_curve)

    # ── Vs Profile section ───────────────────────────────────────

    vs_profile_updated = Signal(str, object)  # uid, VsProfileData
    soil_profile_updated = Signal(str, object)  # uid, SoilProfile
    group_stats_requested = Signal(str)  # group uid

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

    # ── Soil Profile section (loaded from file) ──────────────────

    def _build_soil_profile_info(self, parent_layout):
        """Build the soil profile info + display style sections."""
        from PySide6.QtWidgets import (
            QDoubleSpinBox, QSpinBox, QPushButton, QHBoxLayout, QComboBox,
            QLineEdit,
        )

        # Info section
        self.sp_info_group, content, form = self._make_section(
            "Soil Profile Info", expanded=True,
        )
        self.sp_info_group.setVisible(False)

        self.sp_name_edit = QLineEdit()
        self.sp_name_edit.editingFinished.connect(self._on_sp_name_changed)
        form.addRow("Name:", self.sp_name_edit)
        self.sp_layers_label = QLabel("-")
        form.addRow("Layers:", self.sp_layers_label)
        self.sp_depth_label = QLabel("-")
        form.addRow("Depth range:", self.sp_depth_label)
        self.sp_vs_range_label = QLabel("-")
        form.addRow("Value range:", self.sp_vs_range_label)
        self.sp_has_vp_label = QLabel("-")
        form.addRow("Has Vp:", self.sp_has_vp_label)
        self.sp_has_rho_label = QLabel("-")
        form.addRow("Has Density:", self.sp_has_rho_label)
        self.sp_model_id_label = QLabel("-")
        form.addRow("Model ID:", self.sp_model_id_label)

        # Render-as combo (Vs / Vp / Density)
        self.sp_render_combo = QComboBox()
        self.sp_render_combo.addItems(["Vs", "Vp", "Density"])
        self.sp_render_combo.currentTextChanged.connect(self._on_sp_render_changed)
        form.addRow("Render as:", self.sp_render_combo)

        parent_layout.addWidget(self.sp_info_group)

        # Style section
        self.sp_style_group, style_content, style_form = self._make_section(
            "Profile Style", expanded=True,
        )
        self.sp_style_group.setVisible(False)

        color_row = QHBoxLayout()
        self.sp_color_btn = QPushButton()
        self.sp_color_btn.setFixedSize(28, 28)
        self.sp_color_btn.clicked.connect(self._pick_sp_color)
        color_row.addWidget(self.sp_color_btn)
        self.sp_color_hex = QLabel("#2196F3")
        color_row.addWidget(self.sp_color_hex)
        color_row.addStretch()
        style_form.addRow("Color:", color_row)

        self.sp_width_spin = QDoubleSpinBox()
        self.sp_width_spin.setRange(0.5, 10.0)
        self.sp_width_spin.setValue(1.5)
        self.sp_width_spin.setSingleStep(0.5)
        self.sp_width_spin.valueChanged.connect(self._on_sp_style_changed)
        style_form.addRow("Width:", self.sp_width_spin)

        self.sp_alpha_spin = QSpinBox()
        self.sp_alpha_spin.setRange(0, 100)
        self.sp_alpha_spin.setValue(100)
        self.sp_alpha_spin.setSuffix("%")
        self.sp_alpha_spin.valueChanged.connect(self._on_sp_style_changed)
        style_form.addRow("Opacity:", self.sp_alpha_spin)

        parent_layout.addWidget(self.sp_style_group)

        # Group statistics section (visible when a group is selected)
        self.sp_stats_group, stats_content, stats_form = self._make_section(
            "Group Statistics", expanded=True,
        )
        self.sp_stats_group.setVisible(False)

        self.sp_compute_stats_btn = QPushButton("Compute Statistics")
        self.sp_compute_stats_btn.clicked.connect(self._on_compute_group_stats)
        stats_form.addRow(self.sp_compute_stats_btn)

        self.sp_stats_status = QLabel("Not computed")
        stats_form.addRow("Status:", self.sp_stats_status)

        from PySide6.QtWidgets import QCheckBox

        # -- Individual profiles toggle --
        self.sp_show_individual_check = QCheckBox("Show Individual Profiles")
        self.sp_show_individual_check.setChecked(True)
        self.sp_show_individual_check.toggled.connect(self._on_sp_stats_toggled)
        stats_form.addRow(self.sp_show_individual_check)

        # -- Median controls --
        self.sp_show_median_check = QCheckBox("Show Median")
        self.sp_show_median_check.setChecked(True)
        self.sp_show_median_check.toggled.connect(self._on_sp_stats_toggled)
        stats_form.addRow(self.sp_show_median_check)

        med_row = QHBoxLayout()
        med_row.addWidget(QLabel("Color:"))
        self.sp_median_color_btn = QPushButton()
        self.sp_median_color_btn.setFixedSize(28, 28)
        self.sp_median_color_btn.clicked.connect(self._pick_median_color)
        med_row.addWidget(self.sp_median_color_btn)
        self.sp_median_color_hex = QLabel("#D32F2F")
        med_row.addWidget(self.sp_median_color_hex)
        med_row.addStretch()
        stats_form.addRow(med_row)

        self.sp_median_width_spin = QDoubleSpinBox()
        self.sp_median_width_spin.setRange(0.5, 8.0)
        self.sp_median_width_spin.setSingleStep(0.5)
        self.sp_median_width_spin.setValue(2.5)
        self.sp_median_width_spin.valueChanged.connect(self._on_sp_stats_toggled)
        stats_form.addRow("Median Width:", self.sp_median_width_spin)

        # -- Percentile controls --
        self.sp_show_percentile_check = QCheckBox("Show 5-95 Percentile")
        self.sp_show_percentile_check.setChecked(True)
        self.sp_show_percentile_check.toggled.connect(self._on_sp_stats_toggled)
        stats_form.addRow(self.sp_show_percentile_check)

        pct_row = QHBoxLayout()
        pct_row.addWidget(QLabel("Color:"))
        self.sp_pct_color_btn = QPushButton()
        self.sp_pct_color_btn.setFixedSize(28, 28)
        self.sp_pct_color_btn.clicked.connect(self._pick_percentile_color)
        pct_row.addWidget(self.sp_pct_color_btn)
        self.sp_pct_color_hex = QLabel("#E57373")
        pct_row.addWidget(self.sp_pct_color_hex)
        pct_row.addStretch()
        stats_form.addRow(pct_row)

        self.sp_pct_alpha_spin = QSpinBox()
        self.sp_pct_alpha_spin.setRange(0, 100)
        self.sp_pct_alpha_spin.setValue(31)
        self.sp_pct_alpha_spin.setSuffix("%")
        self.sp_pct_alpha_spin.valueChanged.connect(self._on_sp_stats_toggled)
        stats_form.addRow("Band Opacity:", self.sp_pct_alpha_spin)

        parent_layout.addWidget(self.sp_stats_group)

    def _populate_soil_profile(self, profile: SoilProfile):
        """Fill soil profile info and style fields."""
        import numpy as np

        self.sp_name_edit.setText(profile.custom_name or profile.name)
        self.sp_layers_label.setText(str(profile.n_layers))
        self.sp_depth_label.setText(f"0 - {profile.max_depth:.1f} m")

        vals = profile.active_values
        if vals is not None and len(vals) > 0:
            finite = vals[np.isfinite(vals)]
            if len(finite) > 0:
                self.sp_vs_range_label.setText(f"{np.min(finite):.1f} - {np.max(finite):.1f} m/s")
            else:
                self.sp_vs_range_label.setText("N/A")
        else:
            self.sp_vs_range_label.setText("N/A")

        self.sp_has_vp_label.setText("Yes" if profile.vp is not None else "No")
        self.sp_has_rho_label.setText("Yes" if profile.density is not None else "No")
        self.sp_model_id_label.setText(profile.model_id or "-")

        # Render-as combo
        self._updating = True
        available = []
        if profile.vs is not None:
            available.append("Vs")
        if profile.vp is not None:
            available.append("Vp")
        if profile.density is not None:
            available.append("Density")
        self.sp_render_combo.clear()
        self.sp_render_combo.addItems(available if available else ["Vs"])
        # Select current render mode
        render_map = {"vs": "Vs", "vp": "Vp", "density": "Density"}
        current_text = render_map.get(
            getattr(profile, "render_property", "vs"), "Vs",
        )
        idx = self.sp_render_combo.findText(current_text)
        if idx >= 0:
            self.sp_render_combo.setCurrentIndex(idx)

        # Style
        self._update_sp_color_btn(profile.color)
        self.sp_width_spin.setValue(profile.line_width)
        self.sp_alpha_spin.setValue(round(profile.alpha * 100 / 255))
        self._updating = False

    def _update_sp_color_btn(self, color_str: str):
        from PySide6.QtGui import QColor, QPixmap
        pixmap = QPixmap(24, 24)
        pixmap.fill(QColor(color_str))
        self.sp_color_btn.setIcon(pixmap)
        self.sp_color_btn.setStyleSheet(
            f"background-color: {color_str}; border: 1px solid #555555;"
        )
        self.sp_color_hex.setText(color_str)

    def _pick_sp_color(self):
        from PySide6.QtWidgets import QColorDialog
        from PySide6.QtGui import QColor
        if not self._current_soil_profile:
            return
        color = QColorDialog.getColor(
            QColor(self._current_soil_profile.color), self, "Pick Profile Color",
        )
        if color.isValid():
            self._current_soil_profile.color = color.name()
            self._update_sp_color_btn(color.name())
            self.soil_profile_updated.emit(
                self._current_uid, self._current_soil_profile,
            )

    def _on_sp_style_changed(self):
        if self._updating or not self._current_soil_profile:
            return
        prof = self._current_soil_profile
        prof.line_width = self.sp_width_spin.value()
        prof.alpha = round(self.sp_alpha_spin.value() * 255 / 100)
        self.soil_profile_updated.emit(self._current_uid, prof)

    def _on_sp_name_changed(self):
        if self._updating or not self._current_soil_profile:
            return
        self._current_soil_profile.custom_name = self.sp_name_edit.text()
        self.soil_profile_updated.emit(
            self._current_uid, self._current_soil_profile,
        )

    def _on_sp_render_changed(self, text):
        if self._updating or not self._current_soil_profile:
            return
        render_map = {"Vs": "vs", "Vp": "vp", "Density": "density"}
        self._current_soil_profile.render_property = render_map.get(text, "vs")
        self.soil_profile_updated.emit(
            self._current_uid, self._current_soil_profile,
        )

    # ── Group statistics handlers ──────────────────────────────────

    def _on_compute_group_stats(self):
        """Emit signal to compute group statistics."""
        if self._current_group_uid:
            self.group_stats_requested.emit(self._current_group_uid)

    def _on_sp_stats_toggled(self):
        """Update group statistics display toggles."""
        if self._updating or not self._current_group_uid:
            return
        self.group_stats_requested.emit(self._current_group_uid)

    def _pick_median_color(self):
        from PySide6.QtWidgets import QColorDialog
        from PySide6.QtGui import QColor
        if not self._current_group_uid:
            return
        color = QColorDialog.getColor(
            QColor(self.sp_median_color_hex.text()),
            self, "Median Color",
        )
        if color.isValid():
            self._update_stats_color_btn(
                self.sp_median_color_btn, self.sp_median_color_hex,
                color.name(),
            )
            if not self._updating:
                self.group_stats_requested.emit(self._current_group_uid)

    def _pick_percentile_color(self):
        from PySide6.QtWidgets import QColorDialog
        from PySide6.QtGui import QColor
        if not self._current_group_uid:
            return
        color = QColorDialog.getColor(
            QColor(self.sp_pct_color_hex.text()),
            self, "Percentile Color",
        )
        if color.isValid():
            self._update_stats_color_btn(
                self.sp_pct_color_btn, self.sp_pct_color_hex,
                color.name(),
            )
            if not self._updating:
                self.group_stats_requested.emit(self._current_group_uid)

    def _update_stats_color_btn(self, btn, hex_label, color_str):
        from PySide6.QtGui import QColor, QPixmap
        pixmap = QPixmap(24, 24)
        pixmap.fill(QColor(color_str))
        btn.setIcon(pixmap)
        btn.setStyleSheet(
            f"background-color: {color_str}; border: 1px solid #555555;"
        )
        hex_label.setText(color_str)

    def show_soil_profile_group(self, uid: str, group):
        """Show properties for a SoilProfileGroup (statistics controls)."""
        self._current_group_uid = uid
        self.sp_stats_group.setVisible(True)
        if group.has_statistics:
            self.sp_stats_status.setText(
                f"Computed ({len(group.depth_grid)} depth points)"
            )
        else:
            self.sp_stats_status.setText("Not computed")
        self._updating = True
        self.sp_show_median_check.setChecked(group.show_median)
        self.sp_show_percentile_check.setChecked(group.show_percentile)
        self.sp_show_individual_check.setChecked(group.show_individual)
        self.sp_median_width_spin.setValue(group.median_line_width)
        self._update_stats_color_btn(
            self.sp_median_color_btn, self.sp_median_color_hex,
            group.median_color,
        )
        self._update_stats_color_btn(
            self.sp_pct_color_btn, self.sp_pct_color_hex,
            group.percentile_color,
        )
        self.sp_pct_alpha_spin.setValue(round(group.percentile_alpha * 100 / 255))
        self._updating = False

    def hide_group_stats(self):
        """Hide the group stats section."""
        self.sp_stats_group.setVisible(False)
        self._current_group_uid = None
