"""Read Vs/Vp/density soil profiles from various file formats."""

from __future__ import annotations

import re
from pathlib import Path
from typing import List, Optional

import numpy as np

from geo_figure.core.models import SoilProfile, SoilProfileGroup
from geo_figure.io.data_mapper.config import ColumnMapping


# ---------------------------------------------------------------------------
# Geopsy layered-model format
# ---------------------------------------------------------------------------

def read_geopsy_layered(filepath: str, name: str = "") -> List[SoilProfile]:
    """Read one or more geopsy layered models.

    Format per model::

        N                        (number of layers incl. halfspace)
        thickness  Vp  Vs  density
        ...
        0  Vp  Vs  density       (halfspace: thickness = 0)

    Multiple models may be concatenated in one file.
    """
    path = Path(filepath)
    if not name:
        name = path.stem

    text = path.read_text(encoding="utf-8", errors="replace")
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]

    profiles: List[SoilProfile] = []
    idx = 0
    model_num = 0

    while idx < len(lines):
        # Expect an integer count line
        try:
            n_layers = int(lines[idx])
        except ValueError:
            idx += 1
            continue
        idx += 1

        thicknesses, vp_vals, vs_vals, rho_vals = [], [], [], []
        for _ in range(n_layers):
            if idx >= len(lines):
                break
            parts = lines[idx].split()
            idx += 1
            if len(parts) < 4:
                continue
            thicknesses.append(float(parts[0]))
            vp_vals.append(float(parts[1]))
            vs_vals.append(float(parts[2]))
            rho_vals.append(float(parts[3]))

        if not thicknesses:
            continue

        pname = name if len(lines) < n_layers + 5 else f"{name} #{model_num + 1}"
        profiles.append(SoilProfile.from_thickness(
            thickness=thicknesses, vs=vs_vals, vp=vp_vals, density=rho_vals,
            name=pname, filepath=str(filepath), profile_index=model_num,
        ))
        model_num += 1

    return profiles


# ---------------------------------------------------------------------------
# Geopsy report paired-step text (Vs_01.txt style)
# ---------------------------------------------------------------------------

def read_paired_step_txt(filepath: str, name: str = "") -> List[SoilProfile]:
    """Read paired step-function profiles from geopsy report output.

    Format::

        # Layered model 147: value=0.980944
        # Vs
            122.264  0
            122.264  1.464
            175.766  1.464
            ...
            2714.407  2924.394
            2714.407  inf
    """
    path = Path(filepath)
    if not name:
        name = path.stem

    text = path.read_text(encoding="utf-8", errors="replace")
    profiles: List[SoilProfile] = []
    current_vs: List[float] = []
    current_depth: List[float] = []
    model_label = ""
    model_idx = 0

    def _flush():
        nonlocal current_vs, current_depth, model_idx
        if len(current_vs) < 2:
            current_vs, current_depth = [], []
            return
        prof = _paired_to_soil_profile(
            np.array(current_vs), np.array(current_depth),
            name=model_label or f"{name} #{model_idx + 1}",
            filepath=str(filepath), profile_index=model_idx,
        )
        if prof is not None:
            profiles.append(prof)
        model_idx += 1
        current_vs, current_depth = [], []

    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            m = re.search(r"Layered model\s+(\d+)", stripped)
            if m:
                _flush()
                model_label = f"{name} #{m.group(1)}"
            continue
        parts = stripped.split()
        if len(parts) >= 2:
            try:
                v, d = float(parts[0]), float(parts[1])
                current_vs.append(v)
                current_depth.append(d)
            except ValueError:
                continue

    _flush()
    return profiles


def _paired_to_soil_profile(
    vs_arr: np.ndarray, depth_arr: np.ndarray, **kw
) -> Optional[SoilProfile]:
    """Convert paired (vs, depth) arrays to a SoilProfile.

    Paired format has two rows per layer interface::

        vs0  d0    (top of layer)
        vs0  d1    (bottom of layer = top of next)

    If the row count is odd, the last row is treated as the start of a
    halfspace layer (no bottom specified).
    """
    n = len(vs_arr)
    if n < 2:
        return None

    # If odd, append a halfspace row
    if n % 2 != 0:
        vs_arr = np.append(vs_arr, vs_arr[-1])
        depth_arr = np.append(depth_arr, np.inf)
        n += 1

    n_layers = n // 2
    vs_vals = np.zeros(n_layers)
    top = np.zeros(n_layers)
    bot = np.zeros(n_layers)

    for i in range(n_layers):
        vs_vals[i] = vs_arr[2 * i]
        top[i] = depth_arr[2 * i]
        bot[i] = depth_arr[2 * i + 1]

    thickness = bot - top
    # Halfspace: if last bot is inf, mark thickness as 0
    if np.isinf(bot[-1]):
        thickness[-1] = 0.0

    return SoilProfile(
        n_layers=n_layers, thickness=thickness,
        top_depth=top, bot_depth=bot, vs=vs_vals,
        **kw,
    )


