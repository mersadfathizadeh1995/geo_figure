"""Read dispersion curve files in various formats."""
import numpy as np
from pathlib import Path
from typing import List, Tuple, Optional

from geo_figure.core.models import CurveData, CurveType, WaveType
from geo_figure.io.converters import (
    slowness_to_velocity, velocity_to_slowness,
    detect_stddev_type, STDDEV_CONVERTERS,
    weight_to_mask, dummy_to_mask,
)
from geo_figure.io.data_mapper.core import parse_file
from geo_figure.io.data_mapper.config import (
    ColumnMapping, FREQ, VELOCITY, SLOWNESS_SM, SLOWNESS_SKM,
    LOGSTD, COV_FRAC, COV_MULT, ABS_STD_SLOW, ABS_STD_VEL,
    WEIGHT, DUMMY_0ON, DUMMY_1ON,
)


# ---------------------------------------------------------------------------
# Mapped reader — uses explicit column assignments from data mapper
# ---------------------------------------------------------------------------

def read_dispersion_mapped(
    filepath: str,
    mapping: ColumnMapping,
    wave_type: WaveType = WaveType.RAYLEIGH,
    mode: int = 0,
    name: str = "",
) -> CurveData:
    """Read a dispersion curve using an explicit column mapping."""
    path = Path(filepath)
    if not name:
        name = path.stem

    columns = parse_file(filepath)
    if not columns:
        raise ValueError(f"No data found in {filepath}")

    m = mapping.mapping

    # Frequency (required)
    if FREQ not in m:
        raise ValueError("Frequency column not mapped")
    freq = columns[m[FREQ]]

    # Velocity / slowness
    velocity = slowness = None
    if VELOCITY in m:
        velocity = columns[m[VELOCITY]]
        slowness = velocity_to_slowness(velocity)
    elif SLOWNESS_SM in m:
        slowness = columns[m[SLOWNESS_SM]]
        velocity = slowness_to_velocity(slowness, unit="s/m")
    elif SLOWNESS_SKM in m:
        slowness = columns[m[SLOWNESS_SKM]]
        velocity = slowness_to_velocity(slowness, unit="s/km")
        slowness = slowness / 1000.0  # store as s/m internally
    else:
        raise ValueError("No velocity or slowness column mapped")

    # Stddev
    stddev = None
    stddev_type_key = None
    for key in (LOGSTD, COV_FRAC, COV_MULT, ABS_STD_SLOW, ABS_STD_VEL):
        if key in m:
            stddev_type_key = key
            break
    if stddev_type_key is not None:
        raw_std = columns[m[stddev_type_key]]
        conv_fn = STDDEV_CONVERTERS[stddev_type_key]
        stddev = conv_fn(raw_std, slowness=slowness, velocity=velocity)

    # Point mask from weight / dummy
    point_mask = np.ones(len(freq), dtype=bool)
    if WEIGHT in m:
        point_mask &= weight_to_mask(columns[m[WEIGHT]])
    if DUMMY_0ON in m:
        point_mask &= dummy_to_mask(columns[m[DUMMY_0ON]], mode="0=on")
    if DUMMY_1ON in m:
        point_mask &= dummy_to_mask(columns[m[DUMMY_1ON]], mode="1=on")

    curve_type = (CurveType.RAYLEIGH if wave_type == WaveType.RAYLEIGH
                  else CurveType.LOVE)
    return CurveData(
        name=name, curve_type=curve_type, wave_type=wave_type, mode=mode,
        frequency=freq, velocity=velocity, slowness=slowness,
        stddev=stddev, filepath=str(filepath), stddev_type="logstd",
        point_mask=point_mask,
    )


# ---------------------------------------------------------------------------
# Auto-detecting readers (txt / csv)
# ---------------------------------------------------------------------------

