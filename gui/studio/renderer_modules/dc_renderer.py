"""DC dispersion curve and ensemble rendering."""
import numpy as np
import matplotlib
import matplotlib.ticker as mtick
from typing import Optional, Tuple

from geo_figure.core.models import CurveData, CurveType, EnsembleData, FigureState
from ..models import StudioSettings
from .constants import VEL_LABELS
from .axis_helpers import (
    configure_ticks, configure_grid, compute_dc_visible_bounds,
)


def render_dc_subplot(
    ax,
    subplot_key: str,
    state: FigureState,
    settings: StudioSettings,
    vf: float,
    configure_legend_fn,
):
    """Render dispersion curves and ensembles on a DC subplot.

    Parameters
    ----------
    configure_legend_fn : callable
        Function(ax, subplot_key) to configure the per-subplot legend.
    """
    # Collect data for this subplot
    curves = [c for c in state.curves if c.subplot_key == subplot_key]
    ensembles = [e for e in state.ensembles if e.subplot_key == subplot_key]

    # Configure log-scale X axis
    ax.set_xscale("log")
    ax.xaxis.set_major_formatter(mtick.ScalarFormatter())
    ax.xaxis.get_major_formatter().set_scientific(False)
    ax.xaxis.set_minor_formatter(mtick.NullFormatter())

    # Render ensembles (bottom layers first)
    for ens in ensembles:
        _render_ensemble(ax, ens, vf)

    # Render experimental/theoretical curves
    for curve in curves:
        if not curve.visible or not curve.has_data:
            continue
        _render_curve(ax, curve, vf)

    # Axis labels and config
    acfg = settings.axis_for(subplot_key)
    xlabel = acfg.x_label or "Frequency (Hz)"
    ylabel = (acfg.y_label
              or VEL_LABELS.get(state.velocity_unit, "Phase Velocity (m/s)"))
    ax.set_xlabel(xlabel, fontsize=settings.typography.axis_label_size,
                  fontweight=settings.typography.font_weight)
    ax.set_ylabel(ylabel, fontsize=settings.typography.axis_label_size,
                  fontweight=settings.typography.font_weight)

    # Axis limits
    bounds = compute_dc_visible_bounds(state, subplot_key, vf)
    if acfg.auto_x:
        if bounds:
            xmin, xmax = bounds[0], bounds[1]
            if xmin > 0 and xmax > xmin:
                lmin = np.log10(xmin)
                lmax = np.log10(xmax)
                pad = (lmax - lmin) * 0.05
                ax.set_xlim(10 ** (lmin - pad), 10 ** (lmax + pad))
    else:
        if acfg.x_min is not None and acfg.x_max is not None:
            ax.set_xlim(acfg.x_min, acfg.x_max)

    if acfg.auto_y:
        if bounds:
            ymin, ymax = bounds[2], bounds[3]
            yr = (ymax - ymin) or 1.0
            ax.set_ylim(ymin - yr * 0.05, ymax + yr * 0.05)
    else:
        if acfg.y_min is not None and acfg.y_max is not None:
            ax.set_ylim(acfg.y_min, acfg.y_max)

    tick_weight = "bold" if settings.typography.bold_ticks else "normal"
    configure_ticks(ax, acfg, tick_weight)
    configure_grid(ax, acfg)
    configure_legend_fn(ax, subplot_key)


