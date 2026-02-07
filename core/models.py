"""Core data models for curves and profiles."""
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List, Dict
import numpy as np
import uuid


class CurveType(Enum):
    RAYLEIGH = "Rayleigh"
    LOVE = "Love"
    THEORETICAL = "Theoretical"
    HV_CURVE = "HV Curve"
    HV_PEAK = "HV Peak"


class WaveType(Enum):
    RAYLEIGH = "Rayleigh"
    LOVE = "Love"


class SourceType(Enum):
    PASSIVE = "Passive"
    ACTIVE = "Active"


@dataclass
class CurveData:
    """A single dispersion curve with data and metadata."""
    uid: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str = ""
    custom_name: str = ""  # user-assigned rename (overrides name in display)
    curve_type: CurveType = CurveType.RAYLEIGH
    wave_type: WaveType = WaveType.RAYLEIGH
    source_type: SourceType = SourceType.PASSIVE
    mode: int = 0

    # Data arrays
    frequency: Optional[np.ndarray] = None    # Hz
    velocity: Optional[np.ndarray] = None     # m/s
    slowness: Optional[np.ndarray] = None     # s/m
    stddev: Optional[np.ndarray] = None       # varies by stddev_type

    # Metadata
    filepath: Optional[str] = None
    n_points: int = 0
    freq_min: float = 0.0
    freq_max: float = 0.0
    stddev_type: str = "logstd"  # "logstd", "cov", "absolute"

    # Display state
    visible: bool = True
    color: str = "#2196F3"  # Material Blue
    line_width: float = 1.5
    marker_size: float = 6.0
    selected: bool = False
    show_error_bars: bool = True

    # Processing settings
    resample_enabled: bool = False
    resample_n_points: int = 50
    resample_method: str = "log"  # "log", "linear"
    stddev_mode: str = "file"     # "file", "fixed_logstd", "fixed_cov", "range"
    fixed_logstd: float = 1.1
    fixed_cov: float = 0.1
    stddev_ranges: list = field(default_factory=list)  # [(fmin, fmax, value), ...]

    # Subplot assignment
    subplot_key: str = "main"  # which subplot this curve belongs to

    # Point-level masking (True = visible)
    point_mask: Optional[np.ndarray] = None

    def __post_init__(self):
        if self.frequency is not None:
            self.n_points = len(self.frequency)
            if self.n_points > 0:
                self.freq_min = float(np.min(self.frequency))
                self.freq_max = float(np.max(self.frequency))
            if self.point_mask is None:
                self.point_mask = np.ones(self.n_points, dtype=bool)

    @property
    def has_data(self) -> bool:
        return self.frequency is not None and len(self.frequency) > 0

    @property
    def display_name(self) -> str:
        base = self.custom_name if self.custom_name else self.name
        mode_str = f" M{self.mode}" if self.mode > 0 else ""
        return f"{base}{mode_str}" if base else f"{self.curve_type.value}{mode_str}"

    def velocity_from_slowness(self):
        """Compute velocity from slowness if not already set."""
        if self.velocity is None and self.slowness is not None:
            with np.errstate(divide='ignore', invalid='ignore'):
                self.velocity = np.where(self.slowness != 0, 1.0 / self.slowness, 0.0)


@dataclass
class EnsembleLayer:
    """Display settings for one layer of an ensemble."""
    visible: bool = True
    color: str = "#888888"
    alpha: int = 255      # 0-255
    line_width: float = 2.0


