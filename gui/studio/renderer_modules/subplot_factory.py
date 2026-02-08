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
        # Combined — single subplot
        gs = GridSpec(
            1, 1, figure=fig,
            left=left, right=right, bottom=bottom, top=top,
        )
        return {"main": fig.add_subplot(gs[0, 0])}


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
    """Create NxM grid with mixed DC/Vs cells."""
    rows, cols = state.grid_rows, state.grid_cols
    stypes = state.subplot_types

    # Per-column logical ratios (default to equal)
    col_ratios = list(state.grid_col_ratios)
    while len(col_ratios) < cols:
        col_ratios.append(1.0)

    # Count actual columns (Vs cells need 2: main + sigma).
    # Check ALL rows per column — any vs_profile means the column is wide.
    actual_cols = 0
    col_map = {}  # grid_col -> actual_start_col
    vs_cols = set()  # logical columns that have at least one vs_profile
    width_ratios = []
    for c in range(cols):
        col_map[c] = actual_cols
        is_vs = any(
            stypes.get(f"cell_{r}_{c}") == "vs_profile"
            for r in range(rows)
        )
        r_base = max(col_ratios[c], 0.1)
        if is_vs:
            vs_cols.add(c)
            vs_r, sig_r = settings.vs_width_ratios
            width_ratios.extend([r_base * vs_r, r_base * sig_r])
            actual_cols += 2
        else:
            width_ratios.append(r_base)
            actual_cols += 1

    gs = GridSpec(
        rows, actual_cols, figure=fig,
        width_ratios=width_ratios,
        left=left, right=right, bottom=bottom, top=top,
        hspace=hspace, wspace=wspace,
    )

    axes = {}
    vs_pairs = []  # [(vs_key, sig_key), ...] for post-adjustment
    for r in range(rows):
        for c in range(cols):
            key = f"cell_{r}_{c}"
            ac = col_map[c]
            cell_type = stypes.get(key, "dc")
            if cell_type == "vs_profile":
                ax_vs = fig.add_subplot(gs[r, ac])
                ax_sig = fig.add_subplot(gs[r, ac + 1], sharey=ax_vs)
                axes[key] = ax_vs
                axes[f"{key}_sigma"] = ax_sig
                vs_pairs.append((key, f"{key}_sigma"))
            elif c in vs_cols:
                # DC cell in a column that has vs_profile elsewhere — span both
                axes[key] = fig.add_subplot(gs[r, ac:ac + 2])
            else:
                axes[key] = fig.add_subplot(gs[r, ac])

    # Adjust gap between Vs and sigma subplots using vs_wspace
    vs_ws = settings.vs_wspace
    for vs_key, sig_key in vs_pairs:
        ax_vs = axes[vs_key]
        ax_sig = axes[sig_key]
        pos_vs = ax_vs.get_position()
        pos_sig = ax_sig.get_position()
        total_w = pos_sig.x1 - pos_vs.x0
        gap_frac = vs_ws * (pos_sig.width + pos_vs.width)
        new_sig_x0 = pos_vs.x1 + gap_frac
        if new_sig_x0 < pos_sig.x1:
            ax_sig.set_position([
                new_sig_x0, pos_sig.y0,
                pos_sig.x1 - new_sig_x0, pos_sig.height,
            ])

    return axes
