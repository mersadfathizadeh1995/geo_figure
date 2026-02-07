"""Extract and parse theoretical dispersion curves from Geopsy .report files.

Uses gpdcreport + gpdc CLI pipeline via bash subprocess.
"""
import re
import subprocess
import platform
import tempfile
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

from geo_figure.core.models import CurveData, CurveType, WaveType

logger = logging.getLogger(__name__)

# ── Geopsy CLI helpers ──────────────────────────────────────────

def _to_bash_path(win_path: Path) -> str:
    """Convert Windows path to Git Bash path (e.g. C:\\Users -> /c/Users)."""
    if platform.system() != "Windows":
        return str(win_path)
    p = win_path.resolve()
    return f"/{p.drive[0].lower()}{p.as_posix()[2:]}"


def _build_env_prefix(geopsy_bin: Path) -> str:
    """Build PATH export prefix for Geopsy tools."""
    if platform.system() == "Windows":
        bp = _to_bash_path(geopsy_bin)
    else:
        bp = str(geopsy_bin)
    prefix = f'export PATH="{bp}:$PATH"'
    if platform.system() != "Windows":
        lib_path = geopsy_bin.parent / "lib"
        if lib_path.exists():
            prefix += f' && export LD_LIBRARY_PATH="{lib_path}:$LD_LIBRARY_PATH"'
    return prefix + " && "


def run_geopsy_pipeline(
    report_file: Path,
    geopsy_bin: Path,
    bash_exe: Path,
    selection_mode: str = "best",
    n_best: int = 1000,
    misfit_max: float = 1.0,
    n_max_models: int = 1000,
    ray_modes: int = 1,
    love_modes: int = 0,
    freq_min: float = 0.2,
    freq_max: float = 50.0,
    n_freq_points: int = 100,
) -> str:
    """Run gpdcreport | gpdc and return stdout text.

    Returns:
        Raw text output (# Mode N ... freq slowness lines).
    Raises:
        RuntimeError on failure.
    """
    report_bash = _to_bash_path(report_file)

    if selection_mode == "best":
        gpdcreport_cmd = f"gpdcreport -best {n_best} {report_bash}"
    else:
        gpdcreport_cmd = f"gpdcreport -m {misfit_max} -n {n_max_models} {report_bash}"

    gpdc_cmd = (
        f"gpdc -R {ray_modes} -L {love_modes} "
        f"-min {freq_min} -max {freq_max} -n {n_freq_points}"
    )

    env_prefix = _build_env_prefix(geopsy_bin)
    full_cmd = f"{env_prefix}{gpdcreport_cmd} | {gpdc_cmd}"

    logger.info(f"Running: {gpdcreport_cmd} | {gpdc_cmd}")

    result = subprocess.run(
        [str(bash_exe), "-c", full_cmd],
        capture_output=True, text=True, timeout=600,
    )

    if result.returncode != 0:
        raise RuntimeError(
            f"Geopsy pipeline failed (rc={result.returncode}):\n{result.stderr}"
        )

    if not result.stdout.strip():
        raise RuntimeError("Geopsy pipeline produced no output")

    return result.stdout


# ── Parsing ─────────────────────────────────────────────────────