# ---------------------------------------------------------------------------
# CSV formats (auto-detect header columns)
# ---------------------------------------------------------------------------

_HEADER_MAP = {
    # Normalised header -> canonical name
    "vs": "vs", "vs(m/s)": "vs", "vs (m/s)": "vs", "vs_m_s": "vs",
    "vp": "vp", "vp(m/s)": "vp", "vp (m/s)": "vp",
    "density": "density", "rho": "density", "density(kg/m3)": "density",
    "depth": "depth", "depth(m)": "depth", "depth (m)": "depth",
    "top_depth": "top_depth", "top_depth(m)": "top_depth",
    "top_depth (m)": "top_depth",
    "bot_depth": "bot_depth", "bot_depth(m)": "bot_depth",
    "bot_depth (m)": "bot_depth",
    "thickness": "thickness", "thickness(m)": "thickness",
    "thickness (m)": "thickness",
    "layer": "layer",
    "profile": "profile", "profile_id": "profile",
    "model_id": "model_id",
}


def _normalise_header(h: str) -> str:
    import re
    s = h.strip().lower().replace(" ", "").replace("_", "")
    # Strip any parenthesized unit suffix, e.g. "vs(ft/s)" -> "vs"
    s = re.sub(r"\(.*?\)$", "", s)
    return s


def _map_headers(raw_headers):
    """Map raw CSV headers to canonical names."""
    mapping = {}
    for i, h in enumerate(raw_headers):
        # Try exact match first, then normalised
        hl = h.strip().lower()
        if hl in _HEADER_MAP:
            mapping[_HEADER_MAP[hl]] = i
            continue
        hn = _normalise_header(h)
        for key, canon in _HEADER_MAP.items():
            if _normalise_header(key) == hn:
                mapping[canon] = i
                break
    return mapping


def read_vs_csv(filepath: str, name: str = "") -> List[SoilProfile]:
    """Read Vs profiles from a CSV file with auto-detected headers."""
    path = Path(filepath)
    if not name:
        name = path.stem

    import csv
    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
        reader = csv.reader(f)
        rows = list(reader)

    if len(rows) < 2:
        raise ValueError(f"CSV too short: {filepath}")

    # Detect header
    header_row = rows[0]
    try:
        float(header_row[0])
        has_header = False
    except (ValueError, IndexError):
        has_header = True

    if not has_header:
        raise ValueError(f"CSV has no header row: {filepath}")

    col_map = _map_headers(header_row)
    data_rows = rows[1:]

    # Parse all data into array
    arr = []
    for row in data_rows:
        try:
            arr.append([_parse_csv_val(x) for x in row])
        except ValueError:
            continue
    if not arr:
        raise ValueError(f"No numeric data in CSV: {filepath}")
    arr = np.array(arr)

    # Detect format
    has_profile_col = "profile" in col_map
    has_paired_depth = "depth" in col_map and "top_depth" not in col_map

    if has_paired_depth:
        return _read_paired_csv(arr, col_map, name, filepath)
    elif has_profile_col:
        return _read_multi_profile_csv(arr, col_map, name, filepath)
    else:
        return _read_single_profile_csv(arr, col_map, name, filepath)


def _parse_csv_val(s: str) -> float:
    s = s.strip().lower()
    if s in ("inf", "infinity", "halfspace"):
        return np.inf
    return float(s)


