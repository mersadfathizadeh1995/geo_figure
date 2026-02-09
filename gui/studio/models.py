"""Data models for the Matplotlib Studio.

Defines all settings dataclasses that control figure rendering.
These are pure data containers with no Qt dependencies.
"""
from dataclasses import dataclass, field
from typing import Optional, Tuple, Dict, List


@dataclass
class TypographyConfig:
    """Font settings for all text elements in the figure."""
    font_family: str = "Times New Roman"
    font_weight: str = "normal"          # "normal" or "bold"
    title_size: float = 14.0
    axis_label_size: float = 11.0
    tick_label_size: float = 10.0
    legend_size: float = 9.0
    annotation_size: float = 9.0
    title_pad: float = 6.0              # padding between title and axes (pts)
    label_pad: float = 4.0              # padding between axis label and ticks (pts)
    bold_ticks: bool = False            # bold tick labels


@dataclass
class GridConfig:
    """Grid line appearance."""
    show: bool = True
    which: str = "both"                  # "major", "minor", "both"
    linestyle: str = ":"
    color: str = "#808080"
    alpha: float = 0.4
    linewidth: float = 0.5


@dataclass
class TickConfig:
    """Tick mark configuration."""
    direction: str = "in"                # "in", "out", "inout"
    show_top: bool = True
    show_right: bool = True
    show_minor: bool = True
    major_length: float = 5.0
    minor_length: float = 3.0


@dataclass
class AxisConfig:
    """Per-subplot axis configuration."""
    auto_x: bool = True
    auto_y: bool = True
    x_min: Optional[float] = None
    x_max: Optional[float] = None
    y_min: Optional[float] = None
    y_max: Optional[float] = None
    x_scale: str = "linear"              # "linear" or "log"
    y_scale: str = "linear"
    invert_y: bool = False
    x_label: str = ""
    y_label: str = ""
    show_x_label: bool = True
    show_y_label: bool = True
    freq_tick_mode: str = "default"      # "default", "clean", "data_sampled", "custom"
    freq_tick_custom: str = ""           # comma-separated values for "custom" mode
    link_x_to: str = ""
    link_y_to: str = ""
    ticks: TickConfig = field(default_factory=TickConfig)
    grid: GridConfig = field(default_factory=GridConfig)


@dataclass
class LegendConfig:
    """Legend appearance and positioning."""
    show: bool = True
    location: str = "upper right"
    placement: str = "inside"            # "inside", "outside_left", "outside_right", "outside_top", "outside_bottom"
    bbox_anchor: Optional[Tuple[float, float]] = None
    ncol: int = 1
    fontsize: Optional[float] = None     # None = use typography legend_size
    frame_on: bool = True
    frame_alpha: float = 0.9
    shadow: bool = False
    title: str = ""
    markerscale: float = 1.0             # scale for legend markers/lines
    hidden_labels: Optional[List[str]] = None  # labels to hide from legend


@dataclass
class FigureConfig:
    """Overall figure dimensions and layout."""
    width: float = 6.5                   # inches
    height: float = 5.0                  # inches
    dpi: int = 300
    margin_left: float = 0.70            # inches
    margin_right: float = 0.25
    margin_top: float = 0.50
    margin_bottom: float = 0.55
    hspace: float = 0.90                 # inches between subplot rows
    vspace: float = 0.90                 # inches between subplot columns
    tight_layout: bool = False
    facecolor: str = "white"


@dataclass
class ExportOptions:
    """Export/save parameters."""
    format: str = "png"                  # png, pdf, svg, eps, tiff
    dpi: int = 300
    transparent: bool = False
    bbox_inches: str = "tight"
    pad_inches: float = 0.1
    facecolor: str = "white"


@dataclass
class StudioSettings:
    """Complete settings for a matplotlib studio render.

    This is the single source of truth that the renderer reads from.
    The UI panels write into this object; any change triggers re-render.
    """
    figure: FigureConfig = field(default_factory=FigureConfig)
    typography: TypographyConfig = field(default_factory=TypographyConfig)
    legend: LegendConfig = field(default_factory=LegendConfig)
    export: ExportOptions = field(default_factory=ExportOptions)

    # Per-subplot axis overrides (key = subplot_key from FigureState)
    axis_overrides: Dict[str, AxisConfig] = field(default_factory=dict)

    # Per-subplot legend overrides
    legend_overrides: Dict[str, LegendConfig] = field(default_factory=dict)

    # Spine visibility
    spine_linewidth: float = 1.1

    # Legend scale (applies to all legend text/markers)
    legend_scale: float = 1.0

    # VS profile specific
    vs_wspace: float = 0.05             # gap between Vs and sigma_ln subplots
    vs_width_ratios: Tuple[float, float] = (0.75, 0.25)

    def axis_for(self, subplot_key: str) -> AxisConfig:
        """Get axis config for a subplot, creating a default if needed."""
        if subplot_key not in self.axis_overrides:
            self.axis_overrides[subplot_key] = AxisConfig()
        return self.axis_overrides[subplot_key]

    def legend_for(self, subplot_key: str) -> LegendConfig:
        """Get legend config for a subplot, creating from global defaults if needed."""
        if subplot_key not in self.legend_overrides:
            g = self.legend
            self.legend_overrides[subplot_key] = LegendConfig(
                show=g.show, location=g.location, placement=g.placement,
                ncol=g.ncol, fontsize=g.fontsize, frame_on=g.frame_on,
                frame_alpha=g.frame_alpha, shadow=g.shadow, title=g.title,
                markerscale=g.markerscale,
            )
        return self.legend_overrides[subplot_key]
