"""Soil-profile (SoilProfile / SoilProfileGroup) rendering on the PyQtGraph canvas."""

import numpy as np
import pyqtgraph as pg
from PySide6.QtGui import QColor

from geo_figure.core.models import SoilProfile, SoilProfileGroup
from .constants import VEL_UNIT_STR


# ---------------------------------------------------------------------------
# Single SoilProfile
# ---------------------------------------------------------------------------

def add_soil_profile(canvas, profile: SoilProfile):
    """Render a single SoilProfile as a step function on the canvas."""
    uid = profile.uid
    convert = 3.28084 if canvas._velocity_unit == "imperial" else 1.0

    target_key = profile.subplot_key or canvas.active_subplot or "main"

    # Route to sub-section if multi-property sections exist
    prop = getattr(profile, "render_property", "vs")
    sections = canvas._soil_profile_sections.get(target_key)
    if sections and len(sections) > 1 and prop in sections:
        section_key = f"{target_key}_sp_{prop}"
        plot = canvas._plots.get(section_key)
    else:
        plot = canvas._plots.get(target_key)

    if not plot:
        plot = list(canvas._plots.values())[0] if canvas._plots else None
    if plot is None:
        return

    items = {
        "plot": plot,
        "data": profile,
        "item_list": [],
    }

    if not profile.visible:
        canvas._soil_profiles[uid] = items
        return

    vals = profile.active_values
    if vals is None or len(vals) == 0:
        canvas._soil_profiles[uid] = items
        return

    depth_arr, val_arr, hs_depth, hs_val = profile.to_step_arrays(
        unit_factor=convert,
    )

    # Ensure the plot has inverted Y for depth display
    if not plot.getViewBox().yInverted():
        plot.invertY(True)
    # Ensure X axis is linear (not log-scale from DC subplot)
    plot.setLogMode(x=False, y=False)

    # Update X-axis label (only when not in multi-section mode)
    if not (sections and len(sections) > 1):
        vel_unit = "ft/s" if canvas._velocity_unit == "imperial" else "m/s"
        prop_labels = {
            "vs": f"Vs ({vel_unit})",
            "vp": f"Vp ({vel_unit})",
            "density": "Density (kg/m3)",
        }
        plot.setLabel("bottom", prop_labels.get(prop, f"Vs ({vel_unit})"))

    # Main step curve (to_step_arrays already applied convert)
    c = pg.mkColor(profile.color)
    c.setAlpha(profile.alpha)
    pen = pg.mkPen(color=c, width=profile.line_width)

    display_name = profile.custom_name or profile.name
    line = pg.PlotDataItem(
        val_arr, depth_arr,
        pen=pen, name=display_name,
    )
    plot.addItem(line)
    items["item_list"].append(line)

    # Halfspace dashed extension
    if hs_depth is not None and hs_val is not None:
        dash_pen = pg.mkPen(
            color=c, width=profile.line_width,
            style=pg.QtCore.Qt.PenStyle.DashLine,
        )
        hs_line = pg.PlotDataItem(
            hs_val, hs_depth,
            pen=dash_pen,
        )
        plot.addItem(hs_line)
        items["item_list"].append(hs_line)

    # Uncertainty bands (if available)
    if profile.show_uncertainty:
        low = profile.vs_low if profile.vs_low is not None else None
        high = profile.vs_high if profile.vs_high is not None else None
        if low is not None and high is not None:
            _add_uncertainty_fill(
                plot, items, profile, low, high, depth_arr, convert,
            )

    canvas._soil_profiles[uid] = items
    canvas._apply_legend_mode()