def _parse_tabular(filepath: str) -> Tuple[np.ndarray, int]:
    """Parse a tabular file (txt or csv) into an array + column count."""
    columns = parse_file(filepath)
    if not columns:
        raise ValueError(f"No data found in {filepath}")
    ncols = len(columns)
    nrows = len(columns[0])
    arr = np.column_stack(columns)
    return arr, ncols


def _detect_vel_slow(col2: np.ndarray):
    """Heuristic: slowness vs velocity for the second column."""
    median_val = float(np.median(col2[col2 > 0])) if np.any(col2 > 0) else 0
    if median_val < 0.1:
        slowness = col2
        velocity = slowness_to_velocity(slowness, unit="s/m")
    else:
        velocity = col2
        slowness = velocity_to_slowness(velocity)
    return velocity, slowness


def _detect_stddev(arr: np.ndarray, ncols: int, slowness: np.ndarray,
                   velocity: np.ndarray):
    """Auto-detect stddev from column 3 and point_mask from cols 4-5."""
    stddev = None
    point_mask = np.ones(arr.shape[0], dtype=bool)

    if ncols >= 3:
        raw_std = arr[:, 2]
        det_type = detect_stddev_type(raw_std, slowness)
        conv_fn = STDDEV_CONVERTERS[det_type]
        stddev = conv_fn(raw_std, slowness=slowness, velocity=velocity)

    if ncols >= 4:
        col4 = arr[:, 3]
        unique4 = set(col4[np.isfinite(col4)].tolist())
        is_integer = np.all(col4 == np.floor(col4))
        if is_integer and unique4 - {0.0, 1.0}:
            # Multiple integer values beyond 0/1 -> weight column
            point_mask &= weight_to_mask(col4)
        elif unique4 <= {0.0, 1.0} and len(unique4) == 2:
            # Both 0 and 1 present -> meaningful dummy flag
            point_mask &= dummy_to_mask(col4, mode="0=on")

    if ncols >= 5:
        col5 = arr[:, 4]
        unique5 = set(col5[np.isfinite(col5)].tolist())
        if unique5 <= {0.0, 1.0} and len(unique5) == 2:
            # 5th column is a weight: 1 = on, 0 = off
            point_mask &= weight_to_mask(col5)

    return stddev, point_mask


def read_dispersion_txt(filepath: str, wave_type: WaveType = WaveType.RAYLEIGH,
                        mode: int = 0, name: str = "") -> CurveData:
    """Read a dispersion curve from a text file (2-5 columns).

    Auto-detects slowness vs velocity, stddev type, weight, and dummy columns.
    """
    path = Path(filepath)
    if not name:
        name = path.stem

    arr, ncols = _parse_tabular(filepath)
    if ncols < 2:
        raise ValueError(f"Need at least 2 columns, got {ncols}")

    freq = arr[:, 0]
    velocity, slowness = _detect_vel_slow(arr[:, 1])
    stddev, point_mask = _detect_stddev(arr, ncols, slowness, velocity)

    curve_type = (CurveType.RAYLEIGH if wave_type == WaveType.RAYLEIGH
                  else CurveType.LOVE)
    return CurveData(
        name=name, curve_type=curve_type, wave_type=wave_type, mode=mode,
        frequency=freq, velocity=velocity, slowness=slowness,
        stddev=stddev, filepath=str(filepath), stddev_type="logstd",
        point_mask=point_mask,
    )


def read_dispersion_csv(filepath: str, wave_type: WaveType = WaveType.RAYLEIGH,
                        mode: int = 0, name: str = "") -> CurveData:
    """Read a dispersion curve from a CSV file.

    Auto-detects slowness vs velocity and stddev type.
    """
    path = Path(filepath)
    if not name:
        name = path.stem

    arr, ncols = _parse_tabular(filepath)
    if ncols < 2:
        raise ValueError(f"Need at least 2 columns, got {ncols}")

    freq = arr[:, 0]
    velocity, slowness = _detect_vel_slow(arr[:, 1])
    stddev, point_mask = _detect_stddev(arr, ncols, slowness, velocity)

    curve_type = (CurveType.RAYLEIGH if wave_type == WaveType.RAYLEIGH
                  else CurveType.LOVE)
    return CurveData(
        name=name, curve_type=curve_type, wave_type=wave_type, mode=mode,
        frequency=freq, velocity=velocity, slowness=slowness,
        stddev=stddev, filepath=str(filepath), stddev_type="logstd",
        point_mask=point_mask,
    )


