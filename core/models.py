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
        # Auto-normalize: ensure velocity and slowness are always populated
        if self.velocity is None and self.slowness is not None:
            with np.errstate(divide='ignore', invalid='ignore'):
                self.velocity = np.where(self.slowness != 0,
                                         1.0 / self.slowness, 0.0)
        if self.slowness is None and self.velocity is not None:
            with np.errstate(divide='ignore', invalid='ignore'):
                self.slowness = np.where(self.velocity != 0,
                                         1.0 / self.velocity, 0.0)
        # Clip extreme logstd values
        if (self.stddev is not None and self.stddev_type == "logstd"
                and len(self.stddev) > 0):
            self.stddev = np.clip(self.stddev, 0.0, 5.0)
            self.stddev = np.where(np.isfinite(self.stddev), self.stddev, 0.0)

    @property
    def has_data(self) -> bool:
        return self.frequency is not None and len(self.frequency) > 0

    @property
    def display_name(self) -> str:
        if self.custom_name:
            return self.custom_name
        mode_str = f" M{self.mode}" if self.mode > 0 else ""
        base = self.name
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
    legend_label: str = ""  # user-editable legend text; empty = use default


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
class VsProfileData:
    """Vs (or Vp/Rho) depth-velocity profile ensemble with statistics."""
    uid: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str = "Vs Profile"
    custom_name: str = ""
    profile_type: str = "vs"  # "vs", "vp", "rho"
    n_profiles: int = 0
    subplot_key: str = "main"

    # Paired-format individual profiles: list of (depth, velocity) tuples
    profiles: Optional[List] = None  # List[Tuple[ndarray, ndarray]]

    # Statistics on uniform depth grid
    depth_grid: Optional[np.ndarray] = None
    median: Optional[np.ndarray] = None
    p_low: Optional[np.ndarray] = None     # e.g. 5th percentile
    p_high: Optional[np.ndarray] = None    # e.g. 95th percentile
    sigma_ln: Optional[np.ndarray] = None

    # Layered median (paired format from raw profiles)
    median_depth_paired: Optional[np.ndarray] = None
    median_vel_paired: Optional[np.ndarray] = None

    # Vs30 / Vs100 arrays (one per profile)
    vs30_values: Optional[np.ndarray] = None  # m/s
    vs100_values: Optional[np.ndarray] = None  # ft/s

    # Layer display settings
    median_layer: EnsembleLayer = field(
        default_factory=lambda: EnsembleLayer(
            visible=True, color="#000000", alpha=255, line_width=2.5
        )
    )
    percentile_layer: EnsembleLayer = field(
        default_factory=lambda: EnsembleLayer(
            visible=True, color="#2196F3", alpha=50, line_width=1.0
        )
    )
    individual_layer: EnsembleLayer = field(
        default_factory=lambda: EnsembleLayer(
            visible=True, color="#888888", alpha=80, line_width=0.5
        )
    )
    sigma_layer: EnsembleLayer = field(
        default_factory=lambda: EnsembleLayer(
            visible=True, color="#000000", alpha=255, line_width=1.5
        )
    )
    max_individual: int = 5000
    depth_max_plot: float = 100.0  # m

    @property
    def display_name(self) -> str:
        return self.custom_name if self.custom_name else self.name

    @property
    def has_data(self) -> bool:
        return self.depth_grid is not None and len(self.depth_grid) > 0

    @property
    def vs30_mean(self) -> Optional[float]:
        if self.vs30_values is not None:
            valid = self.vs30_values[~np.isnan(self.vs30_values)]
            return float(np.mean(valid)) if len(valid) > 0 else None
        return None

    @property
    def vs30_std(self) -> Optional[float]:
        if self.vs30_values is not None:
            valid = self.vs30_values[~np.isnan(self.vs30_values)]
            return float(np.std(valid)) if len(valid) > 1 else None
        return None

    @property
    def vs100_mean(self) -> Optional[float]:
        if self.vs100_values is not None:
            valid = self.vs100_values[~np.isnan(self.vs100_values)]
            return float(np.mean(valid)) if len(valid) > 0 else None
        return None

    @property
    def vs100_std(self) -> Optional[float]:
        if self.vs100_values is not None:
            valid = self.vs100_values[~np.isnan(self.vs100_values)]
            return float(np.std(valid)) if len(valid) > 1 else None
        return None


