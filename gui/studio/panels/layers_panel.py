"""Layers panel — tree view of all data layers with visibility toggles."""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QTreeWidget, QTreeWidgetItem, QLabel,
    QGroupBox, QHeaderView,
)
from PySide6.QtCore import Signal, Qt

from geo_figure.core.models import FigureState


class LayersPanel(QWidget):
    """Shows all data layers grouped by subplot, with visibility checkboxes."""

    visibility_changed = Signal()
    axis_label_toggled = Signal(str, str, bool)  # subplot_key, "x"/"y", visible

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(6)

        grp = QGroupBox("Data Layers")
        grp_layout = QVBoxLayout(grp)
        grp_layout.setContentsMargins(4, 4, 4, 4)

        self._tree = QTreeWidget()
        self._tree.setHeaderLabels(["Layer"])
        self._tree.header().setStretchLastSection(True)
        self._tree.header().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        self._tree.setRootIsDecorated(True)
        self._tree.setIndentation(16)
        self._tree.itemChanged.connect(self._on_item_changed)
        grp_layout.addWidget(self._tree)

        layout.addWidget(grp)

        self._state = None

    def populate(self, state: FigureState, subplot_info: list = None,
                 settings=None):
        """Fill the tree from a FigureState, grouped by subplot.

        Parameters
        ----------
        state : FigureState
            Data to display.
        subplot_info : list, optional
            [(key, display_name), ...] for all subplots.
        settings : StudioSettings, optional
            Used to read current axis label visibility.
        """
        self._state = state
        self._tree.blockSignals(True)
        self._tree.clear()

        if subplot_info is None:
            subplot_info = [("main", "Main")]

        sp_keys = [k for k, _ in subplot_info]

        for sp_key, sp_name in subplot_info:
            sp_item = QTreeWidgetItem(self._tree)
            sp_item.setText(0, sp_name or sp_key)
            sp_item.setExpanded(True)
            font = sp_item.font(0)
            font.setBold(True)
            sp_item.setFont(0, font)

            # Axis label toggles
            for axis_id, label_text in [("x", "X Axis Label"),
                                         ("y", "Y Axis Label")]:
                lbl_item = QTreeWidgetItem(sp_item)
                lbl_item.setText(0, label_text)
                vis = True
                if settings:
                    acfg = settings.axis_for(sp_key)
                    vis = acfg.show_x_label if axis_id == "x" else acfg.show_y_label
                lbl_item.setCheckState(0, Qt.Checked if vis else Qt.Unchecked)
                lbl_item.setData(0, Qt.UserRole, ("axis_label", sp_key, axis_id))

            # Curves in this subplot
            for c in state.curves:
                if c.subplot_key != sp_key:
                    continue
                self._add_curve_item(sp_item, c)

            # Ensembles in this subplot
            for e in state.ensembles:
                if e.subplot_key != sp_key:
                    continue
                self._add_ensemble_item(sp_item, e)

            # Vs Profiles in this subplot
            for p in state.vs_profiles:
                if not self._vs_matches(p.subplot_key, sp_key, sp_keys):
                    continue
                self._add_vs_item(sp_item, p)

        self._tree.blockSignals(False)

    # ── Item builders ─────────────────────────────────────────────

    @staticmethod
    def _vs_matches(prof_key: str, sp_key: str, all_keys: list) -> bool:
        """Check if a VsProfile belongs under a given subplot node."""
        if prof_key == sp_key:
            return True
        if prof_key not in all_keys and sp_key in ("vs_profile", "main"):
            return True
        return False

    def _add_curve_item(self, parent, c):
        item = QTreeWidgetItem(parent)
        item.setText(0, c.display_name)
        item.setCheckState(0, Qt.Checked if c.visible else Qt.Unchecked)
        item.setData(0, Qt.UserRole, ("curve", c.uid))
        try:
            from PySide6.QtGui import QColor
            item.setForeground(0, QColor(c.color))
        except Exception:
            pass

    def _add_ensemble_item(self, parent, e):
        item = QTreeWidgetItem(parent)
        item.setText(0, e.display_name)
        item.setCheckState(0, Qt.Checked)
        item.setData(0, Qt.UserRole, ("ensemble", e.uid))
        for lname, layer in [
            ("Median", e.median_layer),
            ("Percentile", e.percentile_layer),
            ("Envelope", e.envelope_layer),
            ("Individual", e.individual_layer),
        ]:
            sub = QTreeWidgetItem(item)
            sub.setText(0, lname)
            sub.setCheckState(0, Qt.Checked if layer.visible else Qt.Unchecked)
            sub.setData(0, Qt.UserRole, ("ensemble_layer", e.uid, lname.lower()))

    def _add_vs_item(self, parent, p):
        item = QTreeWidgetItem(parent)
        item.setText(0, p.display_name)
        item.setCheckState(0, Qt.Checked)
        item.setData(0, Qt.UserRole, ("vs_profile", p.uid))
        for lname, layer in [
            ("Median", p.median_layer),
            ("Percentile", p.percentile_layer),
            ("Individual", p.individual_layer),
            ("Sigma", p.sigma_layer),
        ]:
            sub = QTreeWidgetItem(item)
            sub.setText(0, lname)
            sub.setCheckState(0, Qt.Checked if layer.visible else Qt.Unchecked)
            sub.setData(0, Qt.UserRole, ("vs_layer", p.uid, lname.lower()))

    # ── Checkbox handler ──────────────────────────────────────────

    def _on_item_changed(self, item, column):
        """Handle checkbox toggle — update the model object."""
        if column != 0 or self._state is None:
            return
        data = item.data(0, Qt.UserRole)
        if not data:
            return
        checked = item.checkState(0) == Qt.Checked

        kind = data[0]

        if kind == "axis_label":
            sp_key, axis_id = data[1], data[2]
            self.axis_label_toggled.emit(sp_key, axis_id, checked)
            return

        if kind == "curve":
            uid = data[1]
            for c in self._state.curves:
                if c.uid == uid:
                    c.visible = checked
                    break
        elif kind == "ensemble_layer":
            uid, layer_name = data[1], data[2]
            for e in self._state.ensembles:
                if e.uid == uid:
                    layer = getattr(e, f"{layer_name}_layer", None)
                    if layer:
                        layer.visible = checked
                    break
        elif kind == "vs_layer":
            uid, layer_name = data[1], data[2]
            for p in self._state.vs_profiles:
                if p.uid == uid:
                    layer = getattr(p, f"{layer_name}_layer", None)
                    if layer:
                        layer.visible = checked
                    break

        self.visibility_changed.emit()
