"""Ensemble sections — mixin providing Ensemble Info + Layer Styles build/handlers."""
import numpy as np
from PySide6.QtWidgets import (
    QLineEdit, QLabel, QHBoxLayout, QPushButton,
    QDoubleSpinBox, QSpinBox, QColorDialog,
)
from PySide6.QtGui import QColor, QPixmap


class EnsembleSectionMixin:
    """Builds and manages Ensemble Info + Layer Styles collapsible sections."""

    def _build_ensemble_info(self, layout):
        self.ens_group, _ec, ens_layout = self._make_section(
            "Ensemble Info", expanded=True
        )

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

    def _build_ensemble_styles(self, layout):
        self.ens_style_group, _esc, ens_style_layout = self._make_section(
            "Layer Styles", expanded=False
        )

        # Median layer
        ens_style_layout.addRow(QLabel("-- Median --"))
        self.ens_med_legend = QLineEdit()
        self.ens_med_legend.setPlaceholderText("Median")
        self.ens_med_legend.editingFinished.connect(self._on_ens_changed)
        ens_style_layout.addRow("Legend:", self.ens_med_legend)
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
        self.ens_pct_legend = QLineEdit()
        self.ens_pct_legend.setPlaceholderText("16-84 Percentile")
        self.ens_pct_legend.editingFinished.connect(self._on_ens_changed)
        ens_style_layout.addRow("Legend:", self.ens_pct_legend)
        pct_row = QHBoxLayout()
        self.ens_pct_color_btn = QPushButton()
        self.ens_pct_color_btn.setFixedSize(28, 28)
        self.ens_pct_color_btn.clicked.connect(
            lambda: self._pick_ens_layer_color("percentile")
        )
        pct_row.addWidget(self.ens_pct_color_btn)
        self.ens_pct_alpha = QSpinBox()
        self.ens_pct_alpha.setRange(2, 100)
        self.ens_pct_alpha.setValue(20)
        self.ens_pct_alpha.setSuffix("%")
        self.ens_pct_alpha.valueChanged.connect(self._on_ens_changed)
        pct_row.addWidget(QLabel("Opacity:"))
        pct_row.addWidget(self.ens_pct_alpha)
        ens_style_layout.addRow("Color:", pct_row)

        # Envelope
        ens_style_layout.addRow(QLabel("-- Envelope --"))
        self.ens_env_legend = QLineEdit()
        self.ens_env_legend.setPlaceholderText("Theoretical Range")
        self.ens_env_legend.editingFinished.connect(self._on_ens_changed)
        ens_style_layout.addRow("Legend:", self.ens_env_legend)
        env_row = QHBoxLayout()
        self.ens_env_color_btn = QPushButton()
        self.ens_env_color_btn.setFixedSize(28, 28)
        self.ens_env_color_btn.clicked.connect(
            lambda: self._pick_ens_layer_color("envelope")
        )
        env_row.addWidget(self.ens_env_color_btn)
        self.ens_env_alpha = QSpinBox()
        self.ens_env_alpha.setRange(2, 100)
        self.ens_env_alpha.setValue(31)
        self.ens_env_alpha.setSuffix("%")
        self.ens_env_alpha.valueChanged.connect(self._on_ens_changed)
        env_row.addWidget(QLabel("Opacity:"))
        env_row.addWidget(self.ens_env_alpha)
        ens_style_layout.addRow("Color:", env_row)

        # Individual curves
        ens_style_layout.addRow(QLabel("-- Individual Curves --"))
        self.ens_ind_legend = QLineEdit()
        self.ens_ind_legend.setPlaceholderText("Profiles")
        self.ens_ind_legend.editingFinished.connect(self._on_ens_changed)
        ens_style_layout.addRow("Legend:", self.ens_ind_legend)
        ind_row = QHBoxLayout()
        self.ens_ind_color_btn = QPushButton()
        self.ens_ind_color_btn.setFixedSize(28, 28)
        self.ens_ind_color_btn.clicked.connect(
            lambda: self._pick_ens_layer_color("individual")
        )
        ind_row.addWidget(self.ens_ind_color_btn)
        self.ens_ind_alpha = QSpinBox()
        self.ens_ind_alpha.setRange(2, 100)
        self.ens_ind_alpha.setValue(10)
        self.ens_ind_alpha.setSuffix("%")
        self.ens_ind_alpha.valueChanged.connect(self._on_ens_changed)
        ind_row.addWidget(QLabel("Opacity:"))
        ind_row.addWidget(self.ens_ind_alpha)
        ens_style_layout.addRow("Color:", ind_row)

        self.ens_max_ind = QSpinBox()
        self.ens_max_ind.setRange(10, 5000)
        self.ens_max_ind.setValue(200)
        self.ens_max_ind.valueChanged.connect(self._on_ens_changed)
        ens_style_layout.addRow("Max Curves:", self.ens_max_ind)

        self.ens_style_group.setVisible(False)
        layout.addWidget(self.ens_style_group)

    def _populate_ensemble(self, ens):
        """Fill the Ensemble Info + Layer Styles sections."""
        self.ens_name_edit.setText(ens.custom_name or ens.name)
        self.ens_models_label.setText(str(ens.n_profiles))
        self.ens_wave_label.setText(ens.wave_type.value)
        self.ens_mode_label.setText(str(ens.mode))

        # Sigma_ln summary
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
        self.ens_med_legend.setText(ens.median_layer.legend_label)
        self._set_ens_color_btn(self.ens_pct_color_btn, ens.percentile_layer.color)
        self.ens_pct_alpha.setValue(round(ens.percentile_layer.alpha * 100 / 255))
        self.ens_pct_legend.setText(ens.percentile_layer.legend_label)
        self._set_ens_color_btn(self.ens_env_color_btn, ens.envelope_layer.color)
        self.ens_env_alpha.setValue(round(ens.envelope_layer.alpha * 100 / 255))
        self.ens_env_legend.setText(ens.envelope_layer.legend_label)
        self._set_ens_color_btn(self.ens_ind_color_btn, ens.individual_layer.color)
        self.ens_ind_alpha.setValue(round(ens.individual_layer.alpha * 100 / 255))
        self.ens_ind_legend.setText(ens.individual_layer.legend_label)
        self.ens_max_ind.setValue(ens.max_individual)

    # ── Ensemble handlers ────────────────────────────────────────

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
        color = QColorDialog.getColor(
            QColor(layer.color), self, f"Pick {layer_name} color"
        )
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
        ens.median_layer.legend_label = self.ens_med_legend.text().strip()
        ens.percentile_layer.alpha = round(self.ens_pct_alpha.value() * 255 / 100)
        ens.percentile_layer.legend_label = self.ens_pct_legend.text().strip()
        ens.envelope_layer.alpha = round(self.ens_env_alpha.value() * 255 / 100)
        ens.envelope_layer.legend_label = self.ens_env_legend.text().strip()
        ens.individual_layer.alpha = round(self.ens_ind_alpha.value() * 255 / 100)
        ens.individual_layer.legend_label = self.ens_ind_legend.text().strip()
        ens.max_individual = self.ens_max_ind.value()
        self._emit_ens_update()

    def _emit_ens_update(self):
        if self._current_uid and self._current_ensemble:
            self.ensemble_updated.emit(self._current_uid, self._current_ensemble)