@dataclass
class EnsembleData:
    """Theoretical ensemble: stats + per-layer display settings."""
    uid: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str = "Theoretical"
    custom_name: str = ""
    wave_type: WaveType = WaveType.RAYLEIGH
    mode: int = 0
    n_profiles: int = 0
    subplot_key: str = "main"

    # Statistics arrays (from compute_ensemble_statistics)
    freq: Optional[np.ndarray] = None
    median: Optional[np.ndarray] = None
    p_low: Optional[np.ndarray] = None    # 16th percentile
    p_high: Optional[np.ndarray] = None   # 84th percentile
    envelope_min: Optional[np.ndarray] = None
    envelope_max: Optional[np.ndarray] = None
    sigma_ln: Optional[np.ndarray] = None

    # Individual profile data for spaghetti plot
    individual_freqs: Optional[List[np.ndarray]] = None
    individual_vels: Optional[List[np.ndarray]] = None

    # Layer display settings
    median_layer: EnsembleLayer = field(
        default_factory=lambda: EnsembleLayer(
            visible=True, color="#FF0000", alpha=255, line_width=2.5
        )
    )
    percentile_layer: EnsembleLayer = field(
        default_factory=lambda: EnsembleLayer(
            visible=True, color="#2196F3", alpha=50, line_width=1.0
        )
    )
    envelope_layer: EnsembleLayer = field(
        default_factory=lambda: EnsembleLayer(
            visible=True, color="#b0b0b0", alpha=80, line_width=1.0
        )
    )
    individual_layer: EnsembleLayer = field(
        default_factory=lambda: EnsembleLayer(
            visible=False, color="#888888", alpha=25, line_width=0.5
        )
    )
    max_individual: int = 200

    @property
    def display_name(self) -> str:
        base = self.custom_name if self.custom_name else self.name
        mode_str = f" M{self.mode}" if self.mode > 0 else ""
        return f"{base}{mode_str}"

    @property
    def has_data(self) -> bool:
        return self.freq is not None and len(self.freq) > 0

    @classmethod
    def from_stats(cls, stats: dict, parsed: dict = None, **kwargs) -> "EnsembleData":
        """Create from compute_ensemble_statistics output."""
        ens = cls(
            freq=stats.get("freq"),
            median=stats.get("median"),
            p_low=stats.get("p_low"),
            p_high=stats.get("p_high"),
            envelope_min=stats.get("envelope_min"),
            envelope_max=stats.get("envelope_max"),
            sigma_ln=stats.get("sigma_ln"),
            n_profiles=stats.get("n_profiles", 0),
            **kwargs,
        )
        # Extract individual curves from parsed data if available
        if parsed is not None:
            profiles = parsed.get("profiles", {})
            mode = kwargs.get("mode", 0)
            ind_freqs = []
            ind_vels = []
            for p_data in profiles.values():
                if mode in p_data:
                    ind_freqs.append(p_data[mode]["freq"])
                    ind_vels.append(p_data[mode]["vel"])
            if ind_freqs:
                ens.individual_freqs = ind_freqs
                ens.individual_vels = ind_vels
        return ens


# Default colors for auto-assignment
CURVE_COLORS = [
    "#2196F3",  # Blue
    "#F44336",  # Red
    "#4CAF50",  # Green
    "#FF9800",  # Orange
    "#9C27B0",  # Purple
    "#00BCD4",  # Cyan
    "#795548",  # Brown
    "#607D8B",  # Blue Grey
    "#E91E63",  # Pink
    "#CDDC39",  # Lime
]


@dataclass
class FigureState:
    """Complete renderable state of a figure — the single source of truth
    that any backend (PyQtGraph interactive, Matplotlib export) reads from."""

    # Layout
    layout_mode: str = "combined"
    grid_rows: int = 1
    grid_cols: int = 1
    link_y: bool = False
    link_x: bool = False
    subplot_names: Dict[str, str] = field(default_factory=dict)

    # Data (references to live objects; renderer iterates these)
    curves: List[CurveData] = field(default_factory=list)
    ensembles: List[EnsembleData] = field(default_factory=list)

    # Display
    theme: str = "light"
    velocity_unit: str = "metric"  # "metric" (m/s) or "imperial" (ft/s)

    def curves_for_subplot(self, key: str) -> List[CurveData]:
        """Return curves assigned to a specific subplot."""
        return [c for c in self.curves if c.subplot_key == key]

    def ensembles_for_subplot(self, key: str) -> List[EnsembleData]:
        """Return ensembles assigned to a specific subplot."""
        return [e for e in self.ensembles if e.subplot_key == key]

    @property
    def subplot_keys(self) -> List[str]:
        """Ordered list of subplot keys."""
        return list(self.subplot_names.keys())

    def to_dict(self) -> dict:
        """Serializable summary (layout + metadata, not heavy arrays)."""
        return {
            "layout_mode": self.layout_mode,
            "grid_rows": self.grid_rows,
            "grid_cols": self.grid_cols,
            "link_y": self.link_y,
            "link_x": self.link_x,
            "subplot_names": dict(self.subplot_names),
            "n_curves": len(self.curves),
            "n_ensembles": len(self.ensembles),
            "theme": self.theme,
            "velocity_unit": self.velocity_unit,
        }
