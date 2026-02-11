"""Data Mapper dialog — PySide6 column mapping UI."""

from __future__ import annotations

from typing import List, Optional

import numpy as np
from PySide6 import QtWidgets, QtCore
from PySide6.QtCore import Qt

from .config import DataMapperConfig, ColumnMapping
from .core import DataMapperCore


class ColumnWidget(QtWidgets.QWidget):
    """Single column: type dropdown + data preview."""

    type_changed = QtCore.Signal(int, str)

    def __init__(
        self,
        col_idx: int,
        col_data: np.ndarray,
        type_options: List[str],
        preview_rows: int = 0,
        min_width: int = 130,
        max_width: int = 210,
        parent: Optional[QtWidgets.QWidget] = None,
    ):
        super().__init__(parent)
        self.col_idx = col_idx
        self.setMinimumWidth(min_width)
        self.setMaximumWidth(max_width)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)

        header = QtWidgets.QLabel(f"<b>Column {col_idx + 1}</b>")
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(header)

        self.combo = QtWidgets.QComboBox(self)
        self.combo.addItems(type_options)
        self.combo.currentTextChanged.connect(self._on_changed)
        layout.addWidget(self.combo)

        preview = QtWidgets.QTextEdit(self)
        preview.setReadOnly(True)
        preview.setMaximumHeight(350)
        data_show = col_data if preview_rows == 0 else col_data[:preview_rows]
        lines = []
        for val in data_show:
            if isinstance(val, (int, float)) and np.isfinite(val):
                lines.append(f"{val:.6g}")
            else:
                lines.append(str(val))
        preview.setPlainText("\n".join(lines))
        layout.addWidget(preview, 1)

    def _on_changed(self, text: str) -> None:
        self.type_changed.emit(self.col_idx, text)

    def set_type(self, type_str: str) -> None:
        idx = self.combo.findText(type_str)
        if idx >= 0:
            self.combo.setCurrentIndex(idx)

    def get_type(self) -> str:
        return self.combo.currentText()


class DataMapperDialog(QtWidgets.QDialog):
    """Column mapping dialog for tabular data files.

    Shows each column side-by-side with a dropdown to assign its type and a
    preview of the data values. Validates required types before accepting.
    """

    def __init__(
        self,
        columns_data: List[np.ndarray],
        config: Optional[DataMapperConfig] = None,
        parent: Optional[QtWidgets.QWidget] = None,
    ):
        super().__init__(parent)
        self.config = config or DataMapperConfig()
        self.core = DataMapperCore(columns_data, self.config)
        self.column_widgets: List[ColumnWidget] = []
        self._setup_ui()
        self._auto_detect()
        self._validate()

    def _setup_ui(self) -> None:
        self.setWindowTitle(self.config.window_title)
        self.resize(850, 520)
        layout = QtWidgets.QVBoxLayout(self)

        layout.addWidget(QtWidgets.QLabel(
            "<b>Map each column to its data type:</b>"
        ))

        self.status_label = QtWidgets.QLabel("")
        layout.addWidget(self.status_label)

        scroll = QtWidgets.QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        container = QtWidgets.QWidget()
        self.col_layout = QtWidgets.QHBoxLayout(container)
        self.col_layout.setSpacing(4)
        scroll.setWidget(container)
        layout.addWidget(scroll, 1)

        for i, col_data in enumerate(self.core.columns_data):
            w = ColumnWidget(
                col_idx=i,
                col_data=col_data,
                type_options=self.config.type_options,
                preview_rows=self.config.preview_rows,
                min_width=self.config.column_min_width,
                max_width=self.config.column_max_width,
                parent=container,
            )
            w.type_changed.connect(self._on_type_changed)
            self.column_widgets.append(w)
            self.col_layout.addWidget(w)

        btn_box = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok
            | QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )
        self.btn_ok = btn_box.button(
            QtWidgets.QDialogButtonBox.StandardButton.Ok
        )
        btn_box.accepted.connect(self.accept)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

    def _on_type_changed(self, col_idx: int, type_str: str) -> None:
        self.core.set_column_type(col_idx, type_str)
        self._validate()

    def _auto_detect(self) -> None:
        self.core.auto_detect()
        for w in self.column_widgets:
            w.set_type(self.core.get_column_type(w.col_idx))

    def _validate(self) -> None:
        ok, errors = self.core.validate()
        if ok:
            self.status_label.setText(
                "<span style='color:green;'>Valid mapping</span>"
            )
            self.btn_ok.setEnabled(True)
        else:
            self.status_label.setText(
                f"<span style='color:red;'>{', '.join(errors)}</span>"
            )
            self.btn_ok.setEnabled(False)

    def get_mapping(self) -> ColumnMapping:
        return self.core.get_column_mapping()