@dataclass
class FigureState:
    """Complete renderable state of a figure — the single source of truth
    that any backend (PyQtGraph interactive, Matplotlib export) reads from."""

    # Layout
    layout_mode: str = "combined"
    grid_rows: int = 1
    grid_cols: int = 1
    grid_col_ratios: List[float] = field(default_factory=list)  # per-column width ratios
    link_y: bool = False
    link_x: bool = False
    subplot_names: Dict[str, str] = field(default_factory=dict)
    subplot_types: Dict[str, str] = field(default_factory=dict)  # key -> "dc" or "vs_profile"

    # Data (references to live objects; renderer iterates these)
    curves: List[CurveData] = field(default_factory=list)
    ensembles: List[EnsembleData] = field(default_factory=list)
    vs_profiles: List["VsProfileData"] = field(default_factory=list)

    # Display
    theme: str = "light"
    velocity_unit: str = "metric"  # "metric" (m/s) or "imperial" (ft/s)

    def curves_for_subplot(self, key: str) -> List[CurveData]:
        """Return curves assigned to a specific subplot."""
        return [c for c in self.curves if c.subplot_key == key]

    def ensembles_for_subplot(self, key: str) -> List[EnsembleData]:
        """Return ensembles assigned to a specific subplot."""
        return [e for e in self.ensembles if e.subplot_key == key]

    def vs_profiles_for_subplot(self, key: str) -> List["VsProfileData"]:
        """Return Vs profiles assigned to a specific subplot."""
        return [p for p in self.vs_profiles if p.subplot_key == key]

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
            "n_vs_profiles": len(self.vs_profiles),
            "theme": self.theme,
            "velocity_unit": self.velocity_unit,
            "subplot_types": dict(self.subplot_types),
        }

    # ── Serialization helpers ────────────────────────────────

    @staticmethod
    def _layer_to_dict(layer: "EnsembleLayer") -> dict:
        return {
            "visible": layer.visible, "color": layer.color,
            "alpha": layer.alpha, "line_width": layer.line_width,
            "legend_label": layer.legend_label,
        }

    @staticmethod
    def _layer_from_dict(d: dict) -> "EnsembleLayer":
        if d is None:
            return EnsembleLayer()
        return EnsembleLayer(
            visible=d.get("visible", True),
            color=d.get("color", "#888888"),
            alpha=d.get("alpha", 255),
            line_width=d.get("line_width", 2.0),
            legend_label=d.get("legend_label", ""),
        )

    def _serialize_curve(self, c: "CurveData") -> dict:
        return {
            "uid": c.uid, "name": c.name, "custom_name": c.custom_name,
            "curve_type": c.curve_type, "wave_type": c.wave_type,
            "source_type": c.source_type, "mode": c.mode,
            "frequency": c.frequency, "velocity": c.velocity,
            "slowness": c.slowness, "stddev": c.stddev,
            "subplot_key": c.subplot_key, "color": c.color,
            "line_width": c.line_width, "marker_size": c.marker_size,
            "show_error_bars": c.show_error_bars, "visible": c.visible,
            "point_mask": c.point_mask,
            "resample_enabled": c.resample_enabled,
            "resample_n_points": c.resample_n_points,
            "resample_method": c.resample_method,
            "stddev_type": c.stddev_type,
            "stddev_mode": c.stddev_mode,
            "fixed_logstd": c.fixed_logstd, "fixed_cov": c.fixed_cov,
            "stddev_ranges": c.stddev_ranges,
            "filepath": c.filepath,
        }

    def _serialize_ensemble(self, e: "EnsembleData") -> dict:
        return {
            "uid": e.uid, "name": e.name, "custom_name": e.custom_name,
            "wave_type": e.wave_type, "mode": e.mode,
            "n_profiles": e.n_profiles, "subplot_key": e.subplot_key,
            "freq": e.freq, "median": e.median,
            "p_low": e.p_low, "p_high": e.p_high,
            "envelope_min": e.envelope_min, "envelope_max": e.envelope_max,
            "sigma_ln": e.sigma_ln,
            "individual_freqs": e.individual_freqs,
            "individual_vels": e.individual_vels,
            "max_individual": e.max_individual,
            "median_layer": self._layer_to_dict(e.median_layer),
            "percentile_layer": self._layer_to_dict(e.percentile_layer),
            "envelope_layer": self._layer_to_dict(e.envelope_layer),
            "individual_layer": self._layer_to_dict(e.individual_layer),
        }

    def _serialize_vs_profile(self, p: "VsProfileData") -> dict:
        return {
            "uid": p.uid, "name": p.name, "custom_name": p.custom_name,
            "profile_type": p.profile_type, "subplot_key": p.subplot_key,
            "profiles": p.profiles, "depth_grid": p.depth_grid,
            "median": p.median, "p_low": p.p_low, "p_high": p.p_high,
            "sigma_ln": p.sigma_ln,
            "median_depth_paired": p.median_depth_paired,
            "median_vel_paired": p.median_vel_paired,
            "vs30_values": p.vs30_values, "vs100_values": p.vs100_values,
            "n_profiles": p.n_profiles, "depth_max_plot": p.depth_max_plot,
            "max_individual": p.max_individual,
            "median_layer": self._layer_to_dict(p.median_layer),
            "percentile_layer": self._layer_to_dict(p.percentile_layer),
            "individual_layer": self._layer_to_dict(p.individual_layer),
            "sigma_layer": self._layer_to_dict(p.sigma_layer),
        }

    # ── Save / Load ───────────────────────────────────────────

    def serialize(self) -> dict:
        """Return the full state as a pickle-ready dict (no file I/O)."""
        return {
            "version": 2,
            "layout_mode": self.layout_mode,
            "grid_rows": self.grid_rows,
            "grid_cols": self.grid_cols,
            "grid_col_ratios": list(self.grid_col_ratios),
            "link_y": self.link_y,
            "link_x": self.link_x,
            "subplot_names": dict(self.subplot_names),
            "subplot_types": dict(self.subplot_types),
            "theme": self.theme,
            "velocity_unit": self.velocity_unit,
            "curves": [self._serialize_curve(c) for c in self.curves],
            "ensembles": [self._serialize_ensemble(e) for e in self.ensembles],
            "vs_profiles": [self._serialize_vs_profile(p) for p in self.vs_profiles],
        }

    def save(self, filepath: str):
        """Persist the full figure state (pickle) for later rendering."""
        import pickle
        with open(filepath, "wb") as f:
            pickle.dump(self.serialize(), f)

    @classmethod
    def deserialize(cls, data: dict) -> "FigureState":
        """Reconstruct a FigureState from a serialized dict."""
        return cls(
            layout_mode=data["layout_mode"],
            grid_rows=data["grid_rows"],
            grid_cols=data["grid_cols"],
            grid_col_ratios=data.get("grid_col_ratios", []),
            link_y=data["link_y"],
            link_x=data["link_x"],
            subplot_names=data.get("subplot_names", {}),
            subplot_types=data.get("subplot_types", {}),
            curves=[cls._load_curve(cd) for cd in data.get("curves", [])],
            ensembles=[cls._load_ensemble(ed) for ed in data.get("ensembles", [])],
            vs_profiles=[cls._load_vs_profile(pd_) for pd_ in data.get("vs_profiles", [])],
            theme=data.get("theme", "light"),
            velocity_unit=data.get("velocity_unit", "metric"),
        )

    @classmethod
    def _load_curve(cls, cd: dict) -> "CurveData":
        c = CurveData(uid=cd["uid"], name=cd["name"])
        skip = {"uid", "name"}
        for k, v in cd.items():
            if k not in skip and hasattr(c, k):
                setattr(c, k, v)
        # Recalculate derived fields that __post_init__ set before frequency was loaded
        if c.frequency is not None and len(c.frequency) > 0:
            c.n_points = len(c.frequency)
            c.freq_min = float(np.min(c.frequency))
            c.freq_max = float(np.max(c.frequency))
        return c

    @classmethod
    def _load_ensemble(cls, ed: dict) -> "EnsembleData":
        e = EnsembleData(uid=ed["uid"], name=ed["name"])
        layer_keys = {"median_layer", "percentile_layer",
                      "envelope_layer", "individual_layer"}
        skip = {"uid", "name"} | layer_keys
        for k, v in ed.items():
            if k not in skip and hasattr(e, k):
                setattr(e, k, v)
        for lk in layer_keys:
            if lk in ed:
                setattr(e, lk, cls._layer_from_dict(ed[lk]))
        return e

    @classmethod
    def _load_vs_profile(cls, pd_: dict) -> "VsProfileData":
        p = VsProfileData(uid=pd_.get("uid", ""), name=pd_.get("name", ""))
        layer_keys = {"median_layer", "percentile_layer",
                      "individual_layer", "sigma_layer"}
        skip = {"uid", "name"} | layer_keys
        for k, v in pd_.items():
            if k not in skip and hasattr(p, k):
                setattr(p, k, v)
        for lk in layer_keys:
            if lk in pd_:
                setattr(p, lk, cls._layer_from_dict(pd_[lk]))
        return p

    @classmethod
    def load(cls, filepath: str) -> "FigureState":
        """Load a FigureState from a pickle file."""
        import pickle
        with open(filepath, "rb") as f:
            data = pickle.load(f)
        return cls.deserialize(data)