def _read_paired_csv(arr, col_map, name, filepath) -> List[SoilProfile]:
    """CSV with Depth(m), Vs(m/s) — paired step format."""
    depth = arr[:, col_map["depth"]]
    vs = arr[:, col_map.get("vs", -1)] if "vs" in col_map else None
    vp = arr[:, col_map["vp"]] if "vp" in col_map else None

    if vs is None and vp is None:
        raise ValueError("CSV must have Vs or Vp column")

    val = vs if vs is not None else vp
    prof = _paired_to_soil_profile(val, depth, name=name, filepath=filepath)
    if prof is None:
        raise ValueError("Could not parse paired CSV data")
    if vp is not None and vs is not None:
        # Re-extract vp per layer
        prof.vp = np.array([vp[2 * i] for i in range(prof.n_layers)])
    return [prof]


def _read_single_profile_csv(arr, col_map, name, filepath) -> List[SoilProfile]:
    """CSV with Layer, Vs, Top_Depth, Bot_Depth, Thickness."""
    n = arr.shape[0]

    vs = arr[:, col_map["vs"]] if "vs" in col_map else None
    vp = arr[:, col_map["vp"]] if "vp" in col_map else None
    density = arr[:, col_map["density"]] if "density" in col_map else None

    if "top_depth" in col_map and "bot_depth" in col_map:
        top = arr[:, col_map["top_depth"]]
        bot = arr[:, col_map["bot_depth"]]
        thickness = bot - top
        thickness[np.isinf(bot)] = 0.0
    elif "thickness" in col_map:
        thickness = arr[:, col_map["thickness"]]
        return [SoilProfile.from_thickness(
            thickness=thickness, vs=vs, vp=vp, density=density,
            name=name, filepath=filepath,
        )]
    else:
        raise ValueError("CSV needs Top/Bot Depth or Thickness columns")

    model_id = None
    if "model_id" in col_map:
        model_id = str(int(arr[0, col_map["model_id"]]))

    return [SoilProfile(
        n_layers=n, thickness=thickness, top_depth=top, bot_depth=bot,
        vs=vs, vp=vp, density=density,
        name=name, filepath=filepath, model_id=model_id,
    )]


def _read_multi_profile_csv(arr, col_map, name, filepath) -> List[SoilProfile]:
    """CSV with Profile column — split into separate SoilProfile per profile ID."""
    profile_col = arr[:, col_map["profile"]]
    unique_ids = []
    seen = set()
    for v in profile_col:
        iv = int(v)
        if iv not in seen:
            unique_ids.append(iv)
            seen.add(iv)

    profiles: List[SoilProfile] = []
    for pid in unique_ids:
        mask = profile_col.astype(int) == pid
        sub = arr[mask]
        n = sub.shape[0]

        vs = sub[:, col_map["vs"]] if "vs" in col_map else None
        vp = sub[:, col_map["vp"]] if "vp" in col_map else None
        density = sub[:, col_map["density"]] if "density" in col_map else None

        model_id = None
        if "model_id" in col_map:
            model_id = str(int(sub[0, col_map["model_id"]]))

        if "top_depth" in col_map and "bot_depth" in col_map:
            top = sub[:, col_map["top_depth"]]
            bot = sub[:, col_map["bot_depth"]]
            thickness = bot - top
            thickness[np.isinf(bot)] = 0.0
        elif "thickness" in col_map:
            thickness = sub[:, col_map["thickness"]]
            top = np.zeros(n)
            cum = 0.0
            bot = np.zeros(n)
            for i in range(n):
                top[i] = cum
                if thickness[i] <= 0 and i == n - 1:
                    bot[i] = np.inf
                else:
                    cum += thickness[i]
                    bot[i] = cum
        else:
            continue

        pname = f"{name} #{pid}"
        if model_id:
            pname = f"{name} #{model_id}"

        profiles.append(SoilProfile(
            n_layers=n, thickness=thickness, top_depth=top, bot_depth=bot,
            vs=vs, vp=vp, density=density,
            name=pname, filepath=filepath, model_id=model_id,
            profile_index=int(pid) - 1,
        ))

    return profiles


# ---------------------------------------------------------------------------
# Data-mapper-based reader
# ---------------------------------------------------------------------------

