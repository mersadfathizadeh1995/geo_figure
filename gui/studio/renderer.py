"""Matplotlib rendering engine.

Converts a FigureState (from geo_figure.core.models) into a matplotlib Figure
using StudioSettings for styling. This module has no Qt dependency — it is
pure matplotlib.
"""
import numpy as np
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
import matplotlib.patches as mpatches
from matplotlib.figure import Figure
from matplotlib.gridspec import GridSpec
from typing import Dict, List, Optional, Tuple

from geo_figure.core.models import (
    CurveData, CurveType, EnsembleData, VsProfileData, FigureState,
)
from .models import StudioSettings, AxisConfig

# Velocity conversion
_VEL_FACTORS = {"metric": 1.0, "imperial": 3.28084}
_VEL_LABELS = {"metric": "Phase Velocity (m/s)", "imperial": "Phase Velocity (ft/s)"}
_VS_LABELS = {"metric": "Vs (m/s)", "imperial": "Vs (ft/s)"}
_DEPTH_LABELS = {"metric": "Depth (m)", "imperial": "Depth (ft)"}
_VEL_UNIT = {"metric": "m/s", "imperial": "ft/s"}


class MplRenderer:
    """Renders a FigureState into a matplotlib Figure."""

    def render(
        self,
        state: FigureState,
        settings: StudioSettings,
        fig: Optional[Figure] = None,
    ) -> Figure:
        """Render the entire figure.

        Parameters
        ----------
        state : FigureState
            Data + layout to render (curves, ensembles, vs_profiles).
        settings : StudioSettings
            All visual settings (typography, axis, legend, etc.).
        fig : Figure, optional
            Existing figure to render into. Created if None.
            The caller is responsible for setting size_inches and DPI
            before passing the figure.

        Returns
        -------
        matplotlib.figure.Figure
        """
        self._state = state
        self._settings = settings
        self._vf = _VEL_FACTORS.get(state.velocity_unit, 1.0)

        # Apply global rcParams
        self._apply_rcparams()

        if fig is None:
            fig = Figure(
                figsize=(settings.figure.width, settings.figure.height),
                dpi=settings.figure.dpi,
                facecolor=settings.figure.facecolor,
            )
        else:
            fig.clear()
            fig.set_facecolor(settings.figure.facecolor)

        # Build subplots based on layout_mode
        axes_map = self._create_subplots(fig)
        self._axes_map = axes_map

        # Render data into each subplot
        self._render_all_subplots(axes_map)

        # Post-process: linked axes, frequency ticks, label visibility
        self._post_process(axes_map)

        # Apply layout — adjust margins for legend placement
        if settings.legend.outside:
            fig.subplots_adjust(right=0.75)
        if settings.figure.tight_layout and not settings.legend.outside:
            fig.tight_layout()

        return fig

    # ── rcParams ──────────────────────────────────────────────────

    def _apply_rcparams(self):
        """Set matplotlib rcParams from settings."""
        s = self._settings
        matplotlib.rcParams.update({
            "font.family": s.typography.font_family,
            "font.size": s.typography.tick_label_size,
            "axes.linewidth": s.spine_linewidth,
            "axes.labelsize": s.typography.axis_label_size,
            "axes.labelweight": s.typography.font_weight,
            "axes.titlesize": s.typography.title_size,
            "axes.titleweight": s.typography.font_weight,
            "xtick.labelsize": s.typography.tick_label_size,
            "ytick.labelsize": s.typography.tick_label_size,
            "legend.fontsize": s.typography.legend_size,
        })

    # ── Subplot creation ──────────────────────────────────────────

    def _create_subplots(self, fig: Figure) -> Dict[str, object]:
        """Create axes according to layout_mode. Returns {subplot_key: ax}."""
        st = self._state
        s = self._settings.figure

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

        axes = {}

        if st.layout_mode == "vs_profile":
            axes = self._create_vs_profile_layout(
                fig, left, right, top, bottom
            )
        elif st.layout_mode == "split_wave":
            avg_w = plot_w / 2.0
            ws = s.vspace / avg_w if avg_w > 0 else 0.2
            gs = GridSpec(
                1, 2, figure=fig,
                left=left, right=right, bottom=bottom, top=top,
                wspace=ws,
            )
            axes["rayleigh"] = fig.add_subplot(gs[0, 0])
            axes["love"] = fig.add_subplot(gs[0, 1])
        elif st.layout_mode == "grid":
            rows = max(st.grid_rows, 1)
            cols = max(st.grid_cols, 1)
            avg_h = plot_h / rows
            avg_w = plot_w / cols
            hs = s.hspace / avg_h if avg_h > 0 else 0.2
            ws = s.vspace / avg_w if avg_w > 0 else 0.2
            axes = self._create_grid_layout(
                fig, left, right, top, bottom, hs, ws
            )
        else:
            # Combined — single subplot
            gs = GridSpec(
                1, 1, figure=fig,
                left=left, right=right, bottom=bottom, top=top,
            )
            axes["main"] = fig.add_subplot(gs[0, 0])

        return axes

    def _create_vs_profile_layout(
        self, fig, left, right, top, bottom
    ) -> Dict[str, object]:
        """Create 2-column Vs Profile layout (Vs + sigma_ln)."""
        ws = self._settings.vs_wspace
        ratios = list(self._settings.vs_width_ratios)
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
        self, fig, left, right, top, bottom, hspace, wspace
    ) -> Dict[str, object]:
        """Create NxM grid with mixed DC/Vs cells."""
        st = self._state
        rows, cols = st.grid_rows, st.grid_cols
        stypes = st.subplot_types

        # Per-column logical ratios (default to equal)
        col_ratios = list(st.grid_col_ratios)
        while len(col_ratios) < cols:
            col_ratios.append(1.0)

        # Count actual columns (Vs cells need 2: main + sigma)
        actual_cols = 0
        col_map = {}  # grid_col -> actual_start_col
        width_ratios = []
        for c in range(cols):
            col_map[c] = actual_cols
            key = f"cell_0_{c}"
            r_base = max(col_ratios[c], 0.1)
            if stypes.get(key) == "vs_profile":
                vs_r, sig_r = self._settings.vs_width_ratios
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
                else:
                    axes[key] = fig.add_subplot(gs[r, ac])

        return axes

    # ── Main render dispatch ──────────────────────────────────────

    def _render_all_subplots(self, axes_map: Dict[str, object]):
        """Render curves/ensembles/profiles into each subplot."""
        st = self._state
        s = self._settings

        for key, ax in axes_map.items():
            if key.endswith("_sigma") or key == "sigma_ln":
                continue  # handled by vs_profile rendering

            cell_type = st.subplot_types.get(key, "dc")
            if cell_type == "vs_profile" or key == "vs_profile":
                sig_ax = axes_map.get(
                    f"{key}_sigma", axes_map.get("sigma_ln")
                )
                self._render_vs_subplot(ax, sig_ax, key)
            else:
                self._render_dc_subplot(ax, key)

            # Subplot title
            title = st.subplot_names.get(key, "")
            if title:
                ax.set_title(title, fontsize=s.typography.title_size,
                             fontweight=s.typography.font_weight)

    # ── DC subplot rendering ──────────────────────────────────────

    def _render_dc_subplot(self, ax, subplot_key: str):
        """Render dispersion curves and ensembles on a DC subplot."""
        st = self._state
        s = self._settings
        vf = self._vf

        # Collect data for this subplot
        curves = [c for c in st.curves if c.subplot_key == subplot_key]
        ensembles = [e for e in st.ensembles if e.subplot_key == subplot_key]

        # Configure log-scale X axis
        ax.set_xscale("log")
        ax.xaxis.set_major_formatter(mtick.ScalarFormatter())
        ax.xaxis.get_major_formatter().set_scientific(False)
        ax.xaxis.set_minor_formatter(mtick.NullFormatter())

        # Render ensembles (bottom layers first)
        for ens in ensembles:
            self._render_ensemble(ax, ens, vf)

        # Render experimental/theoretical curves
        for curve in curves:
            if not curve.visible or not curve.has_data:
                continue
            self._render_curve(ax, curve, vf)

        # Axis labels and config
        acfg = s.axis_for(subplot_key)
        xlabel = acfg.x_label or "Frequency (Hz)"
        ylabel = acfg.y_label or _VEL_LABELS.get(st.velocity_unit, "Phase Velocity (m/s)")
        ax.set_xlabel(xlabel, fontsize=s.typography.axis_label_size,
                      fontweight=s.typography.font_weight)
        ax.set_ylabel(ylabel, fontsize=s.typography.axis_label_size,
                      fontweight=s.typography.font_weight)

        # Axis limits — compute from visible data when auto
        bounds = self._compute_dc_visible_bounds(subplot_key)
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

        self._configure_ticks(ax, acfg)
        self._configure_grid(ax, acfg)
        self._configure_legend(ax, subplot_key)

    def _render_curve(self, ax, curve: CurveData, vf: float):
        """Render a single CurveData on a matplotlib axis."""
        freq = curve.frequency
        vel = curve.velocity
        mask = curve.point_mask if curve.point_mask is not None else np.ones(len(freq), dtype=bool)
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
            stddev_plot = curve.stddev[mask] if (
                curve.stddev is not None and len(curve.stddev) == len(freq)
            ) else None

        # Apply stddev mode overrides
        stddev_plot = self._apply_stddev_mode(curve, f, stddev_plot)

        is_theoretical = curve.curve_type == CurveType.THEORETICAL
        label = curve.display_name

        if is_theoretical:
            ax.semilogx(
                f, v, color=curve.color, linewidth=curve.line_width,
                linestyle="-", label=label, zorder=4,
            )
        else:
            # Error bars
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

    def _apply_stddev_mode(self, curve, freq, stddev):
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

    def _render_ensemble(self, ax, ens: EnsembleData, vf: float):
        """Render an EnsembleData with all visible layers."""
        freq = ens.freq
        if freq is None or len(freq) == 0:
            return

        # 1. Envelope (bottom, gray)
        env = ens.envelope_layer
        if env.visible and ens.envelope_min is not None:
            c = matplotlib.colors.to_rgba(env.color, alpha=env.alpha / 255.0)
            ax.fill_between(
                freq, ens.envelope_min * vf, ens.envelope_max * vf,
                color=c, edgecolor="k", linewidth=0.3, zorder=1,
                label="Theoretical Range",
            )

        # 2. Percentile band
        pct = ens.percentile_layer
        if pct.visible and ens.p_low is not None:
            c = matplotlib.colors.to_rgba(pct.color, alpha=pct.alpha / 255.0)
            ax.fill_between(
                freq, ens.p_low * vf, ens.p_high * vf,
                color=c, zorder=2, label="16-84 Percentile",
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
            # Ghost legend entry for individual profile count
            n_total = len(ens.individual_freqs)
            ax.plot([], [], color=ind.color, linewidth=ind.line_width,
                    alpha=ind.alpha / 255.0,
                    label=f"{n_total} Profiles")

        # 4. Median (top, bold)
        med = ens.median_layer
        if med.visible and ens.median is not None:
            median_label = f"Median ({ens.display_name})" if ens.display_name else "Median"
            ax.semilogx(
                freq, ens.median * vf,
                color=med.color, linewidth=med.line_width,
                label=median_label, zorder=5,
            )

    # ── Vs Profile subplot rendering ──────────────────────────────

    def _render_vs_subplot(self, ax_vs, ax_sig, subplot_key: str):
        """Render Vs profiles on the Vs + sigma_ln subplots."""
        st = self._state
        s = self._settings
        vf = self._vf
        vel_unit = _VEL_UNIT.get(st.velocity_unit, "m/s")

        # Collect VsProfileData items for this subplot
        vs_profs = getattr(st, "vs_profiles", [])
        matching = [p for p in vs_profs if (
            p.subplot_key == subplot_key
            or p.subplot_key == "vs_profile"
            or p.subplot_key == "main"
        )]

        # Track whether any profile has sigma visible
        any_sigma_visible = False
        for prof in matching:
            self._render_one_vs_profile(ax_vs, ax_sig, prof, vf, vel_unit)
            if prof.sigma_layer.visible and prof.sigma_ln is not None:
                any_sigma_visible = True

        # Configure Vs axis
        acfg = s.axis_for(subplot_key)
        vs_label = acfg.x_label or _VS_LABELS.get(st.velocity_unit, "Vs (m/s)")
        depth_label = acfg.y_label or _DEPTH_LABELS.get(st.velocity_unit, "Depth (m)")
        ax_vs.set_xlabel(vs_label, fontsize=s.typography.axis_label_size,
                         fontweight=s.typography.font_weight)
        ax_vs.set_ylabel(depth_label, fontsize=s.typography.axis_label_size,
                         fontweight=s.typography.font_weight)
        ax_vs.invert_yaxis()

        if not acfg.auto_x and acfg.x_min is not None:
            ax_vs.set_xlim(acfg.x_min, acfg.x_max)
        if not acfg.auto_y and acfg.y_min is not None:
            ax_vs.set_ylim(acfg.y_max, acfg.y_min)  # inverted

        self._configure_ticks(ax_vs, acfg)
        self._configure_grid(ax_vs, acfg)
        self._configure_legend(ax_vs, subplot_key)

        # Configure sigma_ln axis — hide entirely if no sigma data visible
        if ax_sig is not None:
            if any_sigma_visible:
                self._configure_sigma_axis(ax_sig)
            else:
                ax_sig.set_visible(False)

    def _render_one_vs_profile(self, ax_vs, ax_sig, prof: VsProfileData,
                                vf: float, vel_unit: str):
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
                label=f"5-95 Percentile",
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
                ax_vs.plot(v_plot, d_plot, color=c, linewidth=ind.line_width, zorder=1)
                drawn += 1

            # Ghost legend entry for individual profile count
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
        if self._state.velocity_unit == "imperial":
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

    def _configure_sigma_axis(self, ax_sig):
        """Configure the sigma_ln companion axis."""
        s = self._settings
        ax_sig.set_xlabel(
            r"$\sigma_{\ln(Vs)}$",
            fontsize=s.typography.axis_label_size,
            fontweight=s.typography.font_weight,
        )
        ax_sig.xaxis.set_label_position("top")
        ax_sig.xaxis.tick_top()
        ax_sig.tick_params(
            axis="y", labelleft=False,
        )
        ax_sig.tick_params(
            direction="in", which="both", length=4,
        )
        ax_sig.xaxis.set_minor_locator(mtick.AutoMinorLocator())
        ax_sig.grid(True, alpha=0.3, linestyle=":", linewidth=0.5)

        # Legend
        handles, labels = ax_sig.get_legend_handles_labels()
        if handles and self._settings.legend.show:
            ax_sig.legend(
                loc="upper right",
                fontsize=max(7, s.typography.legend_size - 1),
            )

    # ── Axis helpers ──────────────────────────────────────────────

    def _configure_ticks(self, ax, acfg: AxisConfig):
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

    def _configure_grid(self, ax, acfg: AxisConfig):
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

    def _configure_legend(self, ax, subplot_key: str):
        """Configure legend for a subplot."""
        lc = self._settings.legend
        if not lc.show:
            legend = ax.get_legend()
            if legend:
                legend.remove()
            return

        handles, labels = ax.get_legend_handles_labels()
        # Include any ghost handles stored on the axis
        extra = getattr(ax, "legend_handles", [])
        if extra:
            handles = handles + extra
            labels = labels + [h.get_label() for h in extra]

        if not handles:
            return

        fontsize = lc.fontsize or self._settings.typography.legend_size

        kwargs = dict(
            fontsize=fontsize,
            frameon=lc.frame_on,
            framealpha=lc.frame_alpha,
            shadow=lc.shadow,
            ncol=lc.ncol,
        )
        if lc.title:
            kwargs["title"] = lc.title

        if lc.outside:
            # Place legend outside to the right of the plot
            kwargs["loc"] = "upper left"
            kwargs["bbox_to_anchor"] = (1.02, 1.0)
            kwargs["borderaxespad"] = 0.0
        else:
            kwargs["loc"] = lc.location

        ax.legend(handles, labels, **kwargs)

    # ── Post-processing ───────────────────────────────────────────

    def _post_process(self, axes_map: Dict[str, object]):
        """Apply linked axes, frequency ticks, and label visibility."""
        s = self._settings

        for key, ax in axes_map.items():
            if key.endswith("_sigma"):
                continue
            acfg = s.axis_for(key)

            # Link X axis to another subplot
            if acfg.link_x_to and acfg.link_x_to in axes_map:
                src_ax = axes_map[acfg.link_x_to]
                ax.set_xlim(src_ax.get_xlim())

            # Link Y axis to another subplot
            if acfg.link_y_to and acfg.link_y_to in axes_map:
                src_ax = axes_map[acfg.link_y_to]
                ax.set_ylim(src_ax.get_ylim())

            # Frequency tick modes
            self._apply_freq_ticks(ax, acfg, key)

            # Label visibility
            if not acfg.show_x_label:
                ax.set_xlabel("")
            if not acfg.show_y_label:
                ax.set_ylabel("")

    def _apply_freq_ticks(self, ax, acfg, subplot_key: str):
        """Apply frequency tick mode to x-axis."""
        mode = acfg.freq_tick_mode
        if mode == "default":
            return  # keep matplotlib's default log ticks

        xlim = ax.get_xlim()
        xlo, xhi = max(xlim[0], 1e-6), max(xlim[1], 1e-6)

        if mode == "clean":
            # Nice round values appropriate for frequency axes
            candidates = [
                0.5, 1, 1.5, 2, 3, 4, 5, 7, 10, 15, 20, 30, 40, 50, 70,
                100, 150, 200, 300, 500, 700, 1000, 1500, 2000, 3000, 5000,
            ]
            ticks = [v for v in candidates if xlo * 0.9 <= v <= xhi * 1.1]
            if not ticks:
                return
        elif mode == "data_sampled":
            all_freqs = self._collect_frequencies(subplot_key)
            if not all_freqs:
                return
            # Sample ~10 evenly spaced values in log space
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
            ticks = self._parse_custom_ticks(acfg.freq_tick_custom)
            if not ticks:
                return
        else:
            return

        ax.xaxis.set_major_locator(mtick.FixedLocator(ticks))
        fmt = mtick.FuncFormatter(self._freq_label_formatter)
        ax.xaxis.set_major_formatter(fmt)
        ax.xaxis.set_minor_locator(mtick.NullLocator())

    @staticmethod
    def _freq_label_formatter(val, pos):
        """Format frequency tick labels: integer if whole, else 1 decimal."""
        if val <= 0:
            return ""
        if val == int(val):
            return f"{int(val)}"
        if val < 10:
            return f"{val:.1f}"
        return f"{val:.0f}"

    @staticmethod
    def _parse_custom_ticks(text: str) -> List[float]:
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

    def _collect_frequencies(self, subplot_key: str) -> List[float]:
        """Collect unique frequency values from visible curves in a subplot."""
        freqs = set()
        for c in self._state.curves:
            if c.subplot_key == subplot_key and c.visible and c.has_data:
                mask = c.point_mask if c.point_mask is not None else np.ones(
                    len(c.frequency), dtype=bool)
                for f in c.frequency[mask]:
                    if np.isfinite(f) and f > 0:
                        freqs.add(float(f))
        return sorted(freqs)

    def _compute_dc_visible_bounds(
        self, subplot_key: str
    ) -> Optional[Tuple[float, float, float, float]]:
        """Compute (xmin, xmax, ymin, ymax) from visible data only."""
        vf = self._vf
        x_all: List[float] = []
        y_all: List[float] = []

        for c in self._state.curves:
            if c.subplot_key != subplot_key or not c.visible or not c.has_data:
                continue
            mask = c.point_mask if c.point_mask is not None else np.ones(
                len(c.frequency), dtype=bool)
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

        for e in self._state.ensembles:
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
