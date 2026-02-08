"""Legend configuration: inside per-subplot legends, combined outside legends,
and figure expansion for appended legend areas.
"""
import matplotlib.patches as mpatches
from matplotlib.figure import Figure
from typing import Dict, Optional

from geo_figure.core.models import FigureState
from ..models import StudioSettings


def configure_legend(ax, subplot_key: str, settings: StudioSettings):
    """Configure legend for a subplot using per-subplot settings.

    For 'inside' placement, adds legend directly to the axes.
    For outside placements, skips (handled by create_outside_legend).
    """
    lc = settings.legend_for(subplot_key)
    if not lc.show:
        legend = ax.get_legend()
        if legend:
            legend.remove()
        return

    if lc.placement != "inside":
        return

    handles, labels = ax.get_legend_handles_labels()
    extra = getattr(ax, "legend_handles", [])
    if extra:
        handles = handles + extra
        labels = labels + [h.get_label() for h in extra]

    if not handles:
        return

    scale = settings.legend_scale
    fontsize = (lc.fontsize or settings.typography.legend_size) * scale

    kwargs = dict(
        fontsize=fontsize,
        frameon=lc.frame_on,
        framealpha=lc.frame_alpha,
        shadow=lc.shadow,
        ncol=lc.ncol,
        markerscale=lc.markerscale * scale,
    )
    if lc.title:
        kwargs["title"] = lc.title

    kwargs["loc"] = lc.location
    ax.legend(handles, labels, **kwargs)


def create_outside_legend(
    fig: Figure,
    axes_map: Dict[str, object],
    state: FigureState,
    settings: StudioSettings,
) -> Optional[object]:
    """Create a combined figure-level legend for subplots with outside placement.

    The figure is expanded to append a dedicated legend area.
    Returns the legend object, or None.
    """
    # Collect subplot groups that want outside legends
    groups = []  # [(subplot_name, handles, labels)]
    placement_side = None

    for key, ax in axes_map.items():
        if key.endswith("_sigma") or key == "sigma_ln":
            continue
        lc = settings.legend_for(key)
        if not lc.show or lc.placement == "inside":
            continue

        if placement_side is None:
            placement_side = lc.placement

        handles, labels = ax.get_legend_handles_labels()
        extra = getattr(ax, "legend_handles", [])
        if extra:
            handles = handles + extra
            labels = labels + [h.get_label() for h in extra]

        # Also collect sigma subplot legend entries
        sig_key = "sigma_ln" if key == "vs_profile" else f"{key}_sigma"
        sig_ax = axes_map.get(sig_key)
        if sig_ax is not None:
            sh, sl = sig_ax.get_legend_handles_labels()
            if sh:
                handles = handles + sh
                labels = labels + sl

        if handles:
            name = state.subplot_names.get(key, key)
            groups.append((name, handles, labels))

    if not groups:
        return None

    # Build combined handle/label list with group headers
    combined_handles = []
    combined_labels = []
    scale = settings.legend_scale
    base_fs = settings.typography.legend_size * scale

    header_indices = []
    separator_indices = []

    for i, (name, handles, labels) in enumerate(groups):
        if len(groups) > 1:
            if i > 0:
                separator_indices.append(len(combined_handles))
                combined_handles.append(
                    mpatches.Patch(facecolor="none", edgecolor="none")
                )
                combined_labels.append(" ")
            header_indices.append(len(combined_handles))
            combined_handles.append(
                mpatches.Patch(facecolor="none", edgecolor="none")
            )
            combined_labels.append(name)

        combined_handles.extend(handles)
        combined_labels.extend(labels)

    if not combined_handles:
        return None

    # Use first outside subplot's legend config for frame settings
    first_key = None
    for key in axes_map:
        if not key.endswith("_sigma") and key != "sigma_ln":
            lc = settings.legend_for(key)
            if lc.placement != "inside":
                first_key = key
                break
    lc = settings.legend_for(first_key) if first_key else settings.legend

    # Determine ncol based on placement direction
    is_horizontal = placement_side in ("outside_top", "outside_bottom")
    n_data_items = sum(len(h) for _, h, _ in groups)
    ncol = min(n_data_items, 6) if is_horizontal else 1

    # Create legend at figure center first; _expand_figure_for_legend
    # will measure it and reposition it into an appended area.
    legend = fig.legend(
        combined_handles, combined_labels,
        loc="center",
        bbox_to_anchor=(0.5, 0.5),
        bbox_transform=fig.transFigure,
        fontsize=base_fs,
        frameon=lc.frame_on,
        framealpha=lc.frame_alpha,
        shadow=lc.shadow,
        markerscale=(lc.markerscale or 1.0) * scale,
        borderaxespad=0.3,
        handlelength=1.5,
        ncol=ncol,
    )

    # Style header and separator entries
    if legend:
        for idx in separator_indices:
            if idx < len(legend.get_texts()):
                legend.get_texts()[idx].set_fontsize(base_fs * 0.15)
                legend.get_texts()[idx].set_color("none")
            if idx < len(legend.legend_handles):
                legend.legend_handles[idx].set_visible(False)
        for idx in header_indices:
            if idx < len(legend.get_texts()):
                legend.get_texts()[idx].set_fontweight("bold")
                legend.get_texts()[idx].set_fontsize(base_fs * 1.05)
            if idx < len(legend.legend_handles):
                legend.legend_handles[idx].set_visible(False)

    # Expand the figure to append the legend as a dedicated area
    if legend:
        _expand_figure_for_legend(fig, legend, placement_side)

    return legend


