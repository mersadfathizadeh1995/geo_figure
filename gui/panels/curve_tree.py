"""Data panel - left dock showing loaded data organized by subplot with drag-drop."""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QTreeWidget, QTreeWidgetItem,
    QPushButton, QHBoxLayout, QMenu, QInputDialog, QAbstractItemView
)
from PySide6.QtCore import Signal, Qt, QMimeData
from PySide6.QtGui import QColor, QIcon, QPixmap, QPainter, QBrush, QDrag
from typing import Dict, Optional, List, Tuple
from geo_figure.core.models import CurveData, CurveType, EnsembleData, VsProfileData, CURVE_COLORS

# Data keys stored in tree items
_SUBPLOT_PREFIX = "__subplot__"
_ENSEMBLE_PREFIX = "__ens__"
_LAYER_PREFIX = "__layer__"
_PROFILE_PREFIX = "__vsp__"
_ROLE_UID = Qt.UserRole
_ROLE_POINT_IDX = Qt.UserRole + 1


class DataTreeWidget(QTreeWidget):
    """QTreeWidget with custom drag-drop for moving curves between subplots."""

    curve_moved = Signal(str, str)  # uid, new_subplot_key

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDragDropMode(QAbstractItemView.DragDrop)
        self.setDefaultDropAction(Qt.MoveAction)

    def startDrag(self, supportedActions):
        """Only allow dragging curve-level items."""
        item = self.currentItem()
        if not item:
            return
        uid = item.data(0, _ROLE_UID)
        point_idx = item.data(0, _ROLE_POINT_IDX)
        if uid and not str(uid).startswith(_SUBPLOT_PREFIX) and point_idx is None:
            drag = QDrag(self)
            mime = QMimeData()
            mime.setText(uid)
            drag.setMimeData(mime)
            drag.exec(Qt.MoveAction)

    def dragEnterEvent(self, event):
        if event.mimeData().hasText():
            event.accept()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        """Accept drops only on subplot root items."""
        item = self.itemAt(event.position().toPoint())
        if item:
            data = item.data(0, _ROLE_UID)
            if data and str(data).startswith(_SUBPLOT_PREFIX):
                event.accept()
                return
        event.ignore()

    def dropEvent(self, event):
        """Emit signal when curve dropped on a different subplot."""
        target_item = self.itemAt(event.position().toPoint())
        if not target_item:
            event.ignore()
            return
        target_data = target_item.data(0, _ROLE_UID)
        if not target_data or not str(target_data).startswith(_SUBPLOT_PREFIX):
            event.ignore()
            return
        new_key = str(target_data).replace(_SUBPLOT_PREFIX, "")
        uid = event.mimeData().text()
        if uid:
            self.curve_moved.emit(uid, new_key)
            event.accept()
        else:
            event.ignore()


