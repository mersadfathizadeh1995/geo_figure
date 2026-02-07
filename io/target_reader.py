"""Read Dinver .target files (gzip-compressed tar with UTF-16 XML)."""
import tarfile
import io
import numpy as np
import xml.etree.ElementTree as ET
from typing import List, Tuple, Dict
from geo_figure.core.models import CurveData, CurveType, WaveType


def read_target_file(filepath: str) -> Tuple[List[CurveData], Dict]:
    """
    Parse a Dinver .target file and return dispersion curves.

    Returns:
        (curves, summary) where curves is a list of CurveData objects
        and summary is a dict with metadata.
    """
    with open(filepath, 'rb') as f:
        raw = f.read()

    with tarfile.open(fileobj=io.BytesIO(raw), mode='r:gz') as tar:
        xml_bytes = tar.extractfile('contents.xml').read()

    # Decode UTF-16 (BOM-detected)
    if xml_bytes[:2] == b'\xff\xfe':
        xml_text = xml_bytes.decode('utf-16-le')
    elif xml_bytes[:2] == b'\xfe\xff':
        xml_text = xml_bytes.decode('utf-16-be')
    else:
        xml_text = xml_bytes.decode('utf-8')

    root = ET.fromstring(xml_text)

    curves = []
    rayleigh_count = 0
    love_count = 0

    for mc in root.iter('ModalCurve'):
        name = mc.findtext('name', 'Unknown')
        enabled = mc.findtext('enabled', 'true').lower() == 'true'

        mode_elem = mc.find('Mode')
        if mode_elem is None:
            continue

        polarization = mode_elem.findtext('polarization', 'Rayleigh')
        mode_index = int(mode_elem.findtext('index', '0'))

        # Determine wave type
        if 'rayleigh' in polarization.lower():
            wave_type = WaveType.RAYLEIGH
            curve_type = CurveType.RAYLEIGH
            rayleigh_count += 1
        else:
            wave_type = WaveType.LOVE
            curve_type = CurveType.LOVE
            love_count += 1

        # Extract valid data points
        freqs, slows, stddevs, valids = [], [], [], []
        for pt in mc.iter('RealStatisticalPoint'):
            x = float(pt.findtext('x', '0'))
            mean = float(pt.findtext('mean', '0'))
            stddev = float(pt.findtext('stddev', '0'))
            valid = pt.findtext('valid', 'false').lower() == 'true'

            freqs.append(x)
            slows.append(mean)
            stddevs.append(stddev)
            valids.append(valid)

        if not any(valids):
            continue

        freq_arr = np.array(freqs)
        slow_arr = np.array(slows)
        stddev_arr = np.array(stddevs)
        valid_arr = np.array(valids)

        # Convert slowness to velocity
        with np.errstate(divide='ignore', invalid='ignore'):
            vel_arr = np.where(slow_arr > 0, 1.0 / slow_arr, 0.0)

        # Stddev in target is log-normal factor; convert to logstd
        # For Dinver: stddev is typically ~1.1, meaning CoV ~10%
        # logstd = ln(stddev_factor) when factor > 1
        with np.errstate(divide='ignore', invalid='ignore'):
            logstd_arr = np.where(stddev_arr > 0, np.log(stddev_arr), 0.0)

        # Build point mask from valid flags
        point_mask = valid_arr.copy()

        curve = CurveData(
            name=name,
            curve_type=curve_type,
            wave_type=wave_type,
            mode=mode_index,
            frequency=freq_arr,
            velocity=vel_arr,
            slowness=slow_arr,
            stddev=logstd_arr,
            stddev_type="logstd",
            filepath=filepath,
            point_mask=point_mask,
            visible=enabled,
        )
        curves.append(curve)

    summary = {
        'rayleigh_count': rayleigh_count,
        'love_count': love_count,
        'total_curves': len(curves),
    }
    return curves, summary
