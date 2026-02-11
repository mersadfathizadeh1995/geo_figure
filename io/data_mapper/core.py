"""Core logic for Data Mapper — no GUI dependencies."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

import numpy as np

from .config import (
    DataMapperConfig, ColumnMapping,
    SKIP, FREQ, VELOCITY, SLOWNESS_SM, SLOWNESS_SKM,
    LOGSTD, COV_FRAC, COV_MULT, ABS_STD_SLOW, ABS_STD_VEL,
    WEIGHT, DUMMY_0ON, DUMMY_1ON,
)


class DataMapperCore:
    """Manages column-to-type assignments and validation."""

    def __init__(
        self,
        columns_data: List[np.ndarray],
        config: Optional[DataMapperConfig] = None,
    ):
        self.columns_data = columns_data
        self.config = config or DataMapperConfig()
        self._mapping: Dict[int, str] = {}
        default = self.config.type_options[0] if self.config.type_options else ""
        for i in range(len(columns_data)):
            self._mapping[i] = default

    @property
    def num_columns(self) -> int:
        return len(self.columns_data)

    def set_column_type(self, col_idx: int, type_str: str) -> None:
        if 0 <= col_idx < self.num_columns:
            self._mapping[col_idx] = type_str

    def get_column_type(self, col_idx: int) -> str:
        return self._mapping.get(col_idx, "")

    def auto_detect(self) -> None:
        """Run auto-detection on all columns."""
        for i, col_data in enumerate(self.columns_data):
            detected = None
            if self.config.auto_detect_fn:
                detected = self.config.auto_detect_fn(col_data, i)
            if detected is None:
                detected = detect_column_type(
                    col_data, i, self.columns_data, self.config.type_options
                )
            if detected and detected in self.config.type_options:
                self._mapping[i] = detected

    def validate(self) -> Tuple[bool, List[str]]:
        errors = []
        result = self.get_result_mapping()
        for req in self.config.required_types:
            if req not in result:
                errors.append(f"Missing required: {req}")
        for validator in self.config.validators:
            ok, msg = validator(result)
            if not ok and msg:
                errors.append(msg)
        return (len(errors) == 0, errors)

    def get_result_mapping(self) -> Dict[str, int]:
        """Return {type_name: col_idx} excluding skipped columns."""
        result = {}
        skip = self.config.type_options[0] if self.config.type_options else SKIP
        for col_idx, type_str in self._mapping.items():
            if type_str != skip:
                result[type_str] = col_idx
        return result

    def get_column_mapping(self, remember: bool = False) -> ColumnMapping:
        return ColumnMapping(mapping=self.get_result_mapping(), remember=remember)


# ---------------------------------------------------------------------------
# File parsing
# ---------------------------------------------------------------------------

def parse_file(
    file_path: Union[str, Path],
    comment_chars: str = "#!",
) -> List[np.ndarray]:
    """Parse a tabular data file into per-column arrays.

    Handles UTF-8 and UTF-16 encoding, comment lines, and mixed delimiters.
    """
    file_path = Path(file_path)
    raw = file_path.read_bytes()
    encoding = "utf-16" if raw[:2] in (b"\xff\xfe", b"\xfe\xff") else "utf-8"
    text = raw.decode(encoding, errors="replace")

    rows: List[List[float]] = []
    for line in text.strip().splitlines():
        line = line.strip()
        if not line or line[0] in comment_chars:
            continue
        # Auto-detect delimiter
        if "," in line:
            parts = line.split(",")
        else:
            parts = line.split()
        row: List[float] = []
        for p in parts:
            p = p.strip()
            try:
                row.append(float(p))
            except ValueError:
                row.append(np.nan)
        if row:
            rows.append(row)

    if not rows:
        return []

    max_cols = max(len(r) for r in rows)
    columns: List[np.ndarray] = []
    for ci in range(max_cols):
        col = [r[ci] if ci < len(r) else np.nan for r in rows]
        columns.append(np.array(col, dtype=float))
    return columns


# ---------------------------------------------------------------------------
# Auto-detection heuristics
# ---------------------------------------------------------------------------

def detect_column_type(
    col_data: np.ndarray,
    col_idx: int,
    all_columns: List[np.ndarray],
    type_options: List[str],
) -> Optional[str]:
    """Heuristic-based column type detection for geophysics data."""
    arr = np.asarray(col_data, dtype=float)
    valid = arr[np.isfinite(arr)]
    if valid.size == 0:
        return None

    mn, mx = float(np.min(valid)), float(np.max(valid))
    med = float(np.median(valid))
    is_increasing = np.all(np.diff(valid) >= 0) if valid.size > 1 else False
    is_integer = np.all(valid == np.floor(valid))
    unique_vals = set(valid.tolist())

    # Column 0 is almost always frequency
    if col_idx == 0 and is_increasing and 0.1 <= mn and mx <= 500:
        if FREQ in type_options:
            return FREQ

    # Frequency: monotonically increasing, typical range
    if is_increasing and 0.1 <= mn <= 100 and 1 <= mx <= 500:
        if FREQ in type_options:
            return FREQ

    # Phase velocity: values 30-10000 m/s
    if 30 <= mn and mx <= 10000 and med > 50:
        if VELOCITY in type_options:
            return VELOCITY

    # Slowness (s/m): very small values
    if 0.0001 <= mn and mx <= 0.1 and med < 0.05:
        if SLOWNESS_SM in type_options:
            return SLOWNESS_SM

    # Slowness (s/km): values 0.05-20
    if 0.05 <= mn and mx <= 30 and med < 15:
        # Only if no other column already detected as s/m slowness
        if SLOWNESS_SKM in type_options:
            return SLOWNESS_SKM

    # Weight: integer values, typically small positive
    if is_integer and mn >= 0 and mx < 100 and len(unique_vals) < 20:
        if WEIGHT in type_options:
            return WEIGHT

    # Dummy flag: only 0s and 1s
    if unique_vals <= {0.0, 1.0}:
        if DUMMY_0ON in type_options:
            return DUMMY_0ON

    return None
