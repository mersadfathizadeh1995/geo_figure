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
        preview: bool = False,
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
        preview : bool
            If True, use screen-friendly DPI (100) instead of export DPI.

        Returns
        -------
        matplotlib.figure.Figure
        """
        self._state = state
        self._settings = settings
        self._vf = _VEL_FACTORS.get(state.velocity_unit, 1.0)

        # Apply global rcParams
        self._apply_rcparams()

        # Use low DPI for preview (screen), high DPI only for export
        render_dpi = 100 if preview else settings.figure.dpi

        # Create or clear figure
        if fig is None:
            fig = Figure(
                figsize=(settings.figure.width, settings.figure.height),
                dpi=render_dpi,
                facecolor=settings.figure.facecolor,
            )
        else:
            fig.clear()
            fig.set_size_inches(settings.figure.width, settings.figure.height)
            fig.set_dpi(render_dpi)
            fig.set_facecolor(settings.figure.facecolor)

        # Build subplots based on layout_mode
        axes_map = self._create_subplots(fig)

        # Render data into each subplot
        self._render_all_subplots(axes_map)

        # Apply layout — adjust margins for legend placement
        if settings.legend.outside:
            # Shrink plot area to make room for outside legend on the right
            # Use a generous margin; bbox_inches='tight' on export trims excess
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
        left = s.margin_left / s.width
        right = 1.0 - s.margin_right / s.width
        bottom = s.margin_bottom / s.height
        top = 1.0 - s.margin_top / s.height
        hspace = s.hspace / s.height if s.height > 0 else 0.2
        wspace = s.vspace / s.width if s.width > 0 else 0.2

        axes = {}

        if st.layout_mode == "vs_profile":
            axes = self._create_vs_profile_layout(
                fig, left, right, top, bottom
            )
        elif st.layout_mode == "split_wave":
            gs = GridSpec(
                1, 2, figure=fig,
                left=left, right=right, bottom=bottom, top=top,
                wspace=wspace,
            )
            axes["rayleigh"] = fig.add_subplot(gs[0, 0])
            axes["love"] = fig.add_subplot(gs[0, 1])
        elif st.layout_mode == "grid":
            axes = self._create_grid_layout(
                fig, left, right, top, bottom, hspace, wspace
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

        # Count actual columns (Vs cells need 2: main + sigma)
        actual_cols = 0
        col_map = {}  # grid_col -> actual_start_col
        width_ratios = []
        for c in range(cols):
            col_map[c] = actual_cols
            key = f"cell_0_{c}"
            if stypes.get(key) == "vs_profile":
                width_ratios.extend([3, 1])
                actual_cols += 2
            else:
                width_ratios.append(1)
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
            if key.endswith("_sigma"):
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

        # Axis limits
        if not acfg.auto_x and acfg.x_min is not None and acfg.x_max is not None:
            ax.set_xlim(acfg.x_min, acfg.x_max)
        if not acfg.auto_y and acfg.y_min is not None and acfg.y_max is not None:
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

        # 4. Median (top, bold)
        med = ens.median_layer
        if med.visible and ens.median is not None:
            ax.semilogx(
                freq, ens.median * vf,
                color=med.color, linewidth=med.line_width,
                label=ens.display_name, zorder=5,
            )

    # ── Vs Profile subplot rendering ──────────────────────────────

    def _render_vs_subplot(self, ax_vs, ax_sig, subplot_key: str):
        """Render Vs profiles on the Vs + sigma_ln subplots."""
        st = self._state
        s = self._settings
        vf = self._vf
        vel_unit = _VEL_UNIT.get(st.velocity_unit, "m/s")

        # Collect VsProfileData items for this subplot
        # (vs_profiles are stored on FigureState but not in curves/ensembles)
        vs_profs = getattr(st, "vs_profiles", [])
        matching = [p for p in vs_profs if (
            p.subplot_key == subplot_key
            or p.subplot_key == "vs_profile"
            or p.subplot_key == "main"
        )]

        for prof in matching:
            self._render_one_vs_profile(ax_vs, ax_sig, prof, vf, vel_unit)

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

        # Configure sigma_ln axis
        if ax_sig is not None:
            self._configure_sigma_axis(ax_sig)

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