def _expand_figure_for_legend(fig: Figure, legend, placement_side: str):
    """Expand figure dimensions and reposition axes to append legend."""
    from matplotlib.backends.backend_agg import FigureCanvasAgg

    if fig.canvas is None or not hasattr(fig.canvas, "get_renderer"):
        FigureCanvasAgg(fig)
    fig.canvas.draw()
    rndr = fig.canvas.get_renderer()

    leg_bb = legend.get_window_extent(rndr)
    leg_bb_in = leg_bb.transformed(fig.dpi_scale_trans.inverted())
    leg_w = leg_bb_in.width
    leg_h = leg_bb_in.height

    fig_w, fig_h = fig.get_size_inches()
    pad = 0.25  # inches

    all_axes = list(fig.get_axes())

    if placement_side in ("outside_left", "outside_right"):
        extra = leg_w + pad
        new_w = fig_w + extra
        ratio = fig_w / new_w

        if placement_side == "outside_left":
            shift = extra / new_w
            leg_x = shift / 2.0
        else:
            shift = 0.0
            leg_x = 1.0 - (extra / 2.0) / new_w

        fig.set_size_inches(new_w, fig_h)
        for ax in all_axes:
            pos = ax.get_position()
            ax.set_position([
                shift + pos.x0 * ratio, pos.y0,
                pos.width * ratio, pos.height,
            ])
        legend.set_bbox_to_anchor(
            (leg_x, 0.5), transform=fig.transFigure
        )
        legend._loc = 10  # center

    elif placement_side in ("outside_top", "outside_bottom"):
        extra = leg_h + pad
        new_h = fig_h + extra
        ratio = fig_h / new_h

        if placement_side == "outside_bottom":
            shift = extra / new_h
            leg_y = shift / 2.0
        else:
            shift = 0.0
            leg_y = 1.0 - (extra / 2.0) / new_h

        fig.set_size_inches(fig_w, new_h)
        for ax in all_axes:
            pos = ax.get_position()
            ax.set_position([
                pos.x0, shift + pos.y0 * ratio,
                pos.width, pos.height * ratio,
            ])
        legend.set_bbox_to_anchor(
            (0.5, leg_y), transform=fig.transFigure
        )
        legend._loc = 10  # center


def export_legend_only(
    outside_legend,
    settings: StudioSettings,
    path: str,
    dpi: int = 300,
    **save_kwargs,
) -> bool:
    """Export just the outside legend as a separate image file."""
    if outside_legend is None:
        return False
    from matplotlib.figure import Figure as MplFigure
    fig_leg = MplFigure(dpi=dpi, facecolor="white")

    old_leg = outside_legend
    handles = list(old_leg.legend_handles)
    labels = [t.get_text() for t in old_leg.get_texts()]
    if not handles:
        return False
    ncol = old_leg._ncols if hasattr(old_leg, "_ncols") else 1

    scale = settings.legend_scale
    base_fs = settings.typography.legend_size * scale

    leg = fig_leg.legend(
        handles, labels,
        loc="center",
        fontsize=base_fs,
        frameon=True,
        framealpha=0.9,
        markerscale=(settings.legend.markerscale or 1.0) * scale,
        handlelength=1.5,
        ncol=ncol,
    )
    # Copy styling from original
    for i, txt in enumerate(old_leg.get_texts()):
        if i < len(leg.get_texts()):
            leg.get_texts()[i].set_fontweight(txt.get_fontweight())
            leg.get_texts()[i].set_fontsize(txt.get_fontsize())
            leg.get_texts()[i].set_color(txt.get_color())
    for i, h in enumerate(old_leg.legend_handles):
        if i < len(leg.legend_handles):
            leg.legend_handles[i].set_visible(h.get_visible())

    fig_leg.savefig(
        path, dpi=dpi, bbox_inches="tight", pad_inches=0.1,
        facecolor=save_kwargs.get("facecolor", "white"),
        transparent=save_kwargs.get("transparent", False),
    )
    return True
