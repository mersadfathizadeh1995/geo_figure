"""Legend management: mode, position, font, visibility."""
import pyqtgraph as pg
from PySide6.QtGui import QColor
from PySide6.QtCore import Qt

from .constants import LEGEND_ANCHORS


def set_legend_visible(canvas, visible: bool):
    """Toggle legend visibility for all subplots."""
    for leg in canvas._legends.values():
        leg.setVisible(visible)


def set_legend_position(canvas, position: str):
    """Set legend position for all subplots."""
    canvas._legend_position = position
    anchor = LEGEND_ANCHORS.get(position, (1, 0))
    for leg in canvas._legends.values():
        leg.anchor(itemPos=anchor, parentPos=anchor)


def set_legend_font_size(canvas, size: int):
    """Set legend font size."""
    for leg in canvas._legends.values():
        for item in leg.items:
            for single in item:
                if hasattr(single, "setText"):
                    html = single.toHtml()
                    if "font-size" in html:
                        import re
                        html = re.sub(r"font-size:\s*\d+", f"font-size:{size}",
                                      html)
                        single.setHtml(html)


def set_legend_mode(canvas, mode: str, legend_subplot: str = ""):
    """
    Set legend display mode:
      'per_subplot' — each subplot has its own legend
      'combined_first' — all legends merged on the first subplot
      'combined_second' — all legends merged on the second subplot
      'outside' — legends outside the plot area
    """
    canvas._legend_mode = mode
    canvas._legend_mode_subplot = legend_subplot
    _apply_legend_mode(canvas)


def get_legend_config(canvas):
    """Return current legend config dict."""
    return {
        "mode": canvas._legend_mode,
        "position": canvas._legend_position,
        "subplot": canvas._legend_mode_subplot,
    }


def _apply_legend_mode(canvas):
    """Apply current legend mode configuration."""
    mode = getattr(canvas, "_legend_mode", "per_subplot")

    # Collect legend items from all sources
    all_items = {}
    for key, plot in canvas._plots.items():
        items_list = []
        if hasattr(plot, "legend") and plot.legend is not None:
            for sample, label in plot.legend.items:
                name = label.text if hasattr(label, "text") else str(label)
                if name:
                    items_list.append((sample, name))
        for uid, cinfo in canvas._curves.items():
            if cinfo.get("plot") is plot:
                cdata = cinfo["data"]
                sample = cinfo.get("scatter") or cinfo.get("line")
                if sample:
                    items_list.append((sample, cdata.display_name))
        all_items[key] = items_list

    # Clear all legends
    for leg in canvas._legends.values():
        leg.setVisible(False)

    if mode == "per_subplot":
        for key, leg in canvas._legends.items():
            leg.setVisible(True)
            anchor = LEGEND_ANCHORS.get(canvas._legend_position, (1, 0))
            leg.anchor(itemPos=anchor, parentPos=anchor)
    elif mode in ("combined_first", "combined_second"):
        plot_keys = list(canvas._plots.keys())
        if not plot_keys:
            return
        target = (plot_keys[0] if mode == "combined_first"
                  else plot_keys[min(1, len(plot_keys) - 1)])
        if target in canvas._legends:
            leg = canvas._legends[target]
            leg.setVisible(True)
            anchor = LEGEND_ANCHORS.get(canvas._legend_position, (1, 0))
            leg.anchor(itemPos=anchor, parentPos=anchor)
    elif mode == "outside":
        for leg in canvas._legends.values():
            leg.setVisible(False)
