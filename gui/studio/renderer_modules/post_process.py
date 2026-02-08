"""Post-processing: linked axes, frequency ticks, label visibility."""
from typing import Dict

from geo_figure.core.models import FigureState
from ..models import StudioSettings
from .axis_helpers import apply_freq_ticks


def post_process(
    axes_map: Dict[str, object],
    state: FigureState,
    settings: StudioSettings,
):
    """Apply linked axes, frequency ticks, and label visibility."""
    for key, ax in axes_map.items():
        if key.endswith("_sigma"):
            continue
        acfg = settings.axis_for(key)

        # Link X axis to another subplot
        if acfg.link_x_to and acfg.link_x_to in axes_map:
            src_ax = axes_map[acfg.link_x_to]
            ax.set_xlim(src_ax.get_xlim())

        # Link Y axis to another subplot
        if acfg.link_y_to and acfg.link_y_to in axes_map:
            src_ax = axes_map[acfg.link_y_to]
            ax.set_ylim(src_ax.get_ylim())

        # Frequency tick modes
        apply_freq_ticks(ax, acfg, state, key)

        # Label visibility
        if not acfg.show_x_label:
            ax.set_xlabel("")
        if not acfg.show_y_label:
            ax.set_ylabel("")