# ---------------------------------------------------------------------------
# Detect-and-read entry point
# ---------------------------------------------------------------------------

def detect_and_read(filepath: str,
                    mapping: Optional[ColumnMapping] = None,
                    wave_type: WaveType = WaveType.RAYLEIGH,
                    mode: int = 0,
                    name: str = "") -> List[CurveData]:
    """Auto-detect file format and read curves.

    If *mapping* is provided, uses explicit column assignments instead of
    heuristics (for txt/csv files).
    """
    path = Path(filepath)
    ext = path.suffix.lower()

    if ext == '.target':
        from geo_figure.io.target_reader import read_target_file
        curves, _ = read_target_file(str(filepath))
        return curves

    # Mapped reader (user picked columns in the data mapper dialog)
    if mapping is not None:
        return [read_dispersion_mapped(
            str(filepath), mapping, wave_type=wave_type,
            mode=mode, name=name,
        )]

    if ext == '.csv':
        return [read_dispersion_csv(str(filepath), wave_type=wave_type,
                                    mode=mode, name=name)]
    elif ext == '.txt':
        raw = path.read_bytes()[:256]
        text = raw.decode('utf-8', errors='replace')
        if '# Layered model' in text:
            return read_theoretical_dc_txt(str(filepath))
        else:
            return [read_dispersion_txt(str(filepath), wave_type=wave_type,
                                        mode=mode, name=name)]
    else:
        return [read_dispersion_txt(str(filepath), wave_type=wave_type,
                                    mode=mode, name=name)]


def read_theoretical_dc_txt(filepath: str) -> List[CurveData]:
    """
    Read theoretical DC curves from a Geopsy gpdc output file.

    Format: comment lines starting with #, then freq slowness pairs.
    Multiple models separated by comment lines.
    """
    path = Path(filepath)
    text = path.read_text(encoding='utf-8', errors='replace')

    curves = []
    current_model = []
    model_index = 0

    for line in text.strip().splitlines():
        line = line.strip()
        if line.startswith('#'):
            if 'Layered model' in line:
                if current_model:
                    arr = np.array(current_model)
                    freq = arr[:, 0]
                    slowness = arr[:, 1]
                    with np.errstate(divide='ignore', invalid='ignore'):
                        vel = np.where(slowness != 0, 1.0 / slowness, 0.0)
                    curves.append(CurveData(
                        name=f"Model {model_index}",
                        curve_type=CurveType.THEORETICAL,
                        wave_type=WaveType.RAYLEIGH,
                        frequency=freq,
                        velocity=vel,
                        slowness=slowness,
                        filepath=str(filepath),
                        color="#808080",
                        line_width=0.5,
                    ))
                    model_index += 1
                    current_model = []
            continue
        parts = line.split()
        if len(parts) >= 2:
            try:
                current_model.append([float(parts[0]), float(parts[1])])
            except ValueError:
                continue

    # Last model
    if current_model:
        arr = np.array(current_model)
        freq = arr[:, 0]
        slowness = arr[:, 1]
        with np.errstate(divide='ignore', invalid='ignore'):
            vel = np.where(slowness != 0, 1.0 / slowness, 0.0)
        curves.append(CurveData(
            name=f"Model {model_index}",
            curve_type=CurveType.THEORETICAL,
            wave_type=WaveType.RAYLEIGH,
            frequency=freq,
            velocity=vel,
            slowness=slowness,
            filepath=str(filepath),
            color="#808080",
            line_width=0.5,
        ))

    return curves