class CurveTreePanel(QWidget):
    """Data panel showing curves organized by subplot groups."""

    curve_selected = Signal(str)           # uid
    curve_visibility_changed = Signal(str, bool)  # uid, visible
    point_visibility_changed = Signal(str, int, bool)  # uid, point_index, visible
    add_curve_requested = Signal()         # request file open
    load_target_requested = Signal()       # request .target load
    remove_curve_requested = Signal(str)   # uid
    curve_subplot_changed = Signal(str, str)   # uid, new_subplot_key
    subplot_renamed = Signal(str, str)         # key, new_name
    subplot_activated = Signal(str)            # subplot key clicked
    ensemble_selected = Signal(str)            # ensemble uid
    ensemble_layer_toggled = Signal(str, str, bool)  # ens_uid, layer_name, visible
    remove_ensemble_requested = Signal(str)    # ensemble uid
    ensemble_subplot_changed = Signal(str, str)  # ens_uid, new_subplot_key
    vs_profile_selected = Signal(str, str)           # profile uid, layer_name ("" for root)
    vs_profile_layer_toggled = Signal(str, str, bool)  # prof_uid, layer, visible
    remove_vs_profile_requested = Signal(str)   # profile uid

    def __init__(self, parent=None):
        super().__init__(parent)
        self._curves: Dict[str, QTreeWidgetItem] = {}  # uid -> tree item
        self._ensembles: Dict[str, QTreeWidgetItem] = {}  # ens uid -> tree item
        self._vs_profiles: Dict[str, QTreeWidgetItem] = {}  # profile uid -> tree item
        self._subplot_roots: Dict[str, QTreeWidgetItem] = {}  # key -> root item
        self._color_index = 0
        self._setup_ui()
        # Initialize with single "Main" subplot
        self.set_subplot_structure([("main", "Main")])

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # Custom tree with drag-drop
        self.tree = DataTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setRootIsDecorated(True)
        self.tree.setAnimated(True)
        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._show_context_menu)
        self.tree.itemClicked.connect(self._on_item_clicked)
        self.tree.itemChanged.connect(self._on_item_changed)
        self.tree.curve_moved.connect(self._on_tree_item_moved)
        layout.addWidget(self.tree)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(4)

        self.add_btn = QPushButton("+ Add")
        self.add_btn.setToolTip("Add dispersion curve file")
        self.add_btn.clicked.connect(lambda: self.add_curve_requested.emit())
        btn_layout.addWidget(self.add_btn)

        self.target_btn = QPushButton("Load Target")
        self.target_btn.setToolTip("Load Dinver .target file")
        self.target_btn.clicked.connect(lambda: self.load_target_requested.emit())
        btn_layout.addWidget(self.target_btn)

        layout.addLayout(btn_layout)

    def set_subplot_structure(self, subplots: List[Tuple[str, str]]):
        """Update subplot groups. subplots = [(key, name), ...]."""
        self.tree.blockSignals(True)
        # Clear everything
        self.tree.clear()
        self._subplot_roots.clear()
        self._curves.clear()
        self._ensembles.clear()
        # Create subplot root items
        for key, name in subplots:
            root = QTreeWidgetItem(self.tree, [f"{name} (0)"])
            root.setData(0, _ROLE_UID, f"{_SUBPLOT_PREFIX}{key}")
            root.setExpanded(True)
            flags = root.flags() & ~Qt.ItemIsDragEnabled
            root.setFlags(flags)
            self._subplot_roots[key] = root
        self._active_subplot_key = ""
        self.tree.blockSignals(False)

    def add_curve(self, curve: CurveData):
        """Add a curve under its subplot group, with per-point items."""
        # Find parent subplot root
        parent = self._subplot_roots.get(curve.subplot_key)
        if not parent and self._subplot_roots:
            parent = list(self._subplot_roots.values())[0]
        if not parent:
            return

        # Build label
        text = self._curve_label(curve)
        item = QTreeWidgetItem(parent, [text])
        item.setData(0, _ROLE_UID, curve.uid)
        flags = (item.flags() | Qt.ItemIsUserCheckable | Qt.ItemIsDragEnabled)
        flags = flags & ~Qt.ItemIsDropEnabled
        item.setFlags(flags)
        item.setCheckState(0, Qt.Checked if curve.visible else Qt.Unchecked)
        self._set_item_color(item, curve.color)

        # Per-point children for non-theoretical curves
        if curve.curve_type != CurveType.THEORETICAL and curve.has_data:
            self.tree.blockSignals(True)
            for i in range(curve.n_points):
                freq_val = curve.frequency[i]
                vel_val = curve.velocity[i]
                pt_text = f"{freq_val:.2f} Hz  |  {vel_val:.0f} m/s"
                child = QTreeWidgetItem(item, [pt_text])
                child.setData(0, _ROLE_UID, curve.uid)
                child.setData(0, _ROLE_POINT_IDX, i)
                child_flags = (child.flags() | Qt.ItemIsUserCheckable)
                child_flags = child_flags & ~Qt.ItemIsDragEnabled & ~Qt.ItemIsDropEnabled
                child.setFlags(child_flags)
                mask_val = curve.point_mask[i] if curve.point_mask is not None else True
                child.setCheckState(0, Qt.Checked if mask_val else Qt.Unchecked)
            self.tree.blockSignals(False)
            item.setExpanded(False)

        self._curves[curve.uid] = item
        self._update_counts()

    def remove_curve(self, uid: str):
        """Remove a curve from the tree."""
        item = self._curves.get(uid)
        if item:
            parent = item.parent()
            if parent:
                parent.removeChild(item)
            del self._curves[uid]
            self._update_counts()

    def add_ensemble(self, ensemble: EnsembleData):
        """Add a theoretical ensemble with sub-layer items to the tree."""
        parent = self._subplot_roots.get(ensemble.subplot_key)
        if not parent and self._subplot_roots:
            parent = list(self._subplot_roots.values())[0]
        if not parent:
            return

        self.tree.blockSignals(True)

        label = f"{ensemble.display_name}  ({ensemble.n_profiles} models)"
        item = QTreeWidgetItem(parent, [label])
        item.setData(0, _ROLE_UID, f"{_ENSEMBLE_PREFIX}{ensemble.uid}")
        flags = item.flags() | Qt.ItemIsUserCheckable | Qt.ItemIsDragEnabled
        flags = flags & ~Qt.ItemIsDropEnabled
        item.setFlags(flags)
        item.setCheckState(0, Qt.Checked)
        self._set_item_color(item, ensemble.median_layer.color)

        # Sub-layer children
        layer_defs = [
            ("median", "Median", ensemble.median_layer),
            ("percentile", "16-84 Percentile Band", ensemble.percentile_layer),
            ("envelope", "Min/Max Envelope", ensemble.envelope_layer),
            ("individual", "Individual Curves", ensemble.individual_layer),
        ]
        for layer_name, layer_label, layer in layer_defs:
            child = QTreeWidgetItem(item, [layer_label])
            child.setData(0, _ROLE_UID, f"{_ENSEMBLE_PREFIX}{ensemble.uid}")
            child.setData(0, _ROLE_POINT_IDX, f"{_LAYER_PREFIX}{layer_name}")
            child_flags = child.flags() | Qt.ItemIsUserCheckable
            child_flags = child_flags & ~Qt.ItemIsDragEnabled & ~Qt.ItemIsDropEnabled
            child.setFlags(child_flags)
            child.setCheckState(0, Qt.Checked if layer.visible else Qt.Unchecked)
            self._set_item_color(child, layer.color)

        item.setExpanded(True)
        self.tree.blockSignals(False)

        self._ensembles[ensemble.uid] = item
        self._update_counts()

    def remove_ensemble(self, uid: str):
        """Remove an ensemble from the tree."""
        item = self._ensembles.get(uid)
        if item:
            parent = item.parent()
            if parent:
                parent.removeChild(item)
            del self._ensembles[uid]
            self._update_counts()

    def add_vs_profile(self, prof: VsProfileData):
        """Add a Vs profile with sub-layer items to the tree."""
        parent = self._subplot_roots.get(prof.subplot_key)
        if not parent and self._subplot_roots:
            parent = list(self._subplot_roots.values())[0]
        if not parent:
            return

        self.tree.blockSignals(True)

        ptype = {"vs": "Vs", "vp": "Vp", "rho": "Density"}.get(prof.profile_type, "Vs")
        label = f"{prof.display_name}  ({prof.n_profiles} models)"
        item = QTreeWidgetItem(parent, [label])
        item.setData(0, _ROLE_UID, f"{_PROFILE_PREFIX}{prof.uid}")
        flags = item.flags() | Qt.ItemIsUserCheckable | Qt.ItemIsDragEnabled
        flags = flags & ~Qt.ItemIsDropEnabled
        item.setFlags(flags)
        item.setCheckState(0, Qt.Checked)
        self._set_item_color(item, prof.median_layer.color)

        layer_defs = [
            ("median", "Median", prof.median_layer),
            ("percentile", "5-95 Percentile Band", prof.percentile_layer),
            ("individual", "Individual Profiles", prof.individual_layer),
            ("sigma", "Sigma_ln", prof.sigma_layer),
        ]
        for layer_name, layer_label, layer in layer_defs:
            child = QTreeWidgetItem(item, [layer_label])
            child.setData(0, _ROLE_UID, f"{_PROFILE_PREFIX}{prof.uid}")
            child.setData(0, _ROLE_POINT_IDX, f"{_LAYER_PREFIX}{layer_name}")
            child_flags = child.flags() | Qt.ItemIsUserCheckable
            child_flags = child_flags & ~Qt.ItemIsDragEnabled & ~Qt.ItemIsDropEnabled
            child.setFlags(child_flags)
            child.setCheckState(0, Qt.Checked if layer.visible else Qt.Unchecked)
            self._set_item_color(child, layer.color)

        item.setExpanded(True)
        self.tree.blockSignals(False)

        self._vs_profiles[prof.uid] = item
        self._update_counts()

    def remove_vs_profile(self, uid: str):
        """Remove a Vs profile from the tree."""
        item = self._vs_profiles.get(uid)
        if item:
            parent = item.parent()
            if parent:
                parent.removeChild(item)
            del self._vs_profiles[uid]
            self._update_counts()

    def clear_all(self):
        """Remove all curves, ensembles, and profiles from the tree."""
        for uid in list(self._curves.keys()):
            self.remove_curve(uid)
        for uid in list(self._ensembles.keys()):
            self.remove_ensemble(uid)
        for uid in list(self._vs_profiles.keys()):
            self.remove_vs_profile(uid)

    def select_curve(self, uid: str):
        """Programmatically select a curve in the tree."""
        item = self._curves.get(uid)
        if item:
            self.tree.setCurrentItem(item)

    def update_curve(self, uid: str, curve: CurveData):
        """Update the display text/color of a curve."""
        item = self._curves.get(uid)
        if not item:
            return
        item.setText(0, self._curve_label(curve))
        self._set_item_color(item, curve.color)

    def get_next_color(self) -> str:
        """Get the next auto-assigned color."""
        color = CURVE_COLORS[self._color_index % len(CURVE_COLORS)]
        self._color_index += 1
        return color

    # ── Internal ─────────────────────────────────────────────────

    @staticmethod
    def _curve_label(curve: CurveData) -> str:
        text = curve.display_name
        if curve.n_points > 0:
            text += f"  ({curve.n_points} pts)"
        src = curve.source_type.value if hasattr(curve, 'source_type') else ""
        if src:
            text += f"  [{src}]"
        return text

    def _set_item_color(self, item: QTreeWidgetItem, color_str: str):
        pixmap = QPixmap(12, 12)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setBrush(QBrush(QColor(color_str)))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(1, 1, 10, 10)
        painter.end()
        item.setIcon(0, QIcon(pixmap))

    def _update_counts(self):
        for key, root in self._subplot_roots.items():
            count = root.childCount()
            # Preserve custom name (text before the count)
            current = root.text(0)
            # Extract name portion (before last parenthesized count)
            paren_idx = current.rfind(" (")
            name = current[:paren_idx] if paren_idx > 0 else current
            root.setText(0, f"{name} ({count})")

    def _on_item_clicked(self, item: QTreeWidgetItem, column: int):
        uid = item.data(0, _ROLE_UID)
        if not uid:
            return
        uid_str = str(uid)
        if uid_str.startswith(_SUBPLOT_PREFIX):
            key = uid_str.replace(_SUBPLOT_PREFIX, "")
            self._highlight_subplot(key)
            self.subplot_activated.emit(key)
            return
        if uid_str.startswith(_ENSEMBLE_PREFIX):
            ens_uid = uid_str.replace(_ENSEMBLE_PREFIX, "")
            self.ensemble_selected.emit(ens_uid)
        elif uid_str.startswith(_PROFILE_PREFIX):
            prof_uid = uid_str.replace(_PROFILE_PREFIX, "")
            layer_data = item.data(0, _ROLE_POINT_IDX)
            layer_name = ""
            if layer_data is not None and str(layer_data).startswith(_LAYER_PREFIX):
                layer_name = str(layer_data).replace(_LAYER_PREFIX, "")
            self.vs_profile_selected.emit(prof_uid, layer_name)
        else:
            self.curve_selected.emit(uid_str)

    def _highlight_subplot(self, key: str):
        """Visually highlight the active subplot root item."""
        self._active_subplot_key = key
        highlight = QColor("#D0E8FF")  # light blue highlight
        no_bg = QBrush()
        bold_font_flag = True
        for k, root in self._subplot_roots.items():
            if k == key:
                root.setBackground(0, QBrush(highlight))
                font = root.font(0)
                font.setBold(True)
                root.setFont(0, font)
            else:
                root.setBackground(0, no_bg)
                font = root.font(0)
                font.setBold(False)
                root.setFont(0, font)

    def _on_item_changed(self, item: QTreeWidgetItem, column: int):
        uid = item.data(0, _ROLE_UID)
        if not uid or str(uid).startswith(_SUBPLOT_PREFIX):
            return
        uid_str = str(uid)
        visible = item.checkState(0) == Qt.Checked

        # Ensemble items
        if uid_str.startswith(_ENSEMBLE_PREFIX):
            ens_uid = uid_str.replace(_ENSEMBLE_PREFIX, "")
            layer_data = item.data(0, _ROLE_POINT_IDX)
            if layer_data is not None and str(layer_data).startswith(_LAYER_PREFIX):
                # Layer toggle
                layer_name = str(layer_data).replace(_LAYER_PREFIX, "")
                self.ensemble_layer_toggled.emit(ens_uid, layer_name, visible)
            else:
                # Ensemble root toggle — toggle all child layers
                self.tree.blockSignals(True)
                for i in range(item.childCount()):
                    child = item.child(i)
                    child.setCheckState(0, item.checkState(0))
                self.tree.blockSignals(False)
                for layer_name in ("median", "percentile", "envelope", "individual"):
                    self.ensemble_layer_toggled.emit(ens_uid, layer_name, visible)
            return

        # Vs Profile items
        if uid_str.startswith(_PROFILE_PREFIX):
            prof_uid = uid_str.replace(_PROFILE_PREFIX, "")
            layer_data = item.data(0, _ROLE_POINT_IDX)
            if layer_data is not None and str(layer_data).startswith(_LAYER_PREFIX):
                layer_name = str(layer_data).replace(_LAYER_PREFIX, "")
                self.vs_profile_layer_toggled.emit(prof_uid, layer_name, visible)
            else:
                self.tree.blockSignals(True)
                for i in range(item.childCount()):
                    child = item.child(i)
                    child.setCheckState(0, item.checkState(0))
                self.tree.blockSignals(False)
                for layer_name in ("median", "percentile", "individual", "sigma"):
                    self.vs_profile_layer_toggled.emit(prof_uid, layer_name, visible)
            return

        # Regular curve items
        point_index = item.data(0, _ROLE_POINT_IDX)
        if point_index is not None:
            self.point_visibility_changed.emit(uid_str, int(point_index), visible)
        else:
            self.curve_visibility_changed.emit(uid_str, visible)

    def _show_context_menu(self, pos):
        item = self.tree.itemAt(pos)
        if not item:
            return
        uid = item.data(0, _ROLE_UID)
        if not uid:
            return

        menu = QMenu(self)

        # Subplot root context menu
        if str(uid).startswith(_SUBPLOT_PREFIX):
            key = str(uid).replace(_SUBPLOT_PREFIX, "")
            rename_action = menu.addAction("Rename Subplot...")
            rename_action.triggered.connect(lambda: self._rename_subplot(key))
            menu.exec(self.tree.viewport().mapToGlobal(pos))
            return

        # Ensemble context menu
        if str(uid).startswith(_ENSEMBLE_PREFIX):
            ens_uid = str(uid).replace(_ENSEMBLE_PREFIX, "")
            layer_data = item.data(0, _ROLE_POINT_IDX)
            if layer_data is None:
                # Ensemble root
                remove_action = menu.addAction("Remove Ensemble")
                remove_action.triggered.connect(
                    lambda: self.remove_ensemble_requested.emit(ens_uid)
                )
                # "Move to" submenu for ensemble
                if len(self._subplot_roots) > 1:
                    move_menu = menu.addMenu("Move to")
                    for key, root in self._subplot_roots.items():
                        name = root.text(0)
                        paren_idx = name.rfind(" (")
                        name = name[:paren_idx] if paren_idx > 0 else name
                        act = move_menu.addAction(name)
                        act.triggered.connect(
                            lambda checked, u=ens_uid, k=key:
                                self.ensemble_subplot_changed.emit(u, k)
                        )
            menu.exec(self.tree.viewport().mapToGlobal(pos))
            return

        # Vs Profile context menu
        if str(uid).startswith(_PROFILE_PREFIX):
            prof_uid = str(uid).replace(_PROFILE_PREFIX, "")
            layer_data = item.data(0, _ROLE_POINT_IDX)
            if layer_data is None:
                remove_action = menu.addAction("Remove Vs Profile")
                remove_action.triggered.connect(
                    lambda: self.remove_vs_profile_requested.emit(prof_uid)
                )
            menu.exec(self.tree.viewport().mapToGlobal(pos))
            return

        point_index = item.data(0, _ROLE_POINT_IDX)
        if point_index is None:
            # Curve-level menu
            remove_action = menu.addAction("Remove")
            remove_action.triggered.connect(lambda: self.remove_curve_requested.emit(uid))

            # "Move to" submenu if multiple subplots
            if len(self._subplot_roots) > 1:
                move_menu = menu.addMenu("Move to")
                for key, root in self._subplot_roots.items():
                    name = root.text(0)
                    paren_idx = name.rfind(" (")
                    name = name[:paren_idx] if paren_idx > 0 else name
                    act = move_menu.addAction(name)
                    act.triggered.connect(
                        lambda checked, u=uid, k=key: self.curve_subplot_changed.emit(u, k)
                    )

            menu.addSeparator()
            check_all = menu.addAction("Check All Points")
            check_all.triggered.connect(lambda: self._set_all_points(uid, True))
            uncheck_all = menu.addAction("Uncheck All Points")
            uncheck_all.triggered.connect(lambda: self._set_all_points(uid, False))
        else:
            toggle = menu.addAction("Toggle Point")
            toggle.triggered.connect(lambda: self._toggle_point(item))

        menu.exec(self.tree.viewport().mapToGlobal(pos))

    def _rename_subplot(self, key: str):
        root = self._subplot_roots.get(key)
        if not root:
            return
        current = root.text(0)
        paren_idx = current.rfind(" (")
        current_name = current[:paren_idx] if paren_idx > 0 else current
        new_name, ok = QInputDialog.getText(
            self, "Rename Subplot", "New name:", text=current_name
        )
        if ok and new_name.strip():
            self.subplot_renamed.emit(key, new_name.strip())
            self._update_counts()

    def _set_all_points(self, uid: str, checked: bool):
        item = self._curves.get(uid)
        if not item:
            return
        state = Qt.Checked if checked else Qt.Unchecked
        for i in range(item.childCount()):
            child = item.child(i)
            if child.checkState(0) != state:
                child.setCheckState(0, state)

    def _toggle_point(self, item: QTreeWidgetItem):
        new_state = Qt.Unchecked if item.checkState(0) == Qt.Checked else Qt.Checked
        item.setCheckState(0, new_state)

    def _on_tree_item_moved(self, uid: str, new_key: str):
        """Route drag-drop moves to the correct signal."""
        if uid.startswith(_ENSEMBLE_PREFIX):
            ens_uid = uid.replace(_ENSEMBLE_PREFIX, "")
            self.ensemble_subplot_changed.emit(ens_uid, new_key)
        else:
            self.curve_subplot_changed.emit(uid, new_key)