def _add_uncertainty_fill(plot, items, profile, low, high, depth_arr, convert):
    """Add fill-between for Vs uncertainty bounds."""
    # Build step arrays for low/high
    n = len(low)
    d_step = []
    low_step = []
    high_step = []
    for i in range(n):
        t = profile.top_depth[i] * convert
        b = profile.bot_depth[i]
        if np.isinf(b):
            b = profile.max_depth * (1 + profile.halfspace_extension) * convert
        else:
            b *= convert
        d_step.extend([t, b])
        low_step.extend([low[i] * convert, low[i] * convert])
        high_step.extend([high[i] * convert, high[i] * convert])

    d_step = np.array(d_step)
    low_step = np.array(low_step)
    high_step = np.array(high_step)

    c = pg.mkColor(profile.color)
    c.setAlpha(min(profile.alpha // 3, 80))

    lo_item = pg.PlotDataItem(low_step, d_step)
    hi_item = pg.PlotDataItem(high_step, d_step)
    fill = pg.FillBetweenItem(lo_item, hi_item, brush=pg.mkBrush(c))
    plot.addItem(lo_item)
    plot.addItem(hi_item)
    plot.addItem(fill)
    lo_item.setVisible(False)
    hi_item.setVisible(False)
    items["item_list"].extend([lo_item, hi_item, fill])


# ---------------------------------------------------------------------------
# SoilProfileGroup
# ---------------------------------------------------------------------------

def add_soil_profile_group(canvas, group: SoilProfileGroup):
    """Render all profiles in a group, plus statistics if computed."""
    for prof in group.profiles:
        if group.group_color:
            prof.color = group.group_color
            prof.alpha = group.group_alpha
            prof.line_width = group.group_line_width
        add_soil_profile(canvas, prof)

    # Render group statistics overlay
    if group.has_statistics:
        _add_group_stats(canvas, group)


def remove_soil_profile_group(canvas, group: SoilProfileGroup):
    """Remove all profiles in a group from the canvas."""
    for prof in group.profiles:
        remove_soil_profile(canvas, prof.uid)


# ---------------------------------------------------------------------------
# Lifecycle helpers
# ---------------------------------------------------------------------------

def remove_soil_profile(canvas, uid: str):
    """Remove a single SoilProfile from the canvas."""
    entry = canvas._soil_profiles.pop(uid, None)
    if not entry:
        return
    plot = entry.get("plot")
    for item in entry.get("item_list", []):
        if plot:
            try:
                plot.removeItem(item)
            except Exception:
                pass
    canvas._apply_legend_mode()


def set_soil_profile_visible(canvas, uid: str, visible: bool):
    """Toggle visibility of a single soil profile."""
    entry = canvas._soil_profiles.get(uid)
    if not entry:
        return
    entry["data"].visible = visible
    _rebuild_soil_profile(canvas, uid)


def _rebuild_soil_profile(canvas, uid: str):
    """Remove and re-add a soil profile with current settings."""
    entry = canvas._soil_profiles.get(uid)
    if not entry:
        return
    prof = entry["data"]
    remove_soil_profile(canvas, uid)
    add_soil_profile(canvas, prof)


# ---------------------------------------------------------------------------
# Group statistics overlay
# ---------------------------------------------------------------------------

def _add_group_stats(canvas, group: SoilProfileGroup):
    """Render median line and percentile band for a group."""
    convert = 3.28084 if canvas._velocity_unit == "imperial" else 1.0
    target_key = group.subplot_key or "main"

    # Route to sub-section if multi-property sections exist
    stats_prop = getattr(group, "stats_property", "vs")
    sections = canvas._soil_profile_sections.get(target_key)
    if sections and len(sections) > 1 and stats_prop in sections:
        section_key = f"{target_key}_sp_{stats_prop}"
        plot = canvas._plots.get(section_key)
    else:
        plot = canvas._plots.get(target_key)

    if not plot:
        plot = list(canvas._plots.values())[0] if canvas._plots else None
    if plot is None:
        return

    depth = group.depth_grid * convert
    stats_key = f"_grpstats_{group.uid}"
    items = canvas._soil_profiles.get(stats_key, {
        "plot": plot, "data": group, "item_list": [],
    })
    item_list = items["item_list"]

    # Percentile band (fill between p05 and p95)
    if group.show_percentile and group.p05_values is not None:
        p05 = group.p05_values * convert
        p95 = group.p95_values * convert

        lo_item = pg.PlotDataItem(p05, depth)
        hi_item = pg.PlotDataItem(p95, depth)
        c = pg.mkColor(group.percentile_color)
        c.setAlpha(group.percentile_alpha)
        fill = pg.FillBetweenItem(lo_item, hi_item, brush=pg.mkBrush(c))
        plot.addItem(lo_item)
        plot.addItem(hi_item)
        plot.addItem(fill)
        lo_item.setVisible(False)
        hi_item.setVisible(False)
        item_list.extend([lo_item, hi_item, fill])

    # Median line
    if group.show_median and group.median_values is not None:
        median = group.median_values * convert
        c = pg.mkColor(group.median_color)
        pen = pg.mkPen(color=c, width=group.median_line_width)
        med_line = pg.PlotDataItem(
            median, depth, pen=pen,
            name=f"{group.display_name} Median",
        )
        plot.addItem(med_line)
        item_list.append(med_line)

    canvas._soil_profiles[stats_key] = items


def rebuild_group_stats(canvas, group: SoilProfileGroup):
    """Remove and re-render group statistics overlay."""
    stats_key = f"_grpstats_{group.uid}"
    entry = canvas._soil_profiles.pop(stats_key, None)
    if entry:
        plot = entry.get("plot")
        for item in entry.get("item_list", []):
            if plot:
                try:
                    plot.removeItem(item)
                except Exception:
                    pass
    if group.has_statistics:
        _add_group_stats(canvas, group)
