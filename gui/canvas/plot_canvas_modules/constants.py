"""Shared constants for the plot canvas."""

# Velocity unit conversion
VEL_FACTORS = {"metric": 1.0, "imperial": 3.28084}
VEL_LABELS = {"metric": "Phase Velocity (m/s)", "imperial": "Phase Velocity (ft/s)"}
VEL_UNIT_STR = {"metric": "m/s", "imperial": "ft/s"}

# Layout modes
LAYOUT_COMBINED = "combined"
LAYOUT_SPLIT_WAVE = "split_wave"
LAYOUT_GRID = "grid"
LAYOUT_VS_PROFILE = "vs_profile"

# Legend anchor presets: (itemPos, parentPos)
LEGEND_ANCHORS = {
    "top-right":    ((1, 0), (1, 0)),
    "top-left":     ((0, 0), (0, 0)),
    "bottom-right": ((1, 1), (1, 1)),
    "bottom-left":  ((0, 1), (0, 1)),
}
