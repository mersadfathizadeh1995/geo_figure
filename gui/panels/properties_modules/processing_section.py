"""Processing section — mixin providing build + populate + handlers + range table."""
from PySide6.QtWidgets import (
    QComboBox, QDoubleSpinBox, QSpinBox, QCheckBox, QLabel,
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView,
)


class ProcessingSectionMixin:
    """Builds and manages the Processing collapsible section."""

    def _build_processing(self, layout):
        self.proc_group, _pc, proc_layout = self._make_section(
            "Processing", expanded=False
        )

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
        self.range_table.setHorizontalHeaderLabels(
            ["From (Hz)", "To (Hz)", "StdDev"]
        )
        self.range_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.Stretch
        )
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

    def _populate_processing(self, curve):
        """Fill the Processing section from a CurveData object."""
        mode_map = {"file": 0, "fixed_logstd": 1, "fixed_cov": 2, "range": 3}
        self.stddev_combo.setCurrentIndex(mode_map.get(curve.stddev_mode, 0))
        self._update_stddev_visibility(self.stddev_combo.currentIndex())
        if curve.stddev_mode == "fixed_logstd":
            self.fixed_value_spin.setValue(curve.fixed_logstd)
        elif curve.stddev_mode == "fixed_cov":
            self.fixed_value_spin.setValue(curve.fixed_cov)
        self.resample_cb.setChecked(curve.resample_enabled)
        self.resample_n.setValue(curve.resample_n_points)
        method_idx = 0 if curve.resample_method == "log" else 1
        self.resample_method.setCurrentIndex(method_idx)
        show_resample = curve.resample_enabled
        self.resample_n.setVisible(show_resample)
        self.resample_n_label.setVisible(show_resample)
        self.resample_method.setVisible(show_resample)
        self.resample_method_label.setVisible(show_resample)
        self._populate_range_table(curve.stddev_ranges)

    # ── StdDev mode handling ─────────────────────────────────────

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
            self.range_table.setItem(
                row, 0, QTableWidgetItem(f"{fmin:.2f}")
            )
            self.range_table.setItem(
                row, 1, QTableWidgetItem(f"{fmax:.2f}")
            )
            self.range_table.setItem(
                row, 2, QTableWidgetItem(f"{val:.3f}")
            )
        self.range_table.blockSignals(False)

    def _add_range_row(self):
        """Add a new empty row to the range table."""
        row = self.range_table.rowCount()
        fmin = 0.0
        if row > 0:
            prev_to = self.range_table.item(row - 1, 1)
            if prev_to:
                try:
                    fmin = float(prev_to.text())
                except ValueError:
                    pass
        self.range_table.insertRow(row)
        self.range_table.setItem(
            row, 0, QTableWidgetItem(f"{fmin:.2f}")
        )
        self.range_table.setItem(
            row, 1, QTableWidgetItem(f"{fmin + 5:.2f}")
        )
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
