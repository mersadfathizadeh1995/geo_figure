"""Canvas export: screenshot / image export."""
import pyqtgraph.exporters as pgex
from PySide6.QtWidgets import QFileDialog, QInputDialog
from PySide6.QtGui import QImage, QPainter
from PySide6.QtCore import QRectF


def export_canvas(canvas, path: str, dpi: int = 150):
    """Export the entire canvas as a PNG image at the given DPI."""
    scale = dpi / 96.0
    w = int(canvas.width() * scale)
    h = int(canvas.height() * scale)
    img = QImage(w, h, QImage.Format_ARGB32)
    painter = QPainter(img)
    painter.setRenderHint(QPainter.Antialiasing, True)
    canvas.render(painter, QRectF(0, 0, w, h),
                  canvas.viewport().rect())
    painter.end()
    img.save(path)


def on_export_action(canvas):
    """Interactive export (right-click -> Export Image)."""
    dpi, ok = QInputDialog.getInt(
        canvas, "Export DPI", "DPI:", 150, 72, 1200, 50,
    )
    if not ok:
        return
    path, _ = QFileDialog.getSaveFileName(
        canvas, "Export Image", "",
        "PNG Files (*.png);;JPEG Files (*.jpg);;All Files (*)",
    )
    if path:
        export_canvas(canvas, path, dpi)
