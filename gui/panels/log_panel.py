"""Log panel - bottom dock showing application messages."""
from PySide6.QtWidgets import QWidget, QVBoxLayout, QPlainTextEdit, QHBoxLayout, QPushButton
from PySide6.QtCore import Qt
from datetime import datetime


class LogPanel(QWidget):
    """Log output panel for the bottom dock."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Log text
        self.text_edit = QPlainTextEdit()
        self.text_edit.setReadOnly(True)
        self.text_edit.setMaximumBlockCount(5000)
        layout.addWidget(self.text_edit)

        # Bottom bar
        bar = QHBoxLayout()
        bar.setContentsMargins(4, 2, 4, 2)

        clear_btn = QPushButton("Clear")
        clear_btn.setFixedWidth(60)
        clear_btn.clicked.connect(self.text_edit.clear)
        bar.addStretch()
        bar.addWidget(clear_btn)

        layout.addLayout(bar)

    def log(self, message: str, level: str = "info"):
        """Add a timestamped log message."""
        ts = datetime.now().strftime("%H:%M:%S")
        prefix = {"info": "[INFO]", "warn": "[WARN]", "error": "[ERR]", "success": "[OK]"}.get(level, "[--]")
        self.text_edit.appendPlainText(f"[{ts}] {prefix} {message}")

    def log_info(self, msg: str):
        self.log(msg, "info")

    def log_warn(self, msg: str):
        self.log(msg, "warn")

    def log_error(self, msg: str):
        self.log(msg, "error")

    def log_success(self, msg: str):
        self.log(msg, "success")
