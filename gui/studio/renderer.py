"""Matplotlib rendering engine.

Converts a FigureState (from geo_figure.core.models) into a matplotlib Figure
using StudioSettings for styling. This module has no Qt dependency — it is
pure matplotlib.

This is the refactored version: rendering logic is split across focused
sub-modules in renderer_modules/.
"""
import matplotlib
from matplotlib.figure import Figure
from typing import Dict, Optional

from geo_figure.core.models import FigureState
from .models import StudioSettings
from .renderer_modules.constants import VEL_FACTORS
from .renderer_modules.subplot_factory import create_subplots
from .renderer_modules.dc_renderer import render_dc_subplot
from .renderer_modules.vs_renderer import render_vs_subplot
from .renderer_modules.legend_builder import (
    configure_legend,
    create_outside_legend,
    export_legend_only,
)
from .renderer_modules.post_process import post_process


class MplRenderer:
    """Renders a FigureState into a matplotlib Figure."""

    def render(
        self,
        state: FigureState,
        settings: StudioSettings,
        fig: Optional[Figure] = None,
        skip_outside_legend: bool = False,
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
        skip_outside_legend : bool
            If True, omit the outside legend (used for "save legend separately").

        Returns
        -------
        matplotlib.figure.Figure
        """
        self._state = state
        self._settings = settings
        self._vf = VEL_FACTORS.get(state.velocity_unit, 1.0)

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
        axes_map = create_subplots(fig, state, settings)
        self._axes_map = axes_map

        # Render data into each subplot
        self._render_all_subplots(axes_map)

        # Post-process: linked axes, frequency ticks, label visibility
        post_process(axes_map, state, settings)

        # Create combined outside legend if any subplot requests it
        has_outside = any(
            settings.legend_for(k).placement != "inside"
            and settings.legend_for(k).show
            for k in axes_map
            if not k.endswith("_sigma") and k != "sigma_ln"
        )
        self._outside_legend = None
        if has_outside and not skip_outside_legend:
            self._outside_legend = create_outside_legend(
                fig, axes_map, state, settings,
            )
        elif settings.figure.tight_layout:
            fig.tight_layout()

        return fig

    def export_legend_only(self, path: str, dpi: int = 300, **save_kwargs):
        """Export just the outside legend as a separate image file."""
        return export_legend_only(
            self._outside_legend, self._settings, path, dpi, **save_kwargs,
        )

    # ── rcParams ──────────────────────────────────────────────────

    def _apply_rcparams(self):
        """Set matplotlib rcParams from settings."""
        s = self._settings
        tick_weight = "bold" if s.typography.bold_ticks else "normal"
        matplotlib.rcParams.update({
            "font.family": s.typography.font_family,
            "font.size": s.typography.tick_label_size,
            "axes.linewidth": s.spine_linewidth,
            "axes.labelsize": s.typography.axis_label_size,
            "axes.labelweight": s.typography.font_weight,
            "axes.labelpad": s.typography.label_pad,
            "axes.titlesize": s.typography.title_size,
            "axes.titleweight": s.typography.font_weight,
            "axes.titlepad": s.typography.title_pad,
            "xtick.labelsize": s.typography.tick_label_size,
            "ytick.labelsize": s.typography.tick_label_size,
            "legend.fontsize": s.typography.legend_size,
        })
        self._tick_weight = tick_weight

    # ── Main render dispatch ──────────────────────────────────────

    def _render_all_subplots(self, axes_map: Dict[str, object]):
        """Render curves/ensembles/profiles into each subplot."""
        st = self._state
        s = self._settings

        def _legend_fn(ax, key):
            configure_legend(ax, key, s)

        for key, ax in axes_map.items():
            if key.endswith("_sigma") or key == "sigma_ln":
                continue  # handled by vs_profile rendering

            cell_type = st.subplot_types.get(key, "dc")
            if cell_type == "vs_profile" or key == "vs_profile":
                sig_ax = axes_map.get(
                    f"{key}_sigma", axes_map.get("sigma_ln")
                )
                render_vs_subplot(
                    ax, sig_ax, key, st, s, self._vf, _legend_fn,
                )
            else:
                render_dc_subplot(ax, key, st, s, self._vf, _legend_fn)

            # Subplot title
            title = st.subplot_names.get(key, "")
            if title:
                ax.set_title(title, fontsize=s.typography.title_size,
                             fontweight=s.typography.font_weight)
