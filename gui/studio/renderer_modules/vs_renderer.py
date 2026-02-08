"""Vs profile subplot rendering (Vs + sigma_ln)."""
import numpy as np
import matplotlib
import matplotlib.ticker as mtick

from geo_figure.core.models import VsProfileData, FigureState
from ..models import StudioSettings
from .constants import VS_LABELS, DEPTH_LABELS, VEL_UNIT
from .axis_helpers import configure_ticks, configure_grid


def render_vs_subplot(
    ax_vs,
    ax_sig,
    subplot_key: str,
    state: FigureState,
    settings: StudioSettings,
    vf: float,
    configure_legend_fn,
):
    """Render Vs profiles on the Vs + sigma_ln subplots.

    Parameters
    ----------
    configure_legend_fn : callable
        Function(ax, subplot_key) to configure the per-subplot legend.
    """
    vel_unit = VEL_UNIT.get(state.velocity_unit, "m/s")

    vs_profs = getattr(state, "vs_profiles", [])
    matching = [p for p in vs_profs if (
        p.subplot_key == subplot_key
        or p.subplot_key == "vs_profile"
        or p.subplot_key == "main"
    )]

    any_sigma_visible = False
    for prof in matching:
        _render_one_vs_profile(ax_vs, ax_sig, prof, vf, vel_unit, state)
        if prof.sigma_layer.visible and prof.sigma_ln is not None:
            any_sigma_visible = True

    # Configure Vs axis
    acfg = settings.axis_for(subplot_key)
    vs_label = acfg.x_label or VS_LABELS.get(state.velocity_unit, "Vs (m/s)")
    depth_label = (acfg.y_label
                   or DEPTH_LABELS.get(state.velocity_unit, "Depth (m)"))
    ax_vs.set_xlabel(vs_label, fontsize=settings.typography.axis_label_size,
                     fontweight=settings.typography.font_weight)
    ax_vs.set_ylabel(depth_label, fontsize=settings.typography.axis_label_size,
                     fontweight=settings.typography.font_weight)
    ax_vs.invert_yaxis()

    if not acfg.auto_x and acfg.x_min is not None:
        ax_vs.set_xlim(acfg.x_min, acfg.x_max)
    if not acfg.auto_y and acfg.y_min is not None:
        ax_vs.set_ylim(acfg.y_max, acfg.y_min)  # inverted

    tick_weight = "bold" if settings.typography.bold_ticks else "normal"
    configure_ticks(ax_vs, acfg, tick_weight)
    configure_grid(ax_vs, acfg)
    configure_legend_fn(ax_vs, subplot_key)

    # Configure sigma_ln axis — hide entirely if no sigma data visible
    if ax_sig is not None:
        if any_sigma_visible:
            sig_key = ("sigma_ln" if subplot_key == "vs_profile"
                       else f"{subplot_key}_sigma")
            _configure_sigma_axis(ax_sig, sig_key, settings)
        else:
            ax_sig.set_visible(False)


