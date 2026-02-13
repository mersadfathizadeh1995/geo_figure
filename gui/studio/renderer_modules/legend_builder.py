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
    For section keys (containing '_sp_'), uses the parent key's config.
    """
    # Section keys inherit legend config from parent
    config_key = subplot_key
    if "_sp_" in subplot_key:
        config_key = subplot_key.rsplit("_sp_", 1)[0]

    lc = settings.legend_for(config_key)
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

    # Filter out hidden labels (stored on parent key's config)
    hidden = set(lc.hidden_labels) if lc.hidden_labels else set()
    if hidden:
        filtered = [(h, l) for h, l in zip(handles, labels) if l not in hidden]
        if filtered:
            handles, labels = zip(*filtered)
            handles, labels = list(handles), list(labels)
        else:
            handles, labels = [], []

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

    # Apply offset if set
    ox = getattr(lc, 'offset_x', 0.0)
    oy = getattr(lc, 'offset_y', 0.0)
    if ox != 0.0 or oy != 0.0:
        # Translate location name to approximate anchor point, then nudge
        _LOC_ANCHORS = {
            "upper right": (1.0, 1.0), "upper left": (0.0, 1.0),
            "lower left": (0.0, 0.0), "lower right": (1.0, 0.0),
            "right": (1.0, 0.5), "center left": (0.0, 0.5),
            "center right": (1.0, 0.5), "lower center": (0.5, 0.0),
            "upper center": (0.5, 1.0), "center": (0.5, 0.5),
            "best": (1.0, 1.0),
        }
        base = _LOC_ANCHORS.get(lc.location, (1.0, 1.0))
        kwargs["bbox_to_anchor"] = (base[0] + ox, base[1] + oy)
        kwargs["bbox_transform"] = ax.transAxes

    ax.legend(handles, labels, **kwargs)


def _collect_outside_groups(axes_map, state, settings):
    """Collect per-subplot legend groups for outside placement.

    Returns (groups, placement_side) where groups is a list of
    (subplot_name, sub_groups) and sub_groups is either:
      - [(None, handles, labels)]  for regular subplots
      - [(section_name, handles, labels), ...]  for multi-section subplots
    """
    sections = getattr(state, 'soil_profile_sections', {}) or {}
    sectioned_parents = {
        k for k, secs in sections.items() if secs and len(secs) > 1
    }
    _SEC_NAMES = {"vs": "Vs", "vp": "Vp", "density": "Density"}

    groups = []
    placement_side = None
    processed_keys = set()

    for key, ax in axes_map.items():
        if key.endswith("_sigma") or key == "sigma_ln":
            continue
        if "_sp_" in key:
            continue

        config_key = key
        lc = settings.legend_for(config_key)
        if not lc.show or lc.placement in ("inside", "adjacent"):
            continue
        if key in processed_keys:
            continue
        processed_keys.add(key)

        if placement_side is None:
            placement_side = lc.placement

        hidden = set(lc.hidden_labels) if lc.hidden_labels else set()

        if key in sectioned_parents:
            sub_groups = []
            for prop in sections[key]:
                sec_key = f"{key}_sp_{prop}"
                sec_ax = axes_map.get(sec_key)
                if sec_ax is None:
                    continue
                sh, sl = sec_ax.get_legend_handles_labels()
                extra = getattr(sec_ax, "legend_handles", [])
                if extra:
                    sh = sh + extra
                    sl = sl + [h.get_label() for h in extra]
                if hidden:
                    filtered = [(h, l) for h, l in zip(sh, sl)
                                if l not in hidden]
                    if filtered:
                        sh, sl = zip(*filtered)
                        sh, sl = list(sh), list(sl)
                    else:
                        sh, sl = [], []
                if sh:
                    sub_groups.append(
                        (_SEC_NAMES.get(prop, prop), sh, sl)
                    )
            if sub_groups:
                name = state.subplot_names.get(key, key)
                groups.append((name, sub_groups))
        else:
            handles, labels = ax.get_legend_handles_labels()
            extra = getattr(ax, "legend_handles", [])
            if extra:
                handles = handles + extra
                labels = labels + [h.get_label() for h in extra]

            sig_key = "sigma_ln" if key == "vs_profile" else f"{key}_sigma"
            sig_ax = axes_map.get(sig_key)
            if sig_ax is not None:
                sh, sl = sig_ax.get_legend_handles_labels()
                if sh:
                    handles = handles + sh
                    labels = labels + sl

            if hidden:
                filtered = [(h, l) for h, l in zip(handles, labels)
                            if l not in hidden]
                if filtered:
                    handles, labels = zip(*filtered)
                    handles, labels = list(handles), list(labels)
                else:
                    handles, labels = [], []

            if handles:
                name = state.subplot_names.get(key, key)
                groups.append((name, [(None, handles, labels)]))

    return groups, placement_side


def create_outside_legend(
    fig: Figure,
    axes_map: Dict[str, object],
    state: FigureState,
    settings: StudioSettings,
) -> Optional[object]:
    """Create a combined figure-level legend for subplots with outside placement.

    The figure is expanded to append a dedicated legend area.
    Subplots are visually separated with bold headers; multi-section
    subplots additionally show section sub-headers (Vs, Vp, Density).
    Returns the legend object, or None.
    """
    groups, placement_side = _collect_outside_groups(
        axes_map, state, settings
    )
    if not groups:
        return None

    # Build combined handle/label list with structured group headers
    combined_handles = []
    combined_labels = []
    scale = settings.legend_scale
    base_fs = settings.typography.legend_size * scale

    header_indices = []
    section_header_indices = []
    separator_indices = []

    for i, (name, sub_groups) in enumerate(groups):
        # Inter-group separator
        if i > 0:
            separator_indices.append(len(combined_handles))
            combined_handles.append(
                mpatches.Patch(facecolor="none", edgecolor="none")
            )
            combined_labels.append(" ")

        # Subplot header (always shown when multiple groups or sections)
        has_sections = any(sg[0] is not None for sg in sub_groups)
        if len(groups) > 1 or has_sections:
            header_indices.append(len(combined_handles))
            combined_handles.append(
                mpatches.Patch(facecolor="none", edgecolor="none")
            )
            combined_labels.append(name)

        for j, (sec_name, handles, labels) in enumerate(sub_groups):
            if sec_name is not None:
                # Section sub-header (e.g. "Vs", "Vp", "Density")
                section_header_indices.append(len(combined_handles))
                combined_handles.append(
                    mpatches.Patch(facecolor="none", edgecolor="none")
                )
                combined_labels.append(f"  {sec_name}")

            combined_handles.extend(handles)
            combined_labels.extend(labels)

    if not combined_handles:
        return None

    # Use first outside subplot's legend config for frame settings
    first_key = None
    for key in axes_map:
        if not key.endswith("_sigma") and key != "sigma_ln" \
                and "_sp_" not in key:
            lc = settings.legend_for(key)
            if lc.placement != "inside":
                first_key = key
                break
    lc = settings.legend_for(first_key) if first_key else settings.legend

    # Determine ncol: for horizontal placement use multi-column
    is_horizontal = placement_side in ("outside_top", "outside_bottom")
    if is_horizontal:
        n_data = sum(
            len(h) for _, sgs in groups for _, h, _ in sgs
        )
        ncol = max(lc.ncol, min(n_data, 6))
    else:
        ncol = lc.ncol

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

    # Style headers, section headers, and separators
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
        for idx in section_header_indices:
            if idx < len(legend.get_texts()):
                legend.get_texts()[idx].set_fontstyle("italic")
                legend.get_texts()[idx].set_fontsize(base_fs * 0.95)
                legend.get_texts()[idx].set_color("#444444")
            if idx < len(legend.legend_handles):
                legend.legend_handles[idx].set_visible(False)

    if legend:
        ox = getattr(lc, 'offset_x', 0.0)
        oy = getattr(lc, 'offset_y', 0.0)
        _expand_figure_for_legend(fig, legend, placement_side, ox, oy)

    return legend


def _expand_figure_for_legend(fig: Figure, legend, placement_side: str,
                              offset_x: float = 0.0, offset_y: float = 0.0):
    """Expand figure dimensions and reposition axes to append legend.

    For left/right placement the figure width is expanded; for top/bottom
    the figure height is expanded. In both cases the OTHER dimension is
    also expanded if the legend exceeds the figure extent in that direction,
    preventing clipping. offset_x/y apply a nudge in figure fraction.
    """
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
        # Primary expansion: width
        extra_w = leg_w + pad
        new_w = fig_w + extra_w

        if placement_side == "outside_left":
            shift_x = extra_w / new_w
            leg_x = shift_x / 2.0
        else:
            shift_x = 0.0
            leg_x = 1.0 - (extra_w / 2.0) / new_w

        ratio_w = fig_w / new_w

        # Secondary expansion: height (if legend taller than figure)
        extra_h = max(leg_h + pad - fig_h, 0.0)
        new_h = fig_h + extra_h
        ratio_h = fig_h / new_h if extra_h > 0 else 1.0
        shift_y = (extra_h / 2.0) / new_h if extra_h > 0 else 0.0

        fig.set_size_inches(new_w, new_h)
        for ax in all_axes:
            pos = ax.get_position()
            ax.set_position([
                shift_x + pos.x0 * ratio_w,
                shift_y + pos.y0 * ratio_h,
                pos.width * ratio_w,
                pos.height * ratio_h,
            ])
        legend.set_bbox_to_anchor(
            (leg_x + offset_x, 0.5 + offset_y), transform=fig.transFigure
        )
        legend._loc = 10  # center

    elif placement_side in ("outside_top", "outside_bottom"):
        # Primary expansion: height
        extra_h = leg_h + pad
        new_h = fig_h + extra_h

        if placement_side == "outside_bottom":
            shift_y = extra_h / new_h
            leg_y = shift_y / 2.0
        else:
            shift_y = 0.0
            leg_y = 1.0 - (extra_h / 2.0) / new_h

        ratio_h = fig_h / new_h

        # Secondary expansion: width (if legend wider than figure)
        extra_w = max(leg_w + pad - fig_w, 0.0)
        new_w = fig_w + extra_w
        ratio_w = fig_w / new_w if extra_w > 0 else 1.0
        shift_x = (extra_w / 2.0) / new_w if extra_w > 0 else 0.0

        fig.set_size_inches(new_w, new_h)
        for ax in all_axes:
            pos = ax.get_position()
            ax.set_position([
                shift_x + pos.x0 * ratio_w,
                shift_y + pos.y0 * ratio_h,
                pos.width * ratio_w,
                pos.height * ratio_h,
            ])
        legend.set_bbox_to_anchor(
            (0.5 + offset_x, leg_y + offset_y), transform=fig.transFigure
        )
        legend._loc = 10  # center


def create_adjacent_legends(
    fig: Figure,
    axes_map: Dict[str, object],
    state: FigureState,
    settings: StudioSettings,
) -> list:
    """Create per-subplot legends placed adjacent to their specific subplot.

    Unlike the combined outside legend, each subplot gets its own legend
    positioned next to its axes. The figure is expanded to accommodate all
    adjacent legends.

    Returns a list of legend objects.
    """
    from matplotlib.backends.backend_agg import FigureCanvasAgg

    sections = getattr(state, 'soil_profile_sections', {}) or {}
    sectioned_parents = {
        k for k, secs in sections.items() if secs and len(secs) > 1
    }
    _SEC_NAMES = {"vs": "Vs", "vp": "Vp", "density": "Density"}

    scale = settings.legend_scale
    base_fs = settings.typography.legend_size * scale
    legends = []
    processed = set()

    # Collect which keys use adjacent placement
    adj_keys = []
    for key in axes_map:
        if key.endswith("_sigma") or key == "sigma_ln" or "_sp_" in key:
            continue
        lc = settings.legend_for(key)
        if not lc.show or lc.placement != "adjacent":
            continue
        if key in processed:
            continue
        processed.add(key)
        adj_keys.append(key)

    if not adj_keys:
        return legends

    if fig.canvas is None or not hasattr(fig.canvas, "get_renderer"):
        FigureCanvasAgg(fig)
    fig.canvas.draw()

    # Track total extra space needed per direction
    extra_right = 0.0
    extra_left = 0.0
    extra_top = 0.0
    extra_bottom = 0.0
    pad = 0.15  # inches between subplot and its legend

    legend_specs = []  # [(legend, key, side, leg_w_in, leg_h_in)]

    for key in adj_keys:
        lc = settings.legend_for(key)
        side = getattr(lc, 'adjacent_side', 'right')
        target = getattr(lc, 'adjacent_target', '') or ''
        hidden = set(lc.hidden_labels) if lc.hidden_labels else set()

        # Determine which axes to attach the legend near
        attach_key = target if target else key
        attach_ax = axes_map.get(attach_key)
        if attach_ax is None:
            continue

        # Collect handles/labels from this subplot
        handles, labels = [], []
        if key in sectioned_parents:
            for prop in sections[key]:
                sec_key = f"{key}_sp_{prop}"
                sec_ax = axes_map.get(sec_key)
                if sec_ax is None:
                    continue
                sh, sl = sec_ax.get_legend_handles_labels()
                extra_h = getattr(sec_ax, "legend_handles", [])
                if extra_h:
                    sh = sh + extra_h
                    sl = sl + [h.get_label() for h in extra_h]
                if sh:
                    handles.extend(sh)
                    labels.extend(sl)
        else:
            ax = axes_map.get(key)
            if ax is not None:
                handles, labels = ax.get_legend_handles_labels()
                extra_h = getattr(ax, "legend_handles", [])
                if extra_h:
                    handles = handles + extra_h
                    labels = labels + [h.get_label() for h in extra_h]

                sig_key = "sigma_ln" if key == "vs_profile" else f"{key}_sigma"
                sig_ax = axes_map.get(sig_key)
                if sig_ax is not None:
                    sh, sl = sig_ax.get_legend_handles_labels()
                    if sh:
                        handles = handles + sh
                        labels = labels + sl

        if hidden:
            filtered = [(h, l) for h, l in zip(handles, labels)
                        if l not in hidden]
            if filtered:
                handles, labels = zip(*filtered)
                handles, labels = list(handles), list(labels)
            else:
                handles, labels = [], []

        if not handles:
            continue

        # Compute smart default gap that clears tick labels and axis labels
        fig.canvas.draw()
        rndr = fig.canvas.get_renderer()
        ax_bb = attach_ax.get_tightbbox(rndr)
        plot_bb = attach_ax.get_window_extent(rndr)
        if ax_bb is not None and plot_bb is not None:
            ax_bb_ax = ax_bb.transformed(
                attach_ax.transAxes.inverted()
            )
            plot_bb_ax = plot_bb.transformed(
                attach_ax.transAxes.inverted()
            )
            # gap = distance from axes edge to outermost label, in axes fraction
            gap_right = max(ax_bb_ax.x1 - plot_bb_ax.x1, 0.0) + 0.04
            gap_left = max(plot_bb_ax.x0 - ax_bb_ax.x0, 0.0) + 0.04
            gap_top = max(ax_bb_ax.y1 - plot_bb_ax.y1, 0.0) + 0.04
            gap_bottom = max(plot_bb_ax.y0 - ax_bb_ax.y0, 0.0) + 0.04
        else:
            gap_right = gap_left = gap_top = gap_bottom = 0.06

        ox = getattr(lc, 'offset_x', 0.0)
        oy = getattr(lc, 'offset_y', 0.0)

        if side == "right":
            bbox_anchor = (1.0 + gap_right + ox, 0.5 + oy)
            loc = "center left"
        elif side == "left":
            bbox_anchor = (0.0 - gap_left + ox, 0.5 + oy)
            loc = "center right"
        elif side == "top":
            bbox_anchor = (0.5 + ox, 1.0 + gap_top + oy)
            loc = "lower center"
        else:  # bottom
            bbox_anchor = (0.5 + ox, 0.0 - gap_bottom + oy)
            loc = "upper center"

        is_horiz = side in ("top", "bottom")
        ncol = min(len(handles), 4) if is_horiz else 1

        legend = attach_ax.legend(
            handles, labels,
            loc=loc,
            bbox_to_anchor=bbox_anchor,
            fontsize=base_fs,
            frameon=lc.frame_on,
            framealpha=lc.frame_alpha,
            shadow=lc.shadow,
            markerscale=(lc.markerscale or 1.0) * scale,
            handlelength=1.5,
            ncol=ncol,
            borderaxespad=0.2,
        )
        legends.append(legend)

        # Measure legend size
        fig.canvas.draw()
        rndr = fig.canvas.get_renderer()
        leg_bb = legend.get_window_extent(rndr)
        leg_bb_in = leg_bb.transformed(fig.dpi_scale_trans.inverted())

        if side == "right":
            extra_right = max(extra_right, leg_bb_in.width + pad)
        elif side == "left":
            extra_left = max(extra_left, leg_bb_in.width + pad)
        elif side == "top":
            extra_top = max(extra_top, leg_bb_in.height + pad)
        else:
            extra_bottom = max(extra_bottom, leg_bb_in.height + pad)

    # Expand figure and shift all axes to accommodate adjacent legends
    fig_w, fig_h = fig.get_size_inches()
    new_w = fig_w + extra_left + extra_right
    new_h = fig_h + extra_top + extra_bottom

    if new_w != fig_w or new_h != fig_h:
        ratio_w = fig_w / new_w
        ratio_h = fig_h / new_h
        shift_x = extra_left / new_w
        shift_y = extra_bottom / new_h

        fig.set_size_inches(new_w, new_h)
        for ax in fig.get_axes():
            pos = ax.get_position()
            ax.set_position([
                shift_x + pos.x0 * ratio_w,
                shift_y + pos.y0 * ratio_h,
                pos.width * ratio_w,
                pos.height * ratio_h,
            ])

    return legends


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
