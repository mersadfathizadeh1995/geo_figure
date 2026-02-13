"""Layout building: create and configure subplot PlotItems."""
import pyqtgraph as pg
from PySide6.QtWidgets import QMenu, QInputDialog
from PySide6.QtGui import QColor
from PySide6.QtCore import QSizeF, Qt as QtCore_Qt
from typing import Dict, Optional, Tuple

from .constants import (
    LAYOUT_COMBINED, LAYOUT_SPLIT_WAVE, LAYOUT_GRID, LAYOUT_VS_PROFILE,
    VEL_LABELS, LEGEND_ANCHORS,
)
from .log_freq_axis import LogFreqAxis
from geo_figure.core.subplot_types import (
    UNSET, DC, VS_EXTRACT, PROFILE, SOIL_PROFILE,
)


def build_layout(canvas):
    """Build plot items based on current layout mode.

    Parameters
    ----------
    canvas : PlotCanvas
        The canvas instance whose state drives the layout.
    """
    canvas.graphics_layout.clear()
    canvas._plots.clear()
    canvas._legends.clear()

    mode = canvas._layout_mode

    if mode == LAYOUT_SPLIT_WAVE:
        _build_split_wave(canvas)
    elif mode == LAYOUT_GRID:
        _build_grid(canvas)
    elif mode == LAYOUT_VS_PROFILE:
        _build_vs_profile(canvas)
    else:
        _build_combined(canvas)

    # Prune stale keys from subplot_names / subplot_types
    for store in (canvas._subplot_names, canvas._subplot_types):
        stale = [k for k in store if k not in canvas._plots]
        for k in stale:
            del store[k]

    canvas.layout_changed.emit(canvas.get_subplot_info())
    keys = list(canvas._plots.keys())
    if keys and (canvas._active_subplot not in canvas._plots):
        canvas._active_subplot = keys[0]


# ── Layout builders ──────────────────────────────────────────────


def _build_combined(canvas):
    name = canvas._subplot_names.get("main", "")
    cell_type = canvas._subplot_types.get("main", UNSET)
    sections = canvas._soil_profile_sections.get("main")

    if cell_type == SOIL_PROFILE and sections and len(sections) > 1:
        # Multi-property sub-sections (Vs + Vp + Density)
        sub = canvas.graphics_layout.addLayout(row=0, col=0)
        sub.setContentsMargins(0, 0, 0, 0)
        sub.layout.setSpacing(0)
        sub.setMinimumSize(0, 0)
        sub.setPreferredSize(0, 0)
        canvas._subplot_names.setdefault("main", "")
        canvas._subplot_types["main"] = SOIL_PROFILE
        _build_section_cell(canvas, sub, "main", sections, name, None)
    elif cell_type == VS_EXTRACT:
        p = canvas.graphics_layout.addPlot(row=0, col=0)
        if name:
            p.setTitle(name)
        canvas._plots["main"] = p
        canvas._subplot_names.setdefault("main", "")
        canvas._subplot_types["main"] = VS_EXTRACT
        configure_vs_plot(canvas, p, "main")
    elif cell_type == PROFILE:
        p = canvas.graphics_layout.addPlot(row=0, col=0)
        if name:
            p.setTitle(name)
        canvas._plots["main"] = p
        canvas._subplot_names.setdefault("main", "")
        canvas._subplot_types["main"] = PROFILE
        configure_profile_plot(canvas, p, "main")
    elif cell_type == DC:
        p = canvas.graphics_layout.addPlot(
            row=0, col=0,
            axisItems={"bottom": LogFreqAxis(orientation="bottom")},
        )
        if name:
            p.setTitle(name)
        canvas._plots["main"] = p
        canvas._subplot_names.setdefault("main", "")
        canvas._subplot_types["main"] = DC
        configure_dc_plot(canvas, p, "main")
    else:
        # UNSET or unknown -- blank subplot
        p = canvas.graphics_layout.addPlot(row=0, col=0)
        if name:
            p.setTitle(name)
        canvas._plots["main"] = p
        canvas._subplot_names.setdefault("main", "")
        canvas._subplot_types.setdefault("main", UNSET)
        configure_blank_plot(canvas, p, "main")


