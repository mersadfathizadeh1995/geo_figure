"""Curve rendering: add, remove, update, highlight dispersion curves."""
import numpy as np
import pyqtgraph as pg
from PySide6.QtGui import QColor
from typing import Dict

from geo_figure.core.models import CurveData, CurveType, WaveType
from .constants import VEL_FACTORS, VEL_UNIT_STR, LAYOUT_SPLIT_WAVE


def get_plot_for_curve(canvas, curve: CurveData) -> pg.PlotItem:
    """Return the correct plot item for a curve based on its subplot_key."""
    if curve.subplot_key in canvas._plots:
        return canvas._plots[curve.subplot_key]
    if canvas._layout_mode == LAYOUT_SPLIT_WAVE:
        if curve.wave_type == WaveType.LOVE:
            return canvas._plots.get("love", list(canvas._plots.values())[0])
        return canvas._plots.get("rayleigh", list(canvas._plots.values())[0])
    return list(canvas._plots.values())[0]


def add_curve(canvas, curve: CurveData):
    """Add or update a curve on the canvas."""
    if not curve.has_data or curve.velocity is None:
        return

    if curve.uid in canvas._curves:
        remove_plot_items(canvas, curve.uid)

    plot = get_plot_for_curve(canvas, curve)
    color = QColor(curve.color)
    pen = pg.mkPen(color=color, width=curve.line_width)

    freq = curve.frequency
    vel = curve.velocity
    mask = (curve.point_mask if curve.point_mask is not None
            else np.ones(len(freq), dtype=bool))
    freq_vis = freq[mask]
    vf = VEL_FACTORS.get(canvas._velocity_unit, 1.0)
    vel_vis = vel[mask] * vf

    # Resample if enabled
    if curve.resample_enabled and len(freq_vis) >= 2:
        n = curve.resample_n_points
        f_min, f_max = freq_vis.min(), freq_vis.max()
        if curve.resample_method == "log" and f_min > 0:
            new_freq = np.logspace(np.log10(f_min), np.log10(f_max), n)
        else:
            new_freq = np.linspace(f_min, f_max, n)
        new_vel = np.interp(new_freq, freq_vis, vel_vis)
        if curve.stddev is not None and len(curve.stddev) == len(freq):
            stddev_masked = curve.stddev[mask]
            new_stddev = np.interp(new_freq, freq_vis, stddev_masked)
        else:
            new_stddev = None
        freq_vis = new_freq
        vel_vis = new_vel
        _stddev_for_plot = new_stddev
    else:
        _stddev_for_plot = (curve.stddev[mask]
                            if (curve.stddev is not None
                                and len(curve.stddev) == len(freq))
                            else None)

    # Apply stddev mode overrides
    _stddev_for_plot = _apply_stddev_mode(curve, freq_vis, _stddev_for_plot)

    if len(freq_vis) == 0:
        canvas._curves[curve.uid] = {
            "data": curve, "plot": plot,
            "line": None, "scatter": None, "error": None,
        }
        return

    with np.errstate(divide="ignore", invalid="ignore"):
        log_freq = np.where(freq_vis > 0, np.log10(freq_vis), -10)

    is_theoretical = curve.curve_type == CurveType.THEORETICAL
    line_item = None
    scatter = None
    error_item = None

    if is_theoretical:
        line_item = plot.plot(
            log_freq, vel_vis, pen=pen, name=curve.display_name,
        )
    else:
        if (_stddev_for_plot is not None
                and len(_stddev_for_plot) == len(freq_vis)
                and curve.show_error_bars):
            stddev_vis = _stddev_for_plot
            if curve.stddev_type == "logstd":
                top_err = vel_vis * (np.exp(stddev_vis) - 1)
                bottom_err = vel_vis * (1 - np.exp(-stddev_vis))
            else:
                top_err = stddev_vis
                bottom_err = stddev_vis

            err_color = QColor(curve.color)
            err_color.setAlpha(160)
            error_item = pg.ErrorBarItem(
                x=log_freq, y=vel_vis,
                top=top_err, bottom=bottom_err,
                pen=pg.mkPen(err_color, width=1.2),
                beam=0.0,
            )
            plot.addItem(error_item)

        vu = VEL_UNIT_STR.get(canvas._velocity_unit, "m/s")
        scatter = pg.ScatterPlotItem(
            log_freq, vel_vis,
            pen=pg.mkPen(color, width=1),
            brush=pg.mkBrush(color),
            size=curve.marker_size,
            hoverable=True,
            tip=lambda x, y, data, u=vu: f"f={10**x:.2f} Hz, v={y:.1f} {u}",
            data=[curve.uid] * len(freq_vis),
        )
        scatter.sigClicked.connect(
            lambda pts, ev, uid=curve.uid: canvas.curve_clicked.emit(uid)
        )
        plot.addItem(scatter)
        # Add to legend
        for key, p in canvas._plots.items():
            if p is plot and key in canvas._legends:
                canvas._legends[key].addItem(scatter, curve.display_name)
                break

    canvas._curves[curve.uid] = {
        "data": curve,
        "plot": plot,
        "line": line_item,
        "scatter": scatter,
        "error": error_item,
    }

    # Respect the curve's stored visibility flag
    if not curve.visible:
        set_curve_visible(canvas, curve.uid, False)


def remove_curve(canvas, uid: str):
    """Remove a curve from the canvas."""
    if uid in canvas._curves:
        remove_plot_items(canvas, uid)
        del canvas._curves[uid]


def set_curve_visible(canvas, uid: str, visible: bool):
    """Toggle curve visibility."""
    if uid not in canvas._curves:
        return
    items = canvas._curves[uid]
    if items["line"]:
        items["line"].setVisible(visible)
    if items["scatter"]:
        items["scatter"].setVisible(visible)
    if items.get("error"):
        items["error"].setVisible(visible)
    plot = items.get("plot")
    if plot:
        plot.vb.updateAutoRange()


def highlight_curve(canvas, uid: str, selected: bool):
    """Highlight or unhighlight a curve."""
    if uid not in canvas._curves:
        return
    items = canvas._curves[uid]
    curve = items["data"]
    color = QColor(curve.color)
    if selected:
        width = curve.line_width * 2.5
        if items["scatter"]:
            items["scatter"].setSize(curve.marker_size * 1.5)
        if items["line"]:
            items["line"].setPen(pg.mkPen(color, width=width))
    else:
        width = curve.line_width
        if items["scatter"]:
            items["scatter"].setSize(curve.marker_size)
        if items["line"]:
            items["line"].setPen(pg.mkPen(color, width=width))


def remove_plot_items(canvas, uid: str):
    """Remove plot items for a curve uid."""
    items = canvas._curves.get(uid)
    if not items:
        return
    plot = items.get("plot")
    if not plot:
        return
    if items.get("line"):
        plot.removeItem(items["line"])
    if items.get("scatter"):
        plot.removeItem(items["scatter"])
    if items.get("error"):
        plot.removeItem(items["error"])


def _apply_stddev_mode(curve, freq_vis, stddev):
    """Apply range-based stddev override."""
    if stddev is None:
        return None
    if curve.stddev_mode == "range" and curve.stddev_ranges:
        out = np.copy(stddev)
        for fmin_r, fmax_r, val in curve.stddev_ranges:
            in_range = (freq_vis >= fmin_r) & (freq_vis <= fmax_r)
            out[in_range] = val
        return out
    elif curve.stddev_mode == "fixed_logstd":
        return np.full(len(freq_vis), curve.fixed_logstd)
    elif curve.stddev_mode == "fixed_cov":
        return np.full(len(freq_vis), curve.fixed_cov)
    return stddev