def _render_curve(ax, curve: CurveData, vf: float):
    """Render a single CurveData on a matplotlib axis."""
    freq = curve.frequency
    vel = curve.velocity
    mask = (curve.point_mask if curve.point_mask is not None
            else np.ones(len(freq), dtype=bool))
    f = freq[mask]
    v = vel[mask] * vf

    # Resample if enabled
    if curve.resample_enabled and len(f) >= 2:
        n = curve.resample_n_points
        fmin, fmax = f.min(), f.max()
        if curve.resample_method == "log" and fmin > 0:
            new_f = np.logspace(np.log10(fmin), np.log10(fmax), n)
        else:
            new_f = np.linspace(fmin, fmax, n)
        new_v = np.interp(new_f, f, v)
        if curve.stddev is not None and len(curve.stddev) == len(freq):
            new_std = np.interp(new_f, f, curve.stddev[mask])
        else:
            new_std = None
        f, v = new_f, new_v
        stddev_plot = new_std
    else:
        stddev_plot = (curve.stddev[mask]
                       if (curve.stddev is not None
                           and len(curve.stddev) == len(freq))
                       else None)

    # Apply stddev mode overrides
    stddev_plot = _apply_stddev_mode(curve, f, stddev_plot)

    is_theoretical = curve.curve_type == CurveType.THEORETICAL
    label = curve.display_name

    if is_theoretical:
        ax.semilogx(
            f, v, color=curve.color, linewidth=curve.line_width,
            linestyle="-", label=label, zorder=4,
        )
    else:
        if (stddev_plot is not None and len(stddev_plot) == len(f)
                and curve.show_error_bars):
            if curve.stddev_type == "logstd":
                top_err = v * (np.exp(stddev_plot) - 1)
                bot_err = v * (1 - np.exp(-stddev_plot))
            else:
                top_err = stddev_plot * vf
                bot_err = stddev_plot * vf

            ax.errorbar(
                f, v, yerr=[bot_err, top_err],
                fmt=".", color=curve.color,
                markersize=curve.marker_size,
                linewidth=0.7, capsize=1.5,
                elinewidth=0.7, alpha=0.9,
                label=label, zorder=3,
            )
        else:
            ax.scatter(
                f, v, s=curve.marker_size ** 2,
                color=curve.color, edgecolors=curve.color,
                linewidths=0.5, label=label, zorder=3,
            )


def _apply_stddev_mode(curve, freq, stddev):
    """Apply stddev mode overrides (same logic as PlotCanvas)."""
    if stddev is None:
        return None
    if curve.stddev_mode == "range" and curve.stddev_ranges:
        out = np.copy(stddev)
        for fmin_r, fmax_r, val in curve.stddev_ranges:
            in_range = (freq >= fmin_r) & (freq <= fmax_r)
            out[in_range] = val
        return out
    elif curve.stddev_mode == "fixed_logstd":
        return np.full(len(freq), curve.fixed_logstd)
    elif curve.stddev_mode == "fixed_cov":
        return np.full(len(freq), curve.fixed_cov)
    return stddev


def _render_ensemble(ax, ens: EnsembleData, vf: float):
    """Render an EnsembleData with all visible layers."""
    freq = ens.freq
    if freq is None or len(freq) == 0:
        return

    # 1. Envelope (bottom, gray)
    env = ens.envelope_layer
    if env.visible and ens.envelope_min is not None:
        c = matplotlib.colors.to_rgba(env.color, alpha=env.alpha / 255.0)
        env_label = env.legend_label or "Theoretical Range"
        ax.fill_between(
            freq, ens.envelope_min * vf, ens.envelope_max * vf,
            color=c, edgecolor="k", linewidth=0.3, zorder=1,
            label=env_label,
        )

    # 2. Percentile band
    pct = ens.percentile_layer
    if pct.visible and ens.p_low is not None:
        c = matplotlib.colors.to_rgba(pct.color, alpha=pct.alpha / 255.0)
        pct_label = pct.legend_label or "16-84 Percentile"
        ax.fill_between(
            freq, ens.p_low * vf, ens.p_high * vf,
            color=c, zorder=2, label=pct_label,
        )

    # 3. Individual spaghetti
    ind = ens.individual_layer
    if (ind.visible and ens.individual_freqs is not None
            and ens.individual_vels is not None):
        c = matplotlib.colors.to_rgba(ind.color, alpha=ind.alpha / 255.0)
        count = min(len(ens.individual_freqs), ens.max_individual)
        for i in range(count):
            ax.semilogx(
                ens.individual_freqs[i],
                ens.individual_vels[i] * vf,
                color=c, linewidth=ind.line_width, zorder=1,
            )
        n_total = len(ens.individual_freqs)
        ind_label = ind.legend_label or f"{n_total} Profiles"
        ax.plot([], [], color=ind.color, linewidth=ind.line_width,
                alpha=ind.alpha / 255.0,
                label=ind_label)

    # 4. Median (top, bold)
    med = ens.median_layer
    if med.visible and ens.median is not None:
        med_label = med.legend_label or "Median"
        ax.semilogx(
            freq, ens.median * vf,
            color=med.color, linewidth=med.line_width,
            label=med_label, zorder=5,
        )
