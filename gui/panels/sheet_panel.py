"""Sheet panel — sheet-level settings: name, legend mode, per-subplot legend config."""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout, QLabel, QLineEdit,
    QComboBox, QSpinBox, QCheckBox, QScrollArea, QGroupBox,
    QHBoxLayout, QToolButton,
)
from PySide6.QtCore import Signal, Qt


class _CollapsibleSection(QWidget):
    """Lightweight collapsible section reused from properties_modules."""

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


class SheetPanel(QWidget):
    """Panel for sheet-level settings: sheet name, legend configuration."""

    sheet_name_changed = Signal(str)       # new name
    legend_changed = Signal(dict)          # full legend config

    def __init__(self, parent=None):
        super().__init__(parent)
        self._updating = False
        self._subplot_keys = []
        self._setup_ui()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(4, 4, 4, 4)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setSpacing(8)

        # -- Sheet Info --
        info_sec = _CollapsibleSection("Sheet Info", expanded=True)
        self.sheet_name_edit = QLineEdit()
        self.sheet_name_edit.setPlaceholderText("Sheet name")
        self.sheet_name_edit.editingFinished.connect(self._on_name_edited)
        info_sec.form.addRow("Name:", self.sheet_name_edit)

        self.subplot_count_label = QLabel("-")
        info_sec.form.addRow("Subplots:", self.subplot_count_label)

        layout.addWidget(info_sec)

        # -- Legend Settings --
        legend_sec = _CollapsibleSection("Legend", expanded=True)

        self.legend_mode_combo = QComboBox()
        self.legend_mode_combo.addItems([
            "Per subplot",
            "Combined (outside)",
            "Combined (on first subplot)",
            "Combined (on second subplot)",
        ])
        self.legend_mode_combo.currentIndexChanged.connect(self._on_legend_ui_changed)
        legend_sec.form.addRow("Mode:", self.legend_mode_combo)

        self.legend_visible_cb = QCheckBox("Show")
        self.legend_visible_cb.setChecked(True)
        self.legend_visible_cb.stateChanged.connect(self._on_legend_ui_changed)
        legend_sec.form.addRow("Visible:", self.legend_visible_cb)

        self.legend_pos_combo = QComboBox()
        self.legend_pos_combo.addItems([
            "top-right", "top-left", "bottom-right", "bottom-left"
        ])
        self.legend_pos_combo.currentIndexChanged.connect(self._on_legend_ui_changed)
        legend_sec.form.addRow("Position:", self.legend_pos_combo)

        # Offset row
        offset_row = QHBoxLayout()
        offset_row.addWidget(QLabel("X:"))
        self.legend_offset_x = QSpinBox()
        self.legend_offset_x.setRange(-500, 500)
        self.legend_offset_x.setValue(-10)
        self.legend_offset_x.valueChanged.connect(self._on_legend_ui_changed)
        offset_row.addWidget(self.legend_offset_x)
        offset_row.addWidget(QLabel("Y:"))
        self.legend_offset_y = QSpinBox()
        self.legend_offset_y.setRange(-500, 500)
        self.legend_offset_y.setValue(10)
        self.legend_offset_y.valueChanged.connect(self._on_legend_ui_changed)
        offset_row.addWidget(self.legend_offset_y)
        legend_sec.form.addRow("Offset:", offset_row)

        self.legend_font_size = QSpinBox()
        self.legend_font_size.setRange(6, 24)
        self.legend_font_size.setValue(9)
        self.legend_font_size.valueChanged.connect(self._on_legend_ui_changed)
        legend_sec.form.addRow("Font Size:", self.legend_font_size)

        layout.addWidget(legend_sec)

        layout.addStretch()
        scroll.setWidget(container)
        main_layout.addWidget(scroll)

    # -- Public API -------------------------------------------------------

    def set_sheet_info(self, name: str, subplot_keys: list):
        """Update sheet name and subplot list."""
        self._updating = True
        self.sheet_name_edit.setText(name)
        self._subplot_keys = subplot_keys
        self.subplot_count_label.setText(str(len(subplot_keys)))
        self._updating = False

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

        mode = config.get("mode", "per_subplot")
        mode_map = {
            "per_subplot": 0, "combined_outside": 1,
            "combined_first": 2, "combined_second": 3,
        }
        self.legend_mode_combo.setCurrentIndex(mode_map.get(mode, 0))

        self._updating = False

    def get_legend_config(self) -> dict:
        """Read current legend config from UI."""
        mode_map = {
            0: "per_subplot", 1: "combined_outside",
            2: "combined_first", 3: "combined_second",
        }
        return {
            "visible": self.legend_visible_cb.isChecked(),
            "position": self.legend_pos_combo.currentText(),
            "offset": (
                self.legend_offset_x.value(),
                self.legend_offset_y.value(),
            ),
            "font_size": self.legend_font_size.value(),
            "mode": mode_map.get(self.legend_mode_combo.currentIndex(), "per_subplot"),
        }

    # -- Handlers ---------------------------------------------------------

    def _on_name_edited(self):
        if self._updating:
            return
        self.sheet_name_changed.emit(self.sheet_name_edit.text().strip())

    def _on_legend_ui_changed(self):
        if self._updating:
            return
        self.legend_changed.emit(self.get_legend_config())