def _build_split_wave(canvas):
    ray_name = canvas._subplot_names.get("rayleigh", "Rayleigh")
    love_name = canvas._subplot_names.get("love", "Love")
    p_ray = canvas.graphics_layout.addPlot(
        row=0, col=0,
        axisItems={"bottom": LogFreqAxis(orientation="bottom")},
        title=ray_name,
    )
    p_love = canvas.graphics_layout.addPlot(
        row=0, col=1,
        axisItems={"bottom": LogFreqAxis(orientation="bottom")},
        title=love_name,
    )
    canvas._plots["rayleigh"] = p_ray
    canvas._plots["love"] = p_love
    canvas._subplot_names.setdefault("rayleigh", "Rayleigh")
    canvas._subplot_names.setdefault("love", "Love")
    canvas._subplot_types["rayleigh"] = DC
    canvas._subplot_types["love"] = DC
    for key in ["rayleigh", "love"]:
        configure_dc_plot(canvas, canvas._plots[key], key)
    if canvas._link_y:
        p_love.setYLink(p_ray)
    if canvas._link_x:
        p_love.setXLink(p_ray)


def _build_grid(canvas):
    first_dc = None
    first_vs = None
    rows = canvas._grid_rows
    cols = canvas._grid_cols
    ratios = list(canvas._grid_col_ratios)
    while len(ratios) < cols:
        ratios.append(1.0)

    # Set stretch factors: 1 actual column per logical column (equal treatment)
    for c in range(cols):
        col_ratio = max(ratios[c], 0.1)
        canvas.graphics_layout.ci.layout.setColumnStretchFactor(
            c, round(col_ratio * 100))

    vs_r, sig_r = canvas._vs_internal_ratios

    for r in range(rows):
        for c in range(cols):
            key = f"cell_{r}_{c}"
            cell_type = canvas._subplot_types.get(key, UNSET)
            default_name = f"Subplot ({r+1},{c+1})"
            name = canvas._subplot_names.get(key, default_name)
            canvas._subplot_names.setdefault(key, default_name)
            canvas._subplot_types.setdefault(key, UNSET)

            if cell_type == SOIL_PROFILE:
                sections = canvas._soil_profile_sections.get(key)
                if sections and len(sections) > 1:
                    sub = canvas.graphics_layout.addLayout(row=r, col=c)
                    sub.setContentsMargins(0, 0, 0, 0)
                    sub.layout.setSpacing(0)
                    sub.setMinimumSize(0, 0)
                    sub.setPreferredSize(0, 0)
                    p = _build_section_cell(
                        canvas, sub, key, sections, name, first_vs
                    )
                    if first_vs is None:
                        first_vs = p
                    elif canvas._link_y and p is not None:
                        p.setYLink(first_vs)
                else:
                    p = canvas.graphics_layout.addPlot(
                        row=r, col=c, title=name,
                    )
                    canvas._plots[key] = p
                    configure_profile_plot(canvas, p, key)
                    if first_vs is None:
                        first_vs = p
                    elif canvas._link_y:
                        p.setYLink(first_vs)

            elif cell_type == VS_EXTRACT:
                needs_sigma = key in canvas._vs_extraction_keys
                if needs_sigma:
                    sub = canvas.graphics_layout.addLayout(row=r, col=c)
                    sub.setContentsMargins(0, 0, 0, 0)
                    sub.layout.setSpacing(0)
                    sub.setMinimumSize(0, 0)
                    sub.setPreferredSize(0, 0)
                    total = vs_r + sig_r
                    sub.layout.setColumnStretchFactor(
                        0, round((vs_r / total) * 100))
                    sub.layout.setColumnStretchFactor(
                        1, round((sig_r / total) * 100))

                    p = sub.addPlot(row=0, col=0, title=name)
                    canvas._plots[key] = p
                    configure_vs_plot(canvas, p, key)

                    sig_key = f"{key}_sigma"
                    p_sig = sub.addPlot(row=0, col=1)
                    canvas._plots[sig_key] = p_sig
                    configure_sigma_plot(canvas, p_sig, sig_key)
                    p_sig.setYLink(p)
                else:
                    p = canvas.graphics_layout.addPlot(
                        row=r, col=c, title=name,
                    )
                    canvas._plots[key] = p
                    configure_vs_plot(canvas, p, key)

                if first_vs is None:
                    first_vs = p
                elif canvas._link_y:
                    p.setYLink(first_vs)

            elif cell_type == PROFILE:
                p = canvas.graphics_layout.addPlot(
                    row=r, col=c, title=name,
                )
                canvas._plots[key] = p
                configure_profile_plot(canvas, p, key)
                if first_vs is None:
                    first_vs = p
                elif canvas._link_y:
                    p.setYLink(first_vs)

            elif cell_type == DC:
                p = canvas.graphics_layout.addPlot(
                    row=r, col=c,
                    axisItems={"bottom": LogFreqAxis(orientation="bottom")},
                    title=name,
                )
                canvas._plots[key] = p
                configure_dc_plot(canvas, p, key)

                if first_dc is None:
                    first_dc = p
                else:
                    if canvas._link_y:
                        p.setYLink(first_dc)
                    if canvas._link_x:
                        p.setXLink(first_dc)

            else:
                # UNSET -- blank subplot
                p = canvas.graphics_layout.addPlot(
                    row=r, col=c, title=name,
                )
                canvas._plots[key] = p
                configure_blank_plot(canvas, p, key)

    # Normalize preferred widths so column stretch factors control sizing
    outer_layout = canvas.graphics_layout.ci.layout
    for r in range(rows):
        for c in range(cols):
            item = outer_layout.itemAt(r, c)
            if item is not None:
                item.setPreferredWidth(0)
                item.setMinimumWidth(0)


