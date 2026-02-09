"""Vs profile rendering on the PyQtGraph canvas."""
import numpy as np
import pyqtgraph as pg
from PySide6.QtGui import QColor

from geo_figure.core.models import VsProfileData
from .constants import VEL_UNIT_STR


def add_vs_profile(canvas, prof_data: VsProfileData):
    """Add a VsProfileData to the canvas."""
    uid = prof_data.uid
    convert = 3.28084 if canvas._velocity_unit == "imperial" else 1.0
    vel_unit = VEL_UNIT_STR.get(canvas._velocity_unit, "m/s")

    # Compute actual data depth (in metres), then convert
    data_depth = 0.0
    if prof_data.profiles:
        for d, v in prof_data.profiles:
            finite = d[np.isfinite(d) & (d > 0)]
            if len(finite) > 0:
                data_depth = max(data_depth, float(np.max(finite)))
    if data_depth <= 0:
        data_depth = prof_data.depth_max_plot
    data_depth *= convert
    depth_max = data_depth + max(data_depth * 0.1, 5.0 * convert)

    # Target the vs_profile subplot; fall back to active/first
    vs_plot = canvas._plots.get("vs_profile")
    sig_plot = canvas._plots.get("sigma_ln")
    target_key = prof_data.subplot_key or canvas.active_subplot
    if not vs_plot:
        vs_plot = canvas._plots.get(target_key)
        if not vs_plot:
            vs_plot = list(canvas._plots.values())[0]
        vs_plot.invertY(True)
    if not sig_plot:
        sig_plot = canvas._plots.get(f"{target_key}_sigma")

    items = {
        "vs_plot": vs_plot,
        "sig_plot": sig_plot,
        "data": prof_data,
        "item_list": [],
    }

    # --- Percentile band ---
    if prof_data.percentile_layer.visible and prof_data.depth_grid is not None:
        c = pg.mkColor(prof_data.percentile_layer.color)
        c.setAlpha(prof_data.percentile_layer.alpha)
        dg = prof_data.depth_grid * convert
        mask = dg <= depth_max
        fill_low = pg.PlotDataItem(prof_data.p_low[mask] * convert, dg[mask])
        fill_high = pg.PlotDataItem(prof_data.p_high[mask] * convert, dg[mask])
        fill = pg.FillBetweenItem(fill_low, fill_high,
                                   brush=pg.mkBrush(c))
        vs_plot.addItem(fill_low)
        vs_plot.addItem(fill_high)
        vs_plot.addItem(fill)
        fill_low.setVisible(False)
        fill_high.setVisible(False)
        items["item_list"].extend([fill_low, fill_high, fill])
        pct_ghost = pg.PlotDataItem(
            [], [], pen=pg.mkPen(color=c, width=6),
            name="5-95 Percentile",
        )
        vs_plot.addItem(pct_ghost)
        items["item_list"].append(pct_ghost)

    # --- Individual spaghetti ---
    if prof_data.individual_layer.visible and prof_data.profiles:
        n_show = min(prof_data.max_individual, len(prof_data.profiles))
        step = max(1, len(prof_data.profiles) // n_show)
        c = pg.mkColor(prof_data.individual_layer.color)
        c.setAlpha(prof_data.individual_layer.alpha)
        pen = pg.mkPen(color=c, width=prof_data.individual_layer.line_width)
        for d, v in prof_data.profiles[::step]:
            finite_mask = np.isfinite(d) & (d > 0)
            if not np.any(finite_mask):
                continue
            last_valid = np.max(np.where(finite_mask)[0])
            d_plot = (d[:last_valid + 1] * convert).copy()
            v_plot = (v[:last_valid + 1] * convert).copy()
            if d_plot[-1] < depth_max:
                d_plot = np.append(d_plot, depth_max)
                v_plot = np.append(v_plot, v_plot[-1])
            line = pg.PlotDataItem(v_plot, d_plot, pen=pen)
            vs_plot.addItem(line)
            items["item_list"].append(line)
        ghost = pg.PlotDataItem(
            [], [], pen=pg.mkPen(color=c, width=1.0),
            name=f"{prof_data.n_profiles} Profiles",
        )
        vs_plot.addItem(ghost)
        items["item_list"].append(ghost)

    # --- Bold median line ---
    if (prof_data.median_layer.visible
            and prof_data.median_depth_paired is not None):
        pen = pg.mkPen(
            color=prof_data.median_layer.color,
            width=prof_data.median_layer.line_width,
        )
        md = (prof_data.median_depth_paired * convert).copy()
        mv = (prof_data.median_vel_paired * convert).copy()
        finite_mask = np.isfinite(md) & (md > 0)
        if np.any(finite_mask):
            last_valid = np.max(np.where(finite_mask)[0])
            md = md[:last_valid + 1]
            mv = mv[:last_valid + 1]
            if md[-1] < depth_max:
                md = np.append(md, depth_max)
                mv = np.append(mv, mv[-1])
        median_line = pg.PlotDataItem(
            mv, md, pen=pen,
            name=f"Median ({prof_data.n_profiles} profiles)",
        )
        vs_plot.addItem(median_line)
        items["item_list"].append(median_line)

    # --- VsN legend entry ---
    if canvas._velocity_unit == "imperial":
        if prof_data.vs100_mean is not None:
            vsn_txt = f"Vs100 = {prof_data.vs100_mean:.0f} ft/s"
            if prof_data.vs100_std is not None:
                vsn_txt += f" (std = {prof_data.vs100_std:.1f})"
            vsn_ghost = pg.PlotDataItem([], [], pen=pg.mkPen(None),
                                         name=vsn_txt)
            vs_plot.addItem(vsn_ghost)
            items["item_list"].append(vsn_ghost)
    else:
        if prof_data.vs30_mean is not None:
            vsn_txt = f"Vs30 = {prof_data.vs30_mean:.0f} {vel_unit}"
            if prof_data.vs30_std is not None:
                vsn_txt += f" (std = {prof_data.vs30_std:.1f})"
            vsn_ghost = pg.PlotDataItem([], [], pen=pg.mkPen(None),
                                         name=vsn_txt)
            vs_plot.addItem(vsn_ghost)
            items["item_list"].append(vsn_ghost)

    # Set Y range
    vs_plot.setYRange(0, depth_max, padding=0.02)
    vs_plot.enableAutoRange(axis="x")

    # --- Sigma_ln subplot ---
    if (sig_plot and prof_data.sigma_layer.visible
            and prof_data.sigma_ln is not None):
        dg = prof_data.depth_grid * convert
        mask = dg <= depth_max
        sig_pen = pg.mkPen(
            color=prof_data.sigma_layer.color,
            width=prof_data.sigma_layer.line_width,
        )
        sig_line = pg.PlotDataItem(
            prof_data.sigma_ln[mask], dg[mask], pen=sig_pen,
            name="sigma_ln(Vs)",
        )
        sig_plot.addItem(sig_line)
        items["item_list"].append(sig_line)
        sig_max = max(0.5, float(np.nanmax(prof_data.sigma_ln[mask])) * 1.1)
        sig_plot.setXRange(0, sig_max, padding=0.05)
        sig_plot.setVisible(True)
        sig_col = canvas._get_plot_column(sig_plot)
        if sig_col is not None:
            canvas.graphics_layout.ci.layout.setColumnStretchFactor(sig_col, 1)
    elif sig_plot and not prof_data.sigma_layer.visible:
        sig_plot.setVisible(False)
        sig_col = canvas._get_plot_column(sig_plot)
        if sig_col is not None:
            canvas.graphics_layout.ci.layout.setColumnStretchFactor(sig_col, 0)

    canvas._vs_profiles[uid] = items
    canvas._apply_legend_mode()


def remove_vs_profile(canvas, uid: str):
    """Remove a VsProfileData from the canvas."""
    entry = canvas._vs_profiles.pop(uid, None)
    if not entry:
        return
    for item in entry.get("item_list", []):
        for plot_key in ("vs_plot", "sig_plot"):
            p = entry.get(plot_key)
            if p:
                try:
                    p.removeItem(item)
                except Exception:
                    pass
    canvas._apply_legend_mode()


def set_vs_profile_layer_visible(canvas, uid: str, layer_name: str,
                                  visible: bool):
    """Toggle visibility for one layer of a Vs profile."""
    entry = canvas._vs_profiles.get(uid)
    if not entry:
        return
    prof = entry["data"]
    if layer_name == "median":
        prof.median_layer.visible = visible
    elif layer_name == "percentile":
        prof.percentile_layer.visible = visible
    elif layer_name == "individual":
        prof.individual_layer.visible = visible
    elif layer_name == "sigma":
        prof.sigma_layer.visible = visible
    _rebuild_vs_profile(canvas, uid)


def _rebuild_vs_profile(canvas, uid: str):
    """Remove and re-add a profile with current settings."""
    entry = canvas._vs_profiles.get(uid)
    if not entry:
        return
    prof = entry["data"]
    remove_vs_profile(canvas, uid)
    add_vs_profile(canvas, prof)