def _render_one_vs_profile(
    ax_vs, ax_sig,
    prof: VsProfileData,
    vf: float,
    vel_unit: str,
    state: FigureState,
):
    """Render a single VsProfileData."""
    convert = vf

    # Determine depth range from data
    data_depth = 0.0
    if prof.profiles:
        for d, v in prof.profiles:
            finite = d[np.isfinite(d) & (d > 0)]
            if len(finite) > 0:
                data_depth = max(data_depth, float(np.max(finite)))
    if data_depth <= 0:
        data_depth = prof.depth_max_plot
    depth_max = data_depth + max(data_depth * 0.1, 5.0)

    # --- Percentile band (bottom) ---
    pct = prof.percentile_layer
    if pct.visible and prof.depth_grid is not None and prof.p_low is not None:
        c = matplotlib.colors.to_rgba(pct.color, alpha=pct.alpha / 255.0)
        dg = prof.depth_grid
        mask = dg <= depth_max
        ax_vs.fill_betweenx(
            dg[mask],
            prof.p_low[mask] * convert,
            prof.p_high[mask] * convert,
            color=c, zorder=2,
            label="5-95 Percentile",
        )

    # --- Individual spaghetti (middle) ---
    ind = prof.individual_layer
    if ind.visible and prof.profiles:
        n_show = min(prof.max_individual, len(prof.profiles))
        step = max(1, len(prof.profiles) // n_show)
        c = matplotlib.colors.to_rgba(ind.color, alpha=ind.alpha / 255.0)
        drawn = 0
        for d, v in prof.profiles[::step]:
            finite_mask = np.isfinite(d) & (d > 0)
            if not np.any(finite_mask):
                continue
            last_valid = np.max(np.where(finite_mask)[0])
            d_plot = d[:last_valid + 1].copy()
            v_plot = (v[:last_valid + 1] * convert).copy()
            if d_plot[-1] < depth_max:
                d_plot = np.append(d_plot, depth_max)
                v_plot = np.append(v_plot, v_plot[-1])
            ax_vs.plot(v_plot, d_plot, color=c,
                       linewidth=ind.line_width, zorder=1)
            drawn += 1

        ax_vs.plot([], [], color=ind.color, linewidth=ind.line_width,
                   alpha=0.5, label=f"{prof.n_profiles} Profiles")

    # --- Median step function (top) ---
    med = prof.median_layer
    if med.visible and prof.median_depth_paired is not None:
        md = prof.median_depth_paired.copy()
        mv = (prof.median_vel_paired * convert).copy()
        finite_mask = np.isfinite(md) & (md > 0)
        if np.any(finite_mask):
            last_valid = np.max(np.where(finite_mask)[0])
            md = md[:last_valid + 1]
            mv = mv[:last_valid + 1]
            if md[-1] < depth_max:
                md = np.append(md, depth_max)
                mv = np.append(mv, mv[-1])
        ax_vs.plot(
            mv, md, color=med.color, linewidth=med.line_width,
            label=f"Median ({prof.n_profiles} profiles)", zorder=3,
        )

    # --- VsN legend entry ---
    if state.velocity_unit == "imperial":
        if prof.vs100_mean is not None:
            txt = f"Vs100 = {prof.vs100_mean:.0f} ft/s"
            if prof.vs100_std is not None:
                txt += f" (std = {prof.vs100_std:.1f})"
            ax_vs.plot([], [], " ", label=txt)
    else:
        if prof.vs30_mean is not None:
            txt = f"Vs30 = {prof.vs30_mean:.0f} {vel_unit}"
            if prof.vs30_std is not None:
                txt += f" (std = {prof.vs30_std:.1f})"
            ax_vs.plot([], [], " ", label=txt)

    # --- Sigma_ln subplot ---
    sig = prof.sigma_layer
    if (ax_sig is not None and sig.visible
            and prof.sigma_ln is not None and prof.depth_grid is not None):
        dg = prof.depth_grid
        mask = dg <= depth_max
        ax_sig.plot(
            prof.sigma_ln[mask], dg[mask],
            color=sig.color, linewidth=sig.line_width,
            label=r"$\sigma_{\ln(Vs)}$", zorder=3,
        )
        sig_max = max(0.5, float(np.nanmax(prof.sigma_ln[mask])) * 1.1)
        ax_sig.set_xlim(0, sig_max)

    # Set Y range
    ax_vs.set_ylim(depth_max, 0)


def _configure_sigma_axis(ax_sig, sigma_key: str, settings: StudioSettings):
    """Configure the sigma_ln companion axis."""
    s = settings
    ax_sig.set_xlabel(
        r"$\sigma_{\ln(Vs)}$",
        fontsize=s.typography.axis_label_size,
        fontweight=s.typography.font_weight,
    )
    ax_sig.xaxis.set_label_position("top")
    ax_sig.xaxis.tick_top()
    ax_sig.tick_params(axis="y", labelleft=False)
    ax_sig.tick_params(direction="in", which="both", length=4)
    ax_sig.xaxis.set_minor_locator(mtick.AutoMinorLocator())
    ax_sig.grid(True, alpha=0.3, linestyle=":", linewidth=0.5)

    # Determine parent subplot key from sigma key
    if sigma_key == "sigma_ln":
        parent_key = "vs_profile"
    elif sigma_key.endswith("_sigma"):
        parent_key = sigma_key.rsplit("_sigma", 1)[0]
    else:
        parent_key = sigma_key

    parent_lc = settings.legend_for(parent_key)
    # If parent uses outside legend, skip sigma inside legend
    if parent_lc.placement != "inside":
        existing = ax_sig.get_legend()
        if existing:
            existing.remove()
        return

    lc = settings.legend_for(sigma_key)
    handles, labels = ax_sig.get_legend_handles_labels()
    if handles and lc.show and lc.placement == "inside":
        scale = settings.legend_scale
        ax_sig.legend(
            loc=lc.location,
            fontsize=(lc.fontsize
                      or max(7, s.typography.legend_size - 1)) * scale,
            frameon=lc.frame_on,
            framealpha=lc.frame_alpha,
            markerscale=(lc.markerscale or 1.0) * scale,
        )
