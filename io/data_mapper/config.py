"""Configuration and result types for the Data Mapper."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple, Any
import numpy as np


# Column type constants
SKIP = "Skipped"
FREQ = "Frequency (Hz)"
VELOCITY = "Phase Velocity (m/s)"
SLOWNESS_SM = "Slowness (s/m)"
SLOWNESS_SKM = "Slowness (s/km)"
LOGSTD = "LogStd"
COV_FRAC = "COV (fraction, e.g. 0.10)"
COV_MULT = "COV (multiplier, e.g. 1.10)"
ABS_STD_SLOW = "Abs StdDev Slowness (s/m)"
ABS_STD_VEL = "Abs StdDev Velocity (m/s)"
WEIGHT = "Weight"
DUMMY_0ON = "Dummy (0=on, 1=off)"
DUMMY_1ON = "Dummy (1=on, 0=off)"


@dataclass
class ColumnMapping:
    """Result of column mapping: maps type names to column indices."""

    mapping: Dict[str, int]
    remember: bool = False

    def get_column(self, type_name: str) -> Optional[int]:
        return self.mapping.get(type_name)

    def has_type(self, type_name: str) -> bool:
        return type_name in self.mapping

    def to_dict(self) -> Dict[str, Any]:
        return {"mapping": self.mapping, "remember": self.remember}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ColumnMapping:
        return cls(mapping=data["mapping"], remember=data.get("remember", False))


@dataclass
class DataMapperConfig:
    """Configuration for the Data Mapper dialog."""

    type_options: List[str] = field(default_factory=lambda: [
        SKIP, FREQ, VELOCITY, SLOWNESS_SM, SLOWNESS_SKM,
        LOGSTD, COV_FRAC, COV_MULT, ABS_STD_SLOW, ABS_STD_VEL,
        WEIGHT, DUMMY_0ON, DUMMY_1ON,
    ])
    required_types: List[str] = field(default_factory=list)
    auto_detect_fn: Optional[Callable[[np.ndarray, int], Optional[str]]] = None
    validators: List[Callable[[Dict[str, int]], Tuple[bool, str]]] = field(
        default_factory=list
    )
    window_title: str = "Map File Columns"
    preview_rows: int = 30
    column_min_width: int = 130
    column_max_width: int = 210
    show_remember_checkbox: bool = False


def _validate_vel_or_slow(mapping: Dict[str, int]) -> Tuple[bool, str]:
    """At least one of velocity or slowness must be mapped."""
    has_vel = VELOCITY in mapping
    has_slow = any(k in mapping for k in (SLOWNESS_SM, SLOWNESS_SKM))
    if has_vel or has_slow:
        return (True, "")
    return (False, "Requires Phase Velocity or Slowness")


def dispersion_config() -> DataMapperConfig:
    """Pre-configured mapper for dispersion curve files."""
    return DataMapperConfig(
        required_types=[FREQ],
        validators=[_validate_vel_or_slow],
        window_title="Map Dispersion Curve Columns",
    )
