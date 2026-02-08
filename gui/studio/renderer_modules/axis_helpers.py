"""Axis configuration helpers: ticks, grid, frequency tick modes, bounds."""
import numpy as np
import matplotlib.ticker as mtick
from typing import Dict, List, Optional, Tuple

from geo_figure.core.models import FigureState
from ..models import StudioSettings, AxisConfig


def configure_ticks(ax, acfg: AxisConfig, tick_weight: str = "normal"):
    """Configure tick marks on an axis."""
    tc = acfg.ticks
    ax.tick_params(
        direction=tc.direction,
        which="both",
        top=tc.show_top,
        right=tc.show_right,
        bottom=True, left=True,
        length=tc.major_length,
    )
    ax.tick_params(
        which="minor",
        length=tc.minor_length,
    )
    if tc.show_minor:
        if ax.get_xscale() != "log":
            ax.xaxis.set_minor_locator(mtick.AutoMinorLocator())
        if ax.get_yscale() != "log":
            ax.yaxis.set_minor_locator(mtick.AutoMinorLocator())
    # Bold tick labels
    for label in ax.get_xticklabels() + ax.get_yticklabels():
        label.set_fontweight(tick_weight)


def configure_grid(ax, acfg: AxisConfig):
    """Configure grid lines on an axis."""
    gc = acfg.grid
    if gc.show:
        ax.grid(
            True, which=gc.which,
            color=gc.color, alpha=gc.alpha,
            linestyle=gc.linestyle, linewidth=gc.linewidth,
        )
    else:
        ax.grid(False)


def apply_freq_ticks(ax, acfg: AxisConfig, state: FigureState,
                     subplot_key: str):
    """Apply frequency tick mode to x-axis."""
    mode = acfg.freq_tick_mode
    if mode == "default":
        return

    xlim = ax.get_xlim()
    xlo, xhi = max(xlim[0], 1e-6), max(xlim[1], 1e-6)

    if mode == "clean":
        candidates = [
            0.5, 1, 1.5, 2, 3, 4, 5, 7, 10, 15, 20, 30, 40, 50, 70,
            100, 150, 200, 300, 500, 700, 1000, 1500, 2000, 3000, 5000,
        ]
        ticks = [v for v in candidates if xlo * 0.9 <= v <= xhi * 1.1]
        if not ticks:
            return
    elif mode == "data_sampled":
        all_freqs = collect_frequencies(state, subplot_key)
        if not all_freqs:
            return
        n_target = min(12, len(all_freqs))
        if len(all_freqs) <= n_target:
            ticks = all_freqs
        else:
            log_freqs = np.log10(all_freqs)
            indices = np.round(
                np.linspace(0, len(log_freqs) - 1, n_target)
            ).astype(int)
            ticks = [all_freqs[i] for i in sorted(set(indices))]
    elif mode == "custom":
        ticks = parse_custom_ticks(acfg.freq_tick_custom)
        if not ticks:
            return
    else:
        return

    ax.xaxis.set_major_locator(mtick.FixedLocator(ticks))
    fmt = mtick.FuncFormatter(_freq_label_formatter)
    ax.xaxis.set_major_formatter(fmt)
    ax.xaxis.set_minor_locator(mtick.NullLocator())


def _freq_label_formatter(val, pos):
    """Format frequency tick labels: integer if whole, else 1 decimal."""
    if val <= 0:
        return ""
    if val == int(val):
        return f"{int(val)}"
    if val < 10:
        return f"{val:.1f}"
    return f"{val:.0f}"


def parse_custom_ticks(text: str) -> List[float]:
    """Parse comma/space separated tick values."""
    ticks = []
    for part in text.replace(",", " ").split():
        try:
            v = float(part.strip())
            if v > 0:
                ticks.append(v)
        except ValueError:
            continue
    return sorted(ticks)


def collect_frequencies(state: FigureState, subplot_key: str) -> List[float]:
    """Collect unique frequency values from visible curves in a subplot."""
    freqs = set()
    for c in state.curves:
        if c.subplot_key == subplot_key and c.visible and c.has_data:
            mask = (c.point_mask if c.point_mask is not None
                    else np.ones(len(c.frequency), dtype=bool))
            for f in c.frequency[mask]:
                if np.isfinite(f) and f > 0:
                    freqs.add(float(f))
    return sorted(freqs)


def compute_dc_visible_bounds(
    state: FigureState,
    subplot_key: str,
    vf: float,
) -> Optional[Tuple[float, float, float, float]]:
    """Compute (xmin, xmax, ymin, ymax) from visible data only."""
    x_all: List[float] = []
    y_all: List[float] = []

    for c in state.curves:
        if c.subplot_key != subplot_key or not c.visible or not c.has_data:
            continue
        mask = (c.point_mask if c.point_mask is not None
                else np.ones(len(c.frequency), dtype=bool))
        f = c.frequency[mask]
        v = c.velocity[mask] * vf
        valid = np.isfinite(f) & (f > 0) & np.isfinite(v)
        if np.any(valid):
            x_all.extend(f[valid].tolist())
            y_all.extend(v[valid].tolist())
        # Include error bar extent
        if (c.show_error_bars and c.stddev is not None
                and len(c.stddev) == len(c.frequency)):
            sd = c.stddev[mask]
            v_arr = c.velocity[mask] * vf
            if c.stddev_type == "logstd":
                top = v_arr * np.exp(sd)
                bot = v_arr * np.exp(-sd)
            else:
                top = v_arr + sd * vf
                bot = v_arr - sd * vf
            valid2 = np.isfinite(top) & np.isfinite(bot)
            if np.any(valid2):
                y_all.extend(top[valid2].tolist())
                y_all.extend(bot[valid2].tolist())

    for e in state.ensembles:
        if e.subplot_key != subplot_key or e.freq is None:
            continue
        freq = e.freq
        if e.median_layer.visible and e.median is not None:
            x_all.extend(freq.tolist())
            y_all.extend((e.median * vf).tolist())
        if e.envelope_layer.visible and e.envelope_min is not None:
            x_all.extend(freq.tolist())
            y_all.extend((e.envelope_min * vf).tolist())
            y_all.extend((e.envelope_max * vf).tolist())
        if e.percentile_layer.visible and e.p_low is not None:
            x_all.extend(freq.tolist())
            y_all.extend((e.p_low * vf).tolist())
            y_all.extend((e.p_high * vf).tolist())

    if not x_all or not y_all:
        return None

    xa = np.array(x_all)
    ya = np.array(y_all)
    vx = xa[np.isfinite(xa) & (xa > 0)]
    vy = ya[np.isfinite(ya)]
    if len(vx) == 0 or len(vy) == 0:
        return None
    return (float(vx.min()), float(vx.max()),
            float(vy.min()), float(vy.max()))