_MODE_RE = re.compile(r"#\s*Mode\s+(\d+)", re.IGNORECASE)
_FLOAT_RE = re.compile(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?")


def parse_theoretical_output(
    text: str, wave_type: str = "Rayleigh"
) -> Dict[str, object]:
    """Parse gpdcreport|gpdc output text into per-profile arrays.

    Returns:
        {
          'profiles': {profile_idx: {mode: {'freq': ndarray, 'vel': ndarray}}},
          'n_profiles': int,
          'modes': set of ints,
          'wave_type': str,
        }
    """
    profiles = {}  # profile_idx -> {mode -> {freq: [], vel: []}}
    profile = -1
    mode = None

    for line in text.splitlines():
        line = line.strip()
        m = _MODE_RE.match(line)
        if m:
            mode_tag = int(m.group(1))
            if mode_tag == 0:
                profile += 1
            mode = mode_tag
            continue

        if mode is None or profile < 0:
            continue

        nums = _FLOAT_RE.findall(line)
        if len(nums) >= 2:
            freq_hz = float(nums[0])
            slowness = float(nums[1])
            if slowness <= 0:
                continue
            vel = 1.0 / slowness

            if profile not in profiles:
                profiles[profile] = {}
            if mode not in profiles[profile]:
                profiles[profile][mode] = {"freq": [], "vel": []}

            profiles[profile][mode]["freq"].append(freq_hz)
            profiles[profile][mode]["vel"].append(vel)

    # Convert to numpy
    all_modes = set()
    for p_data in profiles.values():
        for m, arrs in p_data.items():
            arrs["freq"] = np.array(arrs["freq"])
            arrs["vel"] = np.array(arrs["vel"])
            all_modes.add(m)

    return {
        "profiles": profiles,
        "n_profiles": len(profiles),
        "modes": all_modes,
        "wave_type": wave_type,
    }


def parse_theoretical_file(filepath, wave_type: str = "Rayleigh") -> Dict:
    """Parse a gpdc output text file."""
    filepath = Path(filepath)
    text = filepath.read_text(errors="ignore")
    return parse_theoretical_output(text, wave_type)


# ── Statistics ──────────────────────────────────────────────────

def compute_ensemble_statistics(
    parsed: Dict,
    mode: int = 0,
    percentiles: Tuple[float, float] = (16, 84),
    velocity_min: float = 10.0,
    velocity_max: float = 5000.0,
) -> Dict[str, np.ndarray]:
    """Compute median, percentile bands, and sigma_ln from parsed profiles.

    Args:
        parsed: Output from parse_theoretical_output / parse_theoretical_file.
        mode: Mode number (0 = fundamental).
        percentiles: (low, high) percentile pair.
        velocity_min/max: Outlier filter.

    Returns:
        {
          'freq': ndarray (sorted unique frequencies),
          'median': ndarray,
          'p_low': ndarray,
          'p_high': ndarray,
          'envelope_min': ndarray,
          'envelope_max': ndarray,
          'sigma_ln': ndarray,
          'n_profiles': int,
        }
    """
    profiles = parsed["profiles"]

    # Collect all unique frequencies for this mode
    all_freqs = set()
    for p_data in profiles.values():
        if mode in p_data:
            all_freqs.update(p_data[mode]["freq"].tolist())
    if not all_freqs:
        raise ValueError(f"No data found for mode {mode}")

    freqs_sorted = np.array(sorted(all_freqs))

    medians = []
    p_lows = []
    p_highs = []
    env_mins = []
    env_maxs = []
    sigma_lns = []

    for freq in freqs_sorted:
        vels = []
        for p_data in profiles.values():
            if mode not in p_data:
                continue
            idx = np.where(np.isclose(p_data[mode]["freq"], freq, rtol=1e-6))[0]
            if len(idx) > 0:
                v = p_data[mode]["vel"][idx[0]]
                if velocity_min <= v <= velocity_max:
                    vels.append(v)

        if len(vels) == 0:
            medians.append(np.nan)
            p_lows.append(np.nan)
            p_highs.append(np.nan)
            env_mins.append(np.nan)
            env_maxs.append(np.nan)
            sigma_lns.append(np.nan)
            continue

        vels = np.array(vels)
        medians.append(np.median(vels))
        p_lows.append(np.percentile(vels, percentiles[0]))
        p_highs.append(np.percentile(vels, percentiles[1]))
        env_mins.append(np.min(vels))
        env_maxs.append(np.max(vels))

        log_v = np.log(vels[vels > 0])
        sigma_lns.append(np.std(log_v) if len(log_v) > 1 else 0.0)

    # Remove NaN entries
    mask = ~np.isnan(medians)
    return {
        "freq": freqs_sorted[mask],
        "median": np.array(medians)[mask],
        "p_low": np.array(p_lows)[mask],
        "p_high": np.array(p_highs)[mask],
        "envelope_min": np.array(env_mins)[mask],
        "envelope_max": np.array(env_maxs)[mask],
        "sigma_ln": np.array(sigma_lns)[mask],
        "n_profiles": parsed["n_profiles"],
    }


# ── High-level API ──────────────────────────────────────────────

def extract_theoretical_curves(
    report_file: Path,
    geopsy_bin: Path,
    bash_exe: Path,
    curve_type: str = "Rayleigh",
    selection_mode: str = "best",
    n_best: int = 1000,
    misfit_max: float = 1.0,
    n_max_models: int = 1000,
    ray_modes: int = 1,
    love_modes: int = 0,
    freq_min: float = 0.2,
    freq_max: float = 50.0,
    n_freq_points: int = 100,
) -> Dict[str, Dict]:
    """Full pipeline: extract from .report -> parse -> return parsed data.

    Args:
        report_file: Path to .report file.
        geopsy_bin: Path to Geopsy bin directory.
        bash_exe: Path to bash executable.
        curve_type: "Rayleigh", "Love", or "Both".
        selection_mode: "best" or "misfit".
        ... other params for the pipeline.

    Returns:
        Dict mapping wave type key to parsed data dict:
        {"rayleigh": {profiles, n_profiles, modes, wave_type}, "love": {...}}
    """
    results = {}

    specs = []
    if curve_type in ("Rayleigh", "Both"):
        specs.append(("rayleigh", "Rayleigh", ray_modes, 0))
    if curve_type in ("Love", "Both"):
        specs.append(("love", "Love", 0, love_modes))

    for key, wtype, r_modes, l_modes in specs:
        text = run_geopsy_pipeline(
            report_file=report_file,
            geopsy_bin=geopsy_bin,
            bash_exe=bash_exe,
            selection_mode=selection_mode,
            n_best=n_best,
            misfit_max=misfit_max,
            n_max_models=n_max_models,
            ray_modes=r_modes,
            love_modes=l_modes,
            freq_min=freq_min,
            freq_max=freq_max,
            n_freq_points=n_freq_points,
        )
        results[key] = parse_theoretical_output(text, wtype)

    return results


def make_ensemble_curves(
    parsed: Dict,
    mode: int = 0,
    include_individual: bool = True,
    max_individual: int = 200,
) -> List[CurveData]:
    """Convert parsed theoretical data into CurveData objects for plotting.

    Returns list of CurveData:
      - One per individual profile (thin gray, CurveType.THEORETICAL)
      - The caller should compute statistics separately for median/bands.
    """
    profiles = parsed["profiles"]
    wave_type_str = parsed.get("wave_type", "Rayleigh")
    wave_type = WaveType.LOVE if wave_type_str == "Love" else WaveType.RAYLEIGH

    curves = []
    profile_keys = sorted(profiles.keys())

    if include_individual:
        step = max(1, len(profile_keys) // max_individual)
        for i, p_idx in enumerate(profile_keys[::step]):
            if mode not in profiles[p_idx]:
                continue
            data = profiles[p_idx][mode]
            c = CurveData(
                name=f"Model {p_idx}",
                curve_type=CurveType.THEORETICAL,
                wave_type=wave_type,
                mode=mode,
                frequency=data["freq"],
                velocity=data["vel"],
                color="#AAAAAA",
                line_width=0.5,
                visible=True,
            )
            curves.append(c)

    return curves
