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
        "description": "Journal-ready: Times New Roman, 300 DPI, compact",
        "figure": FigureConfig(
            width=6.5, height=5.0, dpi=300,
            margin_left=0.70, margin_right=0.25,
            margin_top=0.45, margin_bottom=0.55,
        ),
        "typography": TypographyConfig(
            font_family="Times New Roman",
            font_weight="normal",
            title_size=14, axis_label_size=11,
            tick_label_size=10, legend_size=9, annotation_size=9,
        ),
        "legend": LegendConfig(
            show=True, location="upper right",
            frame_on=True, frame_alpha=0.9, fontsize=9,
        ),
        "export": ExportOptions(format="pdf", dpi=300),
    },
    "presentation": {
        "label": "Presentation",
        "description": "Slides: Arial, large fonts, 150 DPI",
        "figure": FigureConfig(
            width=10.0, height=7.5, dpi=150,
            margin_left=0.90, margin_right=0.35,
            margin_top=0.65, margin_bottom=0.70,
        ),
        "typography": TypographyConfig(
            font_family="Arial",
            font_weight="bold",
            title_size=20, axis_label_size=16,
            tick_label_size=14, legend_size=12, annotation_size=12,
        ),
        "legend": LegendConfig(
            show=True, location="upper right",
            frame_on=True, frame_alpha=0.8, fontsize=12,
        ),
        "export": ExportOptions(format="png", dpi=150),
    },
    "poster": {
        "label": "Poster",
        "description": "Large format: Arial, extra-large fonts, 300 DPI",
        "figure": FigureConfig(
            width=12.0, height=9.0, dpi=300,
            margin_left=1.10, margin_right=0.40,
            margin_top=0.80, margin_bottom=0.85,
        ),
        "typography": TypographyConfig(
            font_family="Arial",
            font_weight="bold",
            title_size=24, axis_label_size=20,
            tick_label_size=18, legend_size=16, annotation_size=16,
        ),
        "legend": LegendConfig(
            show=True, location="upper right",
            frame_on=True, frame_alpha=0.8, fontsize=16,
        ),
        "export": ExportOptions(format="png", dpi=300),
    },
    "compact": {
        "label": "Compact",
        "description": "Single-column: DejaVu Sans, small, 300 DPI",
        "figure": FigureConfig(
            width=3.5, height=2.8, dpi=300,
            margin_left=0.55, margin_right=0.15,
            margin_top=0.30, margin_bottom=0.45,
        ),
        "typography": TypographyConfig(
            font_family="DejaVu Sans",
            font_weight="normal",
            title_size=10, axis_label_size=8,
            tick_label_size=7, legend_size=7, annotation_size=7,
        ),
        "legend": LegendConfig(
            show=True, location="upper right",
            frame_on=True, frame_alpha=0.9, fontsize=7,
        ),
        "export": ExportOptions(format="pdf", dpi=300),
    },
}


def apply_preset(settings: StudioSettings, name: str) -> StudioSettings:
    """Apply a named preset to an existing StudioSettings instance.

    Returns the same settings object (mutated in-place).
    """
    preset = PRESETS.get(name)
    if not preset:
        return settings

    # Copy figure config fields
    fig = preset["figure"]
    for attr in (
        "width", "height", "dpi", "margin_left", "margin_right",
        "margin_top", "margin_bottom",
    ):
        setattr(settings.figure, attr, getattr(fig, attr))

    # Copy typography
    typo = preset["typography"]
    for attr in (
        "font_family", "font_weight", "title_size", "axis_label_size",
        "tick_label_size", "legend_size", "annotation_size",
    ):
        setattr(settings.typography, attr, getattr(typo, attr))

    # Copy legend
    leg = preset["legend"]
    for attr in ("show", "location", "frame_on", "frame_alpha", "fontsize"):
        setattr(settings.legend, attr, getattr(leg, attr))

    # Copy export
    exp = preset["export"]
    settings.export.format = exp.format
    settings.export.dpi = exp.dpi

    return settings


def get_preset_names() -> list:
    """Return list of preset names in display order."""
    return ["publication", "presentation", "poster", "compact"]


def get_preset_label(name: str) -> str:
    """Return the human-readable label for a preset."""
    return PRESETS.get(name, {}).get("label", name.title())