def _build_vs_profile(canvas):
    vs_name = canvas._subplot_names.get("vs_profile", "Vs Profile")
    sig_name = canvas._subplot_names.get("sigma_ln", "")
    canvas._subplot_names.setdefault("vs_profile", "Vs Profile")
    canvas._subplot_names.setdefault("sigma_ln", "")
    canvas._subplot_types["vs_profile"] = VS_EXTRACT
    canvas._subplot_types["sigma_ln"] = "sigma_ln"

    p_vs = canvas.graphics_layout.addPlot(row=0, col=0, title=vs_name)
    canvas._plots["vs_profile"] = p_vs
    configure_vs_plot(canvas, p_vs, "vs_profile")

    p_sig = canvas.graphics_layout.addPlot(row=0, col=1, title=sig_name)
    canvas._plots["sigma_ln"] = p_sig
    configure_sigma_plot(canvas, p_sig, "sigma_ln")

    p_sig.setYLink(p_vs)
    vs_r, sig_r = canvas._vs_internal_ratios
    canvas.graphics_layout.ci.layout.setColumnStretchFactor(
        0, round(vs_r * 100))
    canvas.graphics_layout.ci.layout.setColumnStretchFactor(
        1, round(sig_r * 100))


# ── Plot configuration helpers ───────────────────────────────────


def configure_dc_plot(canvas, plot: pg.PlotItem, subplot_key: str):
    """Apply standard DC dispersion curve configuration to a plot."""
    plot.setLabel("bottom", "Frequency (Hz)")
    plot.setLabel("left", VEL_LABELS.get(canvas._velocity_unit,
                                          "Phase Velocity (m/s)"))
    plot.showGrid(x=True, y=True, alpha=0.15)
    for axis_name in ["bottom", "left"]:
        axis = plot.getAxis(axis_name)
        axis.enableAutoSIPrefix(False)
        axis.setStyle(tickFont=pg.QtGui.QFont("Segoe UI", 9))
    plot.setMouseEnabled(x=True, y=True)
    plot.enableAutoRange()
    plot.vb.menu = build_context_menu(canvas, plot)
    plot.scene().sigMouseClicked.connect(
        lambda ev, p=plot: canvas._on_plot_clicked(ev, p)
    )
    _add_legend_to_plot(canvas, plot, subplot_key)


def configure_vs_plot(canvas, plot: pg.PlotItem, subplot_key: str):
    """Configure a Vs profile subplot: linear axes, inverted Y (depth)."""
    vel_unit = "ft/s" if canvas._velocity_unit == "imperial" else "m/s"
    depth_unit = "ft" if canvas._velocity_unit == "imperial" else "m"
    plot.setLabel("bottom", f"Vs ({vel_unit})")
    plot.setLabel("left", f"Depth ({depth_unit})")
    plot.showGrid(x=True, y=True, alpha=0.3)
    plot.invertY(True)
    for axis_name in ["bottom", "left"]:
        axis = plot.getAxis(axis_name)
        axis.enableAutoSIPrefix(False)
        axis.setStyle(tickFont=pg.QtGui.QFont("Segoe UI", 9))
    plot.setMouseEnabled(x=True, y=True)
    plot.enableAutoRange()
    plot.vb.menu = build_context_menu(canvas, plot)
    plot.scene().sigMouseClicked.connect(
        lambda ev, p=plot: canvas._on_plot_clicked(ev, p)
    )
    _add_legend_to_plot(canvas, plot, subplot_key)


