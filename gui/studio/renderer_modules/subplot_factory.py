"""Subplot layout creation for the matplotlib renderer.

Handles creating axes layouts: single, split_wave, grid (with mixed DC/Vs),
and dedicated Vs profile layout.
"""
from matplotlib.figure import Figure
from matplotlib.gridspec import GridSpec
from typing import Dict

from geo_figure.core.models import FigureState
from ..models import StudioSettings


def create_subplots(
    fig: Figure,
    state: FigureState,
    settings: StudioSettings,
) -> Dict[str, object]:
    """Create axes according to layout_mode. Returns {subplot_key: ax}."""
    s = settings.figure

    # Convert inch margins to figure fractions
    w = max(s.width, 0.1)
    h = max(s.height, 0.1)
    left = s.margin_left / w
    right = 1.0 - s.margin_right / w
    bottom = s.margin_bottom / h
    top = 1.0 - s.margin_top / h

    # Available plot area in inches
    plot_h = max((top - bottom) * h, 0.1)
    plot_w = max((right - left) * w, 0.1)

    sections = getattr(state, 'soil_profile_sections', {}) or {}

    if state.layout_mode == "vs_profile":
        return _create_vs_profile_layout(fig, settings, left, right, top, bottom)
    elif state.layout_mode == "split_wave":
        avg_w = plot_w / 2.0
        ws = s.vspace / avg_w if avg_w > 0 else 0.2
        gs = GridSpec(
            1, 2, figure=fig,
            left=left, right=right, bottom=bottom, top=top,
            wspace=ws,
        )
        return {"rayleigh": fig.add_subplot(gs[0, 0]),
                "love": fig.add_subplot(gs[0, 1])}
    elif state.layout_mode == "grid":
        rows = max(state.grid_rows, 1)
        cols = max(state.grid_cols, 1)
        avg_h = plot_h / rows
        avg_w = plot_w / cols
        hs = s.hspace / avg_h if avg_h > 0 else 0.2
        ws = s.vspace / avg_w if avg_w > 0 else 0.2
        return _create_grid_layout(
            fig, state, settings, left, right, top, bottom, hs, ws,
        )
    else:
        # Combined — single subplot or multi-section
        main_sections = sections.get("main")
        if main_sections and len(main_sections) > 1:
            return _create_section_layout(
                fig, "main", main_sections, left, right, top, bottom
            )
        gs = GridSpec(
            1, 1, figure=fig,
            left=left, right=right, bottom=bottom, top=top,
        )
        return {"main": fig.add_subplot(gs[0, 0])}


def _create_section_layout(
    fig: Figure,
    parent_key: str,
    sections: list,
    left: float, right: float, top: float, bottom: float,
) -> Dict[str, object]:
    """Create side-by-side sub-sections for multi-property soil profile."""
    from matplotlib.gridspec import GridSpec as GS
    n = len(sections)
    gs = GS(
        1, n, figure=fig,
        left=left, right=right, bottom=bottom, top=top,
        wspace=0.05,
    )
    axes = {}
    first_ax = None
    for i, prop in enumerate(sections):
        sec_key = f"{parent_key}_sp_{prop}"
        if first_ax is None:
            ax = fig.add_subplot(gs[0, i])
            first_ax = ax
        else:
            ax = fig.add_subplot(gs[0, i], sharey=first_ax)
        axes[sec_key] = ax
    # Map parent key to first section
    if first_ax is not None:
        axes[parent_key] = first_ax
    return axes


def _create_vs_profile_layout(
    fig: Figure,
    settings: StudioSettings,
    left: float, right: float, top: float, bottom: float,
) -> Dict[str, object]:
    """Create 2-column Vs Profile layout (Vs + sigma_ln)."""
    ws = settings.vs_wspace
    ratios = list(settings.vs_width_ratios)
    gs = GridSpec(
        1, 2, figure=fig,
        width_ratios=ratios,
        left=left, right=right, bottom=bottom, top=top,
        wspace=ws,
    )
    ax_vs = fig.add_subplot(gs[0, 0])
    ax_sig = fig.add_subplot(gs[0, 1], sharey=ax_vs)
    return {"vs_profile": ax_vs, "sigma_ln": ax_sig}


def _create_grid_layout(
    fig: Figure,
    state: FigureState,
    settings: StudioSettings,
    left: float, right: float, top: float, bottom: float,
    hspace: float, wspace: float,
) -> Dict[str, object]:
    """Create NxM grid with mixed DC/Vs cells.

    Vs columns use a nested GridSpecFromSubplotSpec so they occupy exactly
    the same total width as a DC column.
    """
    from matplotlib.gridspec import GridSpecFromSubplotSpec

    rows, cols = state.grid_rows, state.grid_cols
    stypes = state.subplot_types
    sections = getattr(state, 'soil_profile_sections', {}) or {}

    col_ratios = list(state.grid_col_ratios)
    while len(col_ratios) < cols:
        col_ratios.append(1.0)

    # Detect which logical columns contain at least one vs_profile
    vs_cols = set()
    for c in range(cols):
        if any(stypes.get(f"cell_{r}_{c}") == "vs_profile"
               for r in range(rows)):
            vs_cols.add(c)

    # One gridspec column per logical column (equal treatment)
    gs = GridSpec(
        rows, cols, figure=fig,
        width_ratios=[max(r, 0.1) for r in col_ratios],
        left=left, right=right, bottom=bottom, top=top,
        hspace=hspace, wspace=wspace,
    )

    axes = {}
    vs_r, sig_r = settings.vs_width_ratios
    vs_ws = settings.vs_wspace

    for r in range(rows):
        for c in range(cols):
            key = f"cell_{r}_{c}"
            cell_type = stypes.get(key, "dc")
            cell_sections = sections.get(key)

            if cell_type == "vs_profile" and cell_sections and len(cell_sections) > 1:
                # Multi-property sub-sections
                n_sec = len(cell_sections)
                inner = GridSpecFromSubplotSpec(
                    1, n_sec,
                    subplot_spec=gs[r, c],
                    wspace=0.05,
                )
                first_ax = None
                for i, prop in enumerate(cell_sections):
                    sec_key = f"{key}_sp_{prop}"
                    if first_ax is None:
                        ax = fig.add_subplot(inner[0, i])
                        first_ax = ax
                    else:
                        ax = fig.add_subplot(inner[0, i], sharey=first_ax)
                    axes[sec_key] = ax
                if first_ax is not None:
                    axes[key] = first_ax
            elif cell_type == "vs_profile":
                # Subdivide this single cell into 2 sub-columns
                inner = GridSpecFromSubplotSpec(
                    1, 2,
                    subplot_spec=gs[r, c],
                    width_ratios=[vs_r, sig_r],
                    wspace=vs_ws,
                )
                ax_vs = fig.add_subplot(inner[0, 0])
                ax_sig = fig.add_subplot(inner[0, 1], sharey=ax_vs)
                axes[key] = ax_vs
                axes[f"{key}_sigma"] = ax_sig
            elif c in vs_cols:
                axes[key] = fig.add_subplot(gs[r, c])
            else:
                axes[key] = fig.add_subplot(gs[r, c])

    return axes
