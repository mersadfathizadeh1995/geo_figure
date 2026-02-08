"""Curve Info section — mixin providing build + populate + handlers."""
from PySide6.QtWidgets import QLineEdit, QComboBox, QLabel
from geo_figure.core.models import WaveType, SourceType


class CurveInfoMixin:
    """Builds and manages the Curve Info collapsible section."""

    def _build_curve_info(self, layout):
        self.info_group, _ic, info_layout = self._make_section(
            "Curve Info", expanded=True
        )

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

    def _populate_curve_info(self, curve):
        """Fill the Curve Info section from a CurveData object."""
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
        idx = self.subplot_combo.findData(curve.subplot_key)
        if idx >= 0:
            self.subplot_combo.setCurrentIndex(idx)

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

    def _on_name_changed(self):
        if self._updating or not self._current_curve:
            return
        self._current_curve.custom_name = self.name_edit.text().strip()
        self._emit_update()

    def _on_wave_type_changed(self, index):
        if self._updating or not self._current_curve:
            return
        self._current_curve.wave_type = (
            WaveType.RAYLEIGH if index == 0 else WaveType.LOVE
        )
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