def configure_sigma_plot(canvas, plot: pg.PlotItem, subplot_key: str):
    """Configure the sigma_ln subplot: narrow, shares Y with Vs plot."""
    plot.setLabel("bottom", "sigma_ln(Vs)")
    plot.setLabel("left", "")
    plot.showGrid(x=True, y=True, alpha=0.3)
    plot.invertY(True)
    plot.getAxis("left").setStyle(showValues=False)
    plot.getAxis("left").setWidth(0)
    # Minimise right-axis padding
    plot.getAxis("right").setWidth(0)
    for axis_name in ["bottom"]:
        axis = plot.getAxis(axis_name)
        axis.enableAutoSIPrefix(False)
        axis.setStyle(tickFont=pg.QtGui.QFont("Segoe UI", 9))
    plot.setMouseEnabled(x=True, y=True)
    plot.setXRange(0, 0.5, padding=0.05)
    # Remove title space to reduce overhead
    plot.setTitle("")
    plot.vb.menu = build_context_menu(canvas, plot)
    plot.scene().sigMouseClicked.connect(
        lambda ev, p=plot: canvas._on_plot_clicked(ev, p)
    )
    _add_legend_to_plot(canvas, plot, subplot_key)


def configure_blank_plot(canvas, plot: pg.PlotItem, subplot_key: str):
    """Configure a blank (unset) subplot -- minimal axes, no labels."""
    plot.setLabel("bottom", "")
    plot.setLabel("left", "")
    plot.showGrid(x=True, y=True, alpha=0.1)
    for axis_name in ["bottom", "left"]:
        axis = plot.getAxis(axis_name)
        axis.enableAutoSIPrefix(False)
        axis.setStyle(tickFont=pg.QtGui.QFont("Segoe UI", 9))
    plot.setMouseEnabled(x=True, y=True)
    plot.enableAutoRange()
    plot.vb.menu = build_context_menu(canvas, plot)
    plot.scene().sigMouseClicked.connect(
        lambda ev, p=plot: canvas._on_plot_clicked(ev, p)
    )


def configure_profile_plot(canvas, plot: pg.PlotItem, subplot_key: str):
    """Configure a profile subplot: linear axes, inverted Y, no sigma pane."""
    vel_unit = "ft/s" if canvas._velocity_unit == "imperial" else "m/s"
    depth_unit = "ft" if canvas._velocity_unit == "imperial" else "m"
    plot.setLabel("bottom", f"Vs ({vel_unit})")
    plot.setLabel("left", f"Depth ({depth_unit})")
    plot.showGrid(x=True, y=True, alpha=0.3)
    plot.invertY(True)
    for axis_name in ["bottom", "left"]:
        axis = plot.getAxis(axis_name)
        axis.enableAutoSIPrefix(False)
        axis.setStyle(tickFont=pg.QtGui.QFont("Segoe UI", 9))
    plot.setMouseEnabled(x=True, y=True)
    plot.enableAutoRange()
    plot.vb.menu = build_context_menu(canvas, plot)
    plot.scene().sigMouseClicked.connect(
        lambda ev, p=plot: canvas._on_plot_clicked(ev, p)
    )
    _add_legend_to_plot(canvas, plot, subplot_key)


_SECTION_LABELS = {"vs": "Vs", "vp": "Vp", "density": "Density"}


