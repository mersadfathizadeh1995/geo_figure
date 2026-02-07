"""Read dispersion curve files in various formats."""
import numpy as np
from pathlib import Path
from typing import List, Tuple, Optional
from geo_figure.core.models import CurveData, CurveType, WaveType


def read_dispersion_txt(filepath: str, wave_type: WaveType = WaveType.RAYLEIGH,
                        mode: int = 0, name: str = "") -> CurveData:
    """
    Read a dispersion curve from a text file.

    Supports formats:
    - 3 columns: frequency, slowness, stddev
    - 2 columns: frequency, slowness (or frequency, velocity)

    Handles both UTF-8 and UTF-16 encoding.
    """
    path = Path(filepath)
    if not name:
        name = path.stem

    # Detect encoding
    raw = path.read_bytes()
    encoding = 'utf-16' if raw[:2] in (b'\xff\xfe', b'\xfe\xff') else 'utf-8'

    # Read lines, skip comments
    text = raw.decode(encoding, errors='replace')
    lines = []
    for line in text.strip().splitlines():
        line = line.strip()
        if not line or line.startswith('#') or line.startswith('!'):
            continue
        lines.append(line)

    if not lines:
        raise ValueError(f"No data found in {filepath}")

    # Parse numeric data
    data = []
    for line in lines:
        parts = line.split()
        try:
            row = [float(x) for x in parts]
            data.append(row)
        except ValueError:
            continue

    if not data:
        raise ValueError(f"No numeric data found in {filepath}")

    arr = np.array(data)
    ncols = arr.shape[1]

    freq = arr[:, 0]

    if ncols >= 2:
        col2 = arr[:, 1]
        # Heuristic: if values < 0.1, it's slowness; if > 10, it's velocity
        median_val = np.median(col2[col2 > 0]) if np.any(col2 > 0) else 0
        if median_val < 0.1:
            slowness = col2
            with np.errstate(divide='ignore', invalid='ignore'):
                velocity = np.where(slowness != 0, 1.0 / slowness, 0.0)
        else:
            velocity = col2
            with np.errstate(divide='ignore', invalid='ignore'):
                slowness = np.where(velocity != 0, 1.0 / velocity, 0.0)
    else:
        raise ValueError(f"Need at least 2 columns, got {ncols}")

    # Column 3 is absolute stddev of slowness (s/m).
    # Convert to log-normal stddev: logstd = sigma_slow / |slow|
    if ncols >= 3:
        stddev_slow_abs = arr[:, 2]
        with np.errstate(divide='ignore', invalid='ignore'):
            stddev = np.where(np.abs(slowness) > 0,
                              stddev_slow_abs / np.abs(slowness), 0.0)
    else:
        stddev = None

    curve_type = CurveType.RAYLEIGH if wave_type == WaveType.RAYLEIGH else CurveType.LOVE

    return CurveData(
        name=name,
        curve_type=curve_type,
        wave_type=wave_type,
        mode=mode,
        frequency=freq,
        velocity=velocity,
        slowness=slowness,
        stddev=stddev,
        filepath=str(filepath),
        stddev_type="logstd",
    )


def read_dispersion_csv(filepath: str, wave_type: WaveType = WaveType.RAYLEIGH,
                        mode: int = 0, name: str = "") -> CurveData:
    """
    Read a dispersion curve from a CSV file.

    Expects columns: frequency, slowness_or_velocity, [stddev]
    First row may be a header (auto-detected).
    """
    path = Path(filepath)
    if not name:
        name = path.stem

    import csv
    with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
        reader = csv.reader(f)
        rows = list(reader)

    if not rows:
        raise ValueError(f"No data found in {filepath}")

    # Skip header row if non-numeric
    start = 0
    try:
        float(rows[0][0])
    except (ValueError, IndexError):
        start = 1

    data = []
    for row in rows[start:]:
        try:
            vals = [float(x.strip()) for x in row if x.strip()]
            if len(vals) >= 2:
                data.append(vals)
        except ValueError:
            continue

    if not data:
        raise ValueError(f"No numeric data found in {filepath}")

    arr = np.array(data)
    ncols = arr.shape[1]
    freq = arr[:, 0]
    col2 = arr[:, 1]

    median_val = np.median(col2[col2 > 0]) if np.any(col2 > 0) else 0
    if median_val < 0.1:
        slowness = col2
        with np.errstate(divide='ignore', invalid='ignore'):
            velocity = np.where(slowness != 0, 1.0 / slowness, 0.0)
    else:
        velocity = col2
        with np.errstate(divide='ignore', invalid='ignore'):
            slowness = np.where(velocity != 0, 1.0 / velocity, 0.0)

    if ncols >= 3:
        stddev_slow_abs = arr[:, 2]
        with np.errstate(divide='ignore', invalid='ignore'):
            stddev = np.where(np.abs(slowness) > 0,
                              stddev_slow_abs / np.abs(slowness), 0.0)
    else:
        stddev = None

    curve_type = CurveType.RAYLEIGH if wave_type == WaveType.RAYLEIGH else CurveType.LOVE

    return CurveData(
        name=name, curve_type=curve_type, wave_type=wave_type, mode=mode,
        frequency=freq, velocity=velocity, slowness=slowness, stddev=stddev,
        filepath=str(filepath), stddev_type="logstd",
    )


def detect_and_read(filepath: str) -> List[CurveData]:
    """Auto-detect file format and read curves."""
    path = Path(filepath)
    ext = path.suffix.lower()

    if ext == '.target':
        from geo_figure.io.target_reader import read_target_file
        curves, _ = read_target_file(str(filepath))
        return curves
    elif ext == '.csv':
        return [read_dispersion_csv(str(filepath))]
    elif ext == '.txt':
        # Check if it's a theoretical DC file (gpdc output)
        raw = path.read_bytes()[:256]
        text = raw.decode('utf-8', errors='replace')
        if '# Layered model' in text:
            return read_theoretical_dc_txt(str(filepath))
        else:
            return [read_dispersion_txt(str(filepath))]
    else:
        return [read_dispersion_txt(str(filepath))]


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
