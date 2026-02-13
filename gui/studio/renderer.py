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
    create_adjacent_legends,
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

        # Check which legend placements are requested
        has_outside = False
        has_adjacent = False
        for k in axes_map:
            if k.endswith("_sigma") or k == "sigma_ln":
                continue
            ck = k.rsplit("_sp_", 1)[0] if "_sp_" in k else k
            lc = settings.legend_for(ck)
            if not lc.show:
                continue
            if lc.placement == "adjacent":
                has_adjacent = True
            elif lc.placement != "inside":
                has_outside = True

        self._outside_legend = None
        self._adjacent_legends = []

        if has_outside and not skip_outside_legend:
            self._outside_legend = create_outside_legend(
                fig, axes_map, state, settings,
            )
        if has_adjacent and not skip_outside_legend:
            self._adjacent_legends = create_adjacent_legends(
                fig, axes_map, state, settings,
            )
        if not has_outside and not has_adjacent and settings.figure.tight_layout:
            fig.tight_layout()

        return fig

    def export_legend_only(self, path: str, dpi: int = 300, **save_kwargs):
        """Export just the outside legend as a separate image file."""
        return export_legend_only(
            self._outside_legend, self._settings, path, dpi, **save_kwargs,
        )

    def collect_legend_labels(self) -> Dict[str, list]:
        """Return available legend labels per subplot key.

        Call after render() to discover which labels exist in each subplot.
        For multi-section subplots (soil_profile with vs/vp/density sections),
        labels are aggregated under the parent key with section sub-groups.
        The returned list contains either plain label strings or tuples of
        (section_display_name, [labels]) for sectioned subplots.
        """
        result = {}
        axes_map = getattr(self, "_axes_map", {})
        st = self._state
        sections = getattr(st, 'soil_profile_sections', {}) or {}

        _SEC_NAMES = {"vs": "Vs", "vp": "Vp", "density": "Density"}

        # Identify parent keys that have sections
        sectioned_parents = {
            k for k, secs in sections.items() if secs and len(secs) > 1
        }

        for key, ax in axes_map.items():
            if key.endswith("_sigma") or key == "sigma_ln":
                continue
            # Skip section sub-keys -- handled via parent
            if "_sp_" in key:
                continue
            # Skip parent keys that are aliases for first section axis
            if key in sectioned_parents:
                sec_labels = []
                for prop in sections[key]:
                    sec_key = f"{key}_sp_{prop}"
                    sec_ax = axes_map.get(sec_key)
                    if sec_ax is None:
                        continue
                    _, labels = sec_ax.get_legend_handles_labels()
                    extra = getattr(sec_ax, "legend_handles", [])
                    if extra:
                        labels = labels + [h.get_label() for h in extra]
                    if labels:
                        sec_labels.append(
                            (_SEC_NAMES.get(prop, prop), labels)
                        )
                if sec_labels:
                    result[key] = sec_labels
                continue

            _, labels = ax.get_legend_handles_labels()
            extra = getattr(ax, "legend_handles", [])
            if extra:
                labels = labels + [h.get_label() for h in extra]
            sig_key = "sigma_ln" if key == "vs_profile" else f"{key}_sigma"
            sig_ax = axes_map.get(sig_key)
            if sig_ax is not None:
                _, sl = sig_ax.get_legend_handles_labels()
                if sl:
                    labels = labels + sl
            if labels:
                result[key] = labels
        return result

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

        sections = getattr(st, 'soil_profile_sections', {}) or {}

        for key, ax in axes_map.items():
            if key.endswith("_sigma") or key == "sigma_ln":
                continue  # handled by vs_profile rendering

            # Check if this is a multi-property section axis
            if "_sp_" in key:
                self._render_section_subplot(ax, key, sections, _legend_fn)
                continue

            cell_type = st.subplot_types.get(key, "unset")

            # Skip parent keys that have multi-property sections
            if cell_type in ("soil_profile", "vs_extract") and key in sections and \
                    len(sections[key]) > 1:
                acfg = s.axis_for(key)
                title = acfg.title or st.subplot_names.get(key, "")
                if title:
                    sec_keys = [f"{key}_sp_{p}" for p in sections[key]]
                    sec_axes = [axes_map[sk] for sk in sec_keys
                                if sk in axes_map]
                    if len(sec_axes) >= 2:
                        # Center title across section group using fig.text
                        fig_obj = sec_axes[0].get_figure()
                        fig_obj.canvas.draw_idle()
                        left_bb = sec_axes[0].get_position()
                        right_bb = sec_axes[-1].get_position()
                        cx = (left_bb.x0 + right_bb.x1) / 2.0
                        cy = left_bb.y1 + s.typography.title_pad / 72.0 / fig_obj.get_figheight()
                        fig_obj.text(
                            cx, cy, title,
                            ha="center", va="bottom",
                            fontsize=s.typography.title_size,
                            fontweight=s.typography.font_weight,
                        )
                    elif sec_axes:
                        sec_axes[0].set_title(
                            title, fontsize=s.typography.title_size,
                            fontweight=s.typography.font_weight,
                        )
                continue

            if cell_type in ("vs_extract", "profile") or key == "vs_profile":
                sig_ax = axes_map.get(
                    f"{key}_sigma", axes_map.get("sigma_ln")
                )
                # Profile type has no sigma pane
                if cell_type == "profile":
                    sig_ax = None
                render_vs_subplot(
                    ax, sig_ax, key, st, s, self._vf, _legend_fn,
                )
            elif cell_type == "dc":
                render_dc_subplot(ax, key, st, s, self._vf, _legend_fn)
            elif cell_type == "soil_profile":
                # Soil profile without sections -- render as profile
                render_vs_subplot(
                    ax, None, key, st, s, self._vf, _legend_fn,
                )
            else:
                # "unset" or unknown -- render both DC and profile data
                render_dc_subplot(ax, key, st, s, self._vf, _legend_fn)
                # Also render soil profiles if present on this subplot
                soil_profs = getattr(st, "soil_profiles", []) or []
                soil_on_key = [sp for sp in soil_profs
                               if sp.subplot_key == key
                               or sp.subplot_key == "main"]
                if soil_on_key:
                    render_vs_subplot(
                        ax, None, key, st, s, self._vf, _legend_fn,
                    )

            # Subplot title -- axis config title overrides subplot_names
            acfg = s.axis_for(key)
            title = acfg.title or st.subplot_names.get(key, "")
            if title:
                ax.set_title(title, fontsize=s.typography.title_size,
                             fontweight=s.typography.font_weight)

    def _render_section_subplot(self, ax, sec_key, sections, legend_fn):
        """Render a single sub-section of a multi-property soil profile."""
        from .renderer_modules.vs_renderer import (
            _render_one_soil_profile, _render_group_stats,
        )

        st = self._state
        s = self._settings
        vf = self._vf

        # Parse parent key and property from sec_key (e.g. "main_sp_vs")
        parts = sec_key.rsplit("_sp_", 1)
        if len(parts) != 2:
            return
        parent_key, prop = parts

        vel_unit = "m/s" if st.velocity_unit != "imperial" else "ft/s"
        _LABELS = {"vs": f"Vs ({vel_unit})", "vp": f"Vp ({vel_unit})",
                    "density": "Density (kg/m3)"}
        depth_unit = "ft" if st.velocity_unit == "imperial" else "m"

        parent_sections = sections.get(parent_key, [])
        is_first = (parent_sections and parent_sections[0] == prop)

        # Render soil profiles matching this subplot + property
        soil_profs = getattr(st, "soil_profiles", []) or []
        for sp in soil_profs:
            if (sp.subplot_key == parent_key or sp.subplot_key == "main") \
                    and getattr(sp, "render_property", "vs") == prop:
                _render_one_soil_profile(ax, sp, vf)

        # Render group statistics
        soil_groups = getattr(st, "soil_profile_groups", []) or []
        for grp in soil_groups:
            if (grp.subplot_key == parent_key or grp.subplot_key == "main") \
                    and grp.has_statistics \
                    and getattr(grp, "stats_property", "vs") == prop:
                _render_group_stats(ax, grp, vf)

        # Configure axes
        acfg = s.axis_for(sec_key)
        ax.set_xlabel(acfg.x_label or _LABELS.get(prop, f"Vs ({vel_unit})"),
                       fontsize=s.typography.axis_label_size,
                       fontweight=s.typography.font_weight)
        # Only invert Y on the first section (shared Y propagates)
        if is_first:
            ax.invert_yaxis()

        # Y-axis label only on leftmost section
        if is_first:
            ax.set_ylabel(f"Depth ({depth_unit})",
                          fontsize=s.typography.axis_label_size,
                          fontweight=s.typography.font_weight)
        else:
            ax.tick_params(axis="y", labelleft=False)

        tick_weight = "bold" if s.typography.bold_ticks else "normal"
        from .renderer_modules.axis_helpers import configure_ticks, configure_grid
        configure_ticks(ax, acfg, tick_weight)
        configure_grid(ax, acfg)
        legend_fn(ax, sec_key)