def configure_section_plot(canvas, plot: pg.PlotItem, subplot_key: str,
                           prop: str, is_first: bool):
    """Configure one sub-section of a multi-property soil profile cell."""
    vel_unit = "ft/s" if canvas._velocity_unit == "imperial" else "m/s"
    depth_unit = "ft" if canvas._velocity_unit == "imperial" else "m"
    if prop == "density":
        x_label = "Density (kg/m3)"
    else:
        x_label = f"{_SECTION_LABELS.get(prop, prop)} ({vel_unit})"
    plot.setLabel("bottom", x_label)
    if is_first:
        plot.setLabel("left", f"Depth ({depth_unit})")
    else:
        plot.setLabel("left", "")
        plot.getAxis("left").setStyle(showValues=False)
        plot.getAxis("left").setWidth(0)
    plot.showGrid(x=True, y=True, alpha=0.3)
    plot.invertY(True)
    for axis_name in ["bottom", "left"]:
        axis = plot.getAxis(axis_name)
        axis.enableAutoSIPrefix(False)
        axis.setStyle(tickFont=pg.QtGui.QFont("Segoe UI", 9))
    plot.setMouseEnabled(x=True, y=True)
    plot.enableAutoRange()
    plot.vb.menu = build_context_menu(canvas, plot)
    plot.scene().sigMouseClicked.connect(
        lambda ev, p=plot: canvas._on_plot_clicked(ev, p)
    )
    _add_legend_to_plot(canvas, plot, subplot_key)


def _build_section_cell(canvas, sub, key, sections, title, first_vs_ref):
    """Build multi-property sub-section plots within a sub-layout.

    Returns the first PlotItem created (for Y-axis linking).
    """
    n = len(sections)
    for i in range(n):
        sub.layout.setColumnStretchFactor(i, 100)
    first_plot = None
    for i, prop in enumerate(sections):
        sec_key = f"{key}_sp_{prop}"
        is_first = (i == 0)
        p = sub.addPlot(row=0, col=i, title=(title if is_first else ""))
        canvas._plots[sec_key] = p
        configure_section_plot(canvas, p, sec_key, prop, is_first)
        if first_plot is None:
            first_plot = p
        else:
            p.setYLink(first_plot)
    # Also register the parent key pointing to the first section
    if first_plot is not None:
        canvas._plots[key] = first_plot
    return first_plot


def _add_legend_to_plot(canvas, plot: pg.PlotItem, subplot_key: str):
    """Add a legend to a plot if legends are enabled."""
    if not canvas._legend_visible:
        return
    anchor = LEGEND_ANCHORS.get(canvas._legend_pos, ((1, 0), (1, 0)))
    legend = plot.addLegend(offset=canvas._legend_offset)
    legend.anchor(*anchor)
    legend.setLabelTextSize(f"{canvas._legend_font_size}pt")
    canvas._legends[subplot_key] = legend


def build_context_menu(canvas, plot: pg.PlotItem) -> QMenu:
    """Build a clean context menu for a plot."""
    menu = QMenu()
    menu.addAction("Fit to Data", lambda p=plot: p.enableAutoRange())
    menu.addSeparator()

    grid_action = menu.addAction("Toggle Grid")
    grid_action.triggered.connect(
        lambda checked, p=plot: p.showGrid(
            x=not p.ctrl.xGridCheck.isChecked(),
            y=not p.ctrl.yGridCheck.isChecked(),
            alpha=0.15,
        )
    )

    legend_action = menu.addAction(
        "Hide Legend" if canvas._legend_visible else "Show Legend"
    )
    legend_action.triggered.connect(
        lambda: canvas.set_legend_visible(not canvas._legend_visible)
    )
    menu.addSeparator()

    rename_action = menu.addAction("Rename Subplot...")
    rename_action.triggered.connect(
        lambda: _rename_subplot_from_menu(canvas, plot)
    )

    clear_action = menu.addAction("Clear Data")
    clear_action.triggered.connect(
        lambda: _clear_subplot_from_menu(canvas, plot)
    )

    menu.addSeparator()
    menu.addAction("Export Canvas Image...", canvas._on_export_action)
    return menu


def _rename_subplot_from_menu(canvas, plot):
    """Rename the clicked subplot via dialog."""
    key = None
    for k, p in canvas._plots.items():
        if p is plot:
            key = k
            break
    if key is None:
        return
    current_name = canvas._subplot_names.get(key, key)
    new_name, ok = QInputDialog.getText(
        canvas, "Rename Subplot", "New name:", text=current_name
    )
    if ok and new_name.strip():
        canvas.rename_subplot(key, new_name.strip())


def _clear_subplot_from_menu(canvas, plot):
    """Clear all data from the clicked subplot."""
    key = None
    for k, p in canvas._plots.items():
        if p is plot:
            key = k
            break
    if key is None:
        return
    # Resolve section keys (e.g. cell_0_0_sp_vs -> cell_0_0)
    if "_sp_" in key:
        key = key.rsplit("_sp_", 1)[0]
    canvas.clear_subplot(key)
