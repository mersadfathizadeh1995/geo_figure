"""Unit conversion functions for dispersion curve data.

All stddev conversions produce log-normal standard deviation (logstd).
"""

from __future__ import annotations

import numpy as np

# Maximum sane logstd — logstd > 5.0 means > 14000% uncertainty
MAX_LOGSTD = 5.0


def slowness_to_velocity(
    slowness: np.ndarray, unit: str = "s/m"
) -> np.ndarray:
    """Convert slowness to velocity (m/s).

    Parameters
    ----------
    slowness : array
        Slowness values.
    unit : str
        "s/m" or "s/km".
    """
    s = np.asarray(slowness, dtype=float)
    if unit == "s/km":
        s = s / 1000.0  # convert to s/m
    with np.errstate(divide="ignore", invalid="ignore"):
        vel = np.where(s != 0, 1.0 / s, 0.0)
    return vel


def velocity_to_slowness(velocity: np.ndarray) -> np.ndarray:
    """Convert velocity (m/s) to slowness (s/m)."""
    v = np.asarray(velocity, dtype=float)
    with np.errstate(divide="ignore", invalid="ignore"):
        slow = np.where(v != 0, 1.0 / v, 0.0)
    return slow


# ---------------------------------------------------------------------------
# Stddev normalisation — all paths produce logstd
# ---------------------------------------------------------------------------

def logstd_passthrough(raw: np.ndarray, **_kw) -> np.ndarray:
    """Raw values are already logstd."""
    return _clip_logstd(np.asarray(raw, dtype=float))


def cov_fraction_to_logstd(raw: np.ndarray, **_kw) -> np.ndarray:
    """COV as fraction (0.10 = 10%) -> logstd."""
    cov = np.asarray(raw, dtype=float)
    with np.errstate(invalid="ignore"):
        result = np.sqrt(np.log1p(cov ** 2))
    return _clip_logstd(result)


def cov_multiplier_to_logstd(raw: np.ndarray, **_kw) -> np.ndarray:
    """COV as multiplier (1.10 = 10%) -> logstd."""
    cov = np.asarray(raw, dtype=float) - 1.0
    cov = np.maximum(cov, 0.0)
    with np.errstate(invalid="ignore"):
        result = np.sqrt(np.log1p(cov ** 2))
    return _clip_logstd(result)


def abs_std_slowness_to_logstd(
    raw: np.ndarray, *, slowness: np.ndarray, **_kw
) -> np.ndarray:
    """Absolute slowness stddev -> logstd = |sigma_s / s|."""
    s = np.abs(np.asarray(slowness, dtype=float))
    with np.errstate(divide="ignore", invalid="ignore"):
        result = np.where(s > 0, np.asarray(raw, dtype=float) / s, 0.0)
    return _clip_logstd(result)


def abs_std_velocity_to_logstd(
    raw: np.ndarray, *, velocity: np.ndarray, **_kw
) -> np.ndarray:
    """Absolute velocity stddev -> logstd = |sigma_v / v|."""
    v = np.abs(np.asarray(velocity, dtype=float))
    with np.errstate(divide="ignore", invalid="ignore"):
        result = np.where(v > 0, np.asarray(raw, dtype=float) / v, 0.0)
    return _clip_logstd(result)


def _clip_logstd(arr: np.ndarray) -> np.ndarray:
    """Clip logstd to sane range and replace nan/inf with 0."""
    arr = np.where(np.isfinite(arr), arr, 0.0)
    return np.clip(arr, 0.0, MAX_LOGSTD)


# Lookup by config type name
STDDEV_CONVERTERS = {
    "LogStd": logstd_passthrough,
    "COV (fraction, e.g. 0.10)": cov_fraction_to_logstd,
    "COV (multiplier, e.g. 1.10)": cov_multiplier_to_logstd,
    "Abs StdDev Slowness (s/m)": abs_std_slowness_to_logstd,
    "Abs StdDev Velocity (m/s)": abs_std_velocity_to_logstd,
}


# ---------------------------------------------------------------------------
# Point mask from weight / dummy columns
# ---------------------------------------------------------------------------

def weight_to_mask(weight: np.ndarray) -> np.ndarray:
    """Weight column -> bool mask (weight > 0 means point is ON)."""
    return np.asarray(weight, dtype=float) > 0


def dummy_to_mask(dummy: np.ndarray, mode: str = "0=on") -> np.ndarray:
    """Dummy column -> bool mask.

    mode "0=on":  0 means point is ON  (geopsy convention: dummy points OFF)
    mode "1=on":  1 means point is ON
    """
    d = np.asarray(dummy, dtype=float)
    if mode == "1=on":
        return d > 0.5
    return d < 0.5  # 0=on


# ---------------------------------------------------------------------------
# Heuristic: detect stddev column type automatically
# ---------------------------------------------------------------------------

def detect_stddev_type(
    stddev_col: np.ndarray, slowness: np.ndarray
) -> str:
    """Guess what stddev_col represents and return the converter key.

    Strategy:
    1. Compute candidate_logstd = stddev / |slowness|.
       If the 90th percentile is in a sane range (< 1.5) it is likely
       absolute slowness stddev.
    2. Otherwise the column is already in a normalized form:
       - If all values >= 1.0 and median < 3.0 -> COV multiplier (1.x)
       - Otherwise -> logstd directly

    Defaults to logstd when ambiguous since it is the most common format
    in geophysics tools (geopsy, dinver, etc.).
    """
    valid_slow = np.abs(np.asarray(slowness, dtype=float))
    valid_std = np.asarray(stddev_col, dtype=float)

    mask = np.isfinite(valid_std) & (valid_slow > 0) & np.isfinite(valid_slow)
    if not np.any(mask):
        return "LogStd"

    candidate = valid_std[mask] / valid_slow[mask]
    p90 = float(np.percentile(candidate, 90))

    if p90 < 1.5:
        return "Abs StdDev Slowness (s/m)"

    # Not abs stddev — check if COV multiplier (all values >= 1.0)
    finite_std = valid_std[np.isfinite(valid_std)]
    if finite_std.size > 0:
        min_raw = float(np.min(finite_std))
        med_raw = float(np.median(finite_std))
        if min_raw >= 1.0 and med_raw < 3.0:
            return "COV (multiplier, e.g. 1.10)"

    return "LogStd"
