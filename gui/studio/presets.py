"""Presets for common figure styles.

Each preset is a function that returns a fully-configured StudioSettings.
Presets can also be applied onto an existing StudioSettings instance.
"""
from .models import (
    StudioSettings, FigureConfig, TypographyConfig,
    LegendConfig, GridConfig, TickConfig, ExportOptions,
)

# ── Preset definitions ────────────────────────────────────────────────

PRESETS = {
    "publication": {
        "label": "Publication",
        "description": "Journal-ready: Times New Roman, normal weight, standard sizes",
        "typography": TypographyConfig(
            font_family="Times New Roman",
            font_weight="normal",
            title_size=14, axis_label_size=11,
            tick_label_size=10, legend_size=9, annotation_size=9,
        ),
    },
    "compact": {
        "label": "Compact",
        "description": "Small format: DejaVu Sans, smaller fonts",
        "typography": TypographyConfig(
            font_family="DejaVu Sans",
            font_weight="normal",
            title_size=10, axis_label_size=8,
            tick_label_size=7, legend_size=7, annotation_size=7,
        ),
    },
}


def apply_preset(settings: StudioSettings, name: str) -> StudioSettings:
    """Apply a named preset to an existing StudioSettings instance.

    Only modifies typography (fonts, sizes, weight). Does NOT change
    figure dimensions, axis limits, legend, or export settings.

    Returns the same settings object (mutated in-place).
    """
    preset = PRESETS.get(name)
    if not preset:
        return settings

    # Copy typography only
    typo = preset["typography"]
    for attr in (
        "font_family", "font_weight", "title_size", "axis_label_size",
        "tick_label_size", "legend_size", "annotation_size",
    ):
        setattr(settings.typography, attr, getattr(typo, attr))

    return settings


def get_preset_names() -> list:
    """Return list of preset names in display order."""
    return ["publication", "compact"]


def get_preset_label(name: str) -> str:
    """Return the human-readable label for a preset."""
    return PRESETS.get(name, {}).get("label", name.title())