def read_vs_mapped(
    filepath: str,
    mapping: ColumnMapping,
    name: str = "",
) -> List[SoilProfile]:
    """Read a Vs profile using explicit column mapping from the data mapper."""
    from geo_figure.io.data_mapper.core import parse_file

    path = Path(filepath)
    if not name:
        name = path.stem

    columns = parse_file(filepath)
    if not columns:
        raise ValueError(f"No data in {filepath}")

    m = mapping.mapping

    # Required: some depth info + some value
    vs = columns[m["Vs (m/s)"]] if "Vs (m/s)" in m else None
    vp = columns[m["Vp (m/s)"]] if "Vp (m/s)" in m else None
    density = columns[m["Density (kg/m3)"]] if "Density (kg/m3)" in m else None

    if vs is None and vp is None and density is None:
        raise ValueError("Need at least one of Vs, Vp, or Density")

    if "Thickness (m)" in m:
        return [SoilProfile.from_thickness(
            thickness=columns[m["Thickness (m)"]],
            vs=vs, vp=vp, density=density,
            name=name, filepath=str(filepath),
        )]

    if "Top Depth (m)" in m and "Bottom Depth (m)" in m:
        top = columns[m["Top Depth (m)"]]
        bot = columns[m["Bottom Depth (m)"]]
        n = len(top)
        thickness = bot - top
        thickness[np.isinf(bot)] = 0.0
        return [SoilProfile(
            n_layers=n, thickness=thickness, top_depth=top, bot_depth=bot,
            vs=vs, vp=vp, density=density,
            name=name, filepath=str(filepath),
        )]

    raise ValueError("Need Thickness or Top/Bottom Depth columns")


# ---------------------------------------------------------------------------
# Data mapper configuration for Vs
# ---------------------------------------------------------------------------

def vs_profile_config():
    """DataMapperConfig preset for Vs profile files."""
    from geo_figure.io.data_mapper.config import DataMapperConfig

    def _validate(mapping):
        has_val = any(k in mapping for k in ("Vs (m/s)", "Vp (m/s)", "Density (kg/m3)"))
        has_depth = ("Thickness (m)" in mapping
                     or ("Top Depth (m)" in mapping and "Bottom Depth (m)" in mapping))
        errors = []
        if not has_val:
            errors.append("Need Vs, Vp, or Density")
        if not has_depth:
            errors.append("Need Thickness or Top+Bottom Depth")
        return (len(errors) == 0, "; ".join(errors))

    return DataMapperConfig(
        type_options=[
            "Skipped",
            "Thickness (m)", "Top Depth (m)", "Bottom Depth (m)",
            "Vs (m/s)", "Vp (m/s)", "Density (kg/m3)",
            "Vs Low (m/s)", "Vs High (m/s)",
            "Depth Low (m)", "Depth High (m)",
            "Layer Number", "Profile ID", "Model ID",
        ],
        required_types=[],
        validators=[_validate],
        window_title="Map Vs Profile Columns",
    )


# ---------------------------------------------------------------------------
# Auto-detect entry point
# ---------------------------------------------------------------------------

def detect_and_read_vs(
    filepath: str,
    mapping: Optional[ColumnMapping] = None,
    name: str = "",
) -> List[SoilProfile]:
    """Auto-detect file format and read Vs profile(s).

    If *mapping* is provided, uses explicit column assignments.
    """
    if mapping is not None:
        return read_vs_mapped(filepath, mapping, name=name)

    path = Path(filepath)
    ext = path.suffix.lower()

    # Read first lines for heuristic detection
    raw = path.read_bytes()
    enc = "utf-16" if raw[:2] in (b"\xff\xfe", b"\xfe\xff") else "utf-8"
    text = raw.decode(enc, errors="replace")
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if not lines:
        raise ValueError(f"Empty file: {filepath}")

    # CSV with header?
    if ext == ".csv":
        return read_vs_csv(filepath, name=name)

    # Geopsy layered model: first non-comment line is a single integer
    first_data = None
    for ln in lines:
        if not ln.startswith("#") and not ln.startswith("!"):
            first_data = ln
            break

    if first_data is not None:
        parts = first_data.split()
        if len(parts) == 1:
            try:
                int(parts[0])
                return read_geopsy_layered(filepath, name=name)
            except ValueError:
                pass

    # Paired step from geopsy report (has "# Layered model" comments)
    if "# Layered model" in text or "# Vs" in text:
        return read_paired_step_txt(filepath, name=name)

    # Fallback: try CSV-style even for .txt
    if ext == ".txt":
        # Check if first non-comment line could be a CSV header
        for ln in lines:
            if not ln.startswith("#"):
                if "," in ln:
                    return read_vs_csv(filepath, name=name)
                break

    # Last resort: try paired step (two numeric columns)
    return read_paired_step_txt(filepath, name=name)
