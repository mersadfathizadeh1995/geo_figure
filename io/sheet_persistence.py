"""Sheet persistence: save and load complete sheet states to disk.

File format: .gfs (GeoFigure Sheet) — pickled SheetState dict.
Storage layout:
    project_dir/sheets/{sheet_name}/sheet.gfs
"""
import os
import pickle
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from geo_figure.core.models import FigureState


# ── Sheet state container ─────────────────────────────────────

SHEET_STATE_VERSION = 1


@dataclass
class CanvasConfig:
    """Canvas display settings not carried by FigureState."""
    legend_visible: bool = True
    legend_position: str = "top-right"
    legend_offset: tuple = (-10, 10)
    legend_font_size: int = 9
    legend_mode: str = "per_subplot"
    vs_internal_ratios: tuple = (0.75, 0.25)
    axis_ranges: Dict[str, Tuple[Tuple[float, float], Tuple[float, float]]] = field(
        default_factory=dict
    )

    def to_dict(self) -> dict:
        return {
            "legend_visible": self.legend_visible,
            "legend_position": self.legend_position,
            "legend_offset": self.legend_offset,
            "legend_font_size": self.legend_font_size,
            "legend_mode": self.legend_mode,
            "vs_internal_ratios": self.vs_internal_ratios,
            "axis_ranges": dict(self.axis_ranges),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "CanvasConfig":
        if d is None:
            return cls()
        return cls(
            legend_visible=d.get("legend_visible", True),
            legend_position=d.get("legend_position", "top-right"),
            legend_offset=tuple(d.get("legend_offset", (-10, 10))),
            legend_font_size=d.get("legend_font_size", 9),
            legend_mode=d.get("legend_mode", "per_subplot"),
            vs_internal_ratios=tuple(d.get("vs_internal_ratios", (0.75, 0.25))),
            axis_ranges=d.get("axis_ranges", {}),
        )


def _sanitize_name(name: str) -> str:
    """Create a filesystem-safe folder name from a sheet name."""
    safe = re.sub(r'[<>:"/\\|?*]', '_', name).strip()
    return safe or "sheet"


# ── Capture from live canvas ──────────────────────────────────

def capture_canvas_config(canvas) -> CanvasConfig:
    """Extract canvas display settings from a live PlotCanvas."""
    legend_cfg = canvas.get_legend_config()
    axis_ranges = {}
    if hasattr(canvas, '_plots'):
        for key, plot_item in canvas._plots.items():
            if key.endswith("_sigma"):
                continue
            try:
                vb = plot_item.vb
                x_range, y_range = vb.viewRange()
                axis_ranges[key] = (
                    (x_range[0], x_range[1]),
                    (y_range[0], y_range[1]),
                )
            except Exception:
                pass
    vs_ratios = getattr(canvas, '_vs_internal_ratios', (0.75, 0.25))
    return CanvasConfig(
        legend_visible=legend_cfg.get("visible", True),
        legend_position=legend_cfg.get("position", "top-right"),
        legend_offset=legend_cfg.get("offset", (-10, 10)),
        legend_font_size=legend_cfg.get("font_size", 9),
        legend_mode=legend_cfg.get("mode", "per_subplot"),
        vs_internal_ratios=vs_ratios,
        axis_ranges=axis_ranges,
    )


# ── Save ──────────────────────────────────────────────────────

def save_sheet(
    project_dir: str,
    sheet_name: str,
    figure_state: FigureState,
    canvas=None,
) -> str:
    """Save a complete sheet to project_dir/sheets/{sheet_name}/sheet.gfs.

    Returns the path to the saved file.
    """
    safe_name = _sanitize_name(sheet_name)
    sheet_dir = os.path.join(str(project_dir), "sheets", safe_name)
    os.makedirs(sheet_dir, exist_ok=True)
    filepath = os.path.join(sheet_dir, "sheet.gfs")

    canvas_cfg = capture_canvas_config(canvas) if canvas is not None else CanvasConfig()

    payload = {
        "version": SHEET_STATE_VERSION,
        "sheet_name": sheet_name,
        "figure_state": figure_state.serialize(),
        "canvas_config": canvas_cfg.to_dict(),
    }
    with open(filepath, "wb") as f:
        pickle.dump(payload, f, protocol=pickle.HIGHEST_PROTOCOL)
    return filepath


# ── Load ──────────────────────────────────────────────────────

def load_sheet(filepath: str) -> Tuple[str, FigureState, CanvasConfig]:
    """Load a sheet from a .gfs file.

    Returns (sheet_name, FigureState, CanvasConfig).
    """
    with open(filepath, "rb") as f:
        payload = pickle.load(f)
    sheet_name = payload.get("sheet_name", "Loaded Sheet")
    fs_data = payload.get("figure_state", {})
    figure_state = FigureState.deserialize(fs_data)
    canvas_config = CanvasConfig.from_dict(payload.get("canvas_config"))
    return sheet_name, figure_state, canvas_config


# ── Listing ───────────────────────────────────────────────────

def list_saved_sheets(project_dir: str) -> List[Tuple[str, str]]:
    """List available saved sheets.

    Returns list of (sheet_name, filepath) tuples.
    """
    sheets_dir = os.path.join(str(project_dir), "sheets")
    if not os.path.isdir(sheets_dir):
        return []
    results = []
    for entry in sorted(os.listdir(sheets_dir)):
        gfs_path = os.path.join(sheets_dir, entry, "sheet.gfs")
        if os.path.isfile(gfs_path):
            try:
                with open(gfs_path, "rb") as f:
                    payload = pickle.load(f)
                name = payload.get("sheet_name", entry)
            except Exception:
                name = entry
            results.append((name, gfs_path))
    return results


def delete_saved_sheet(project_dir: str, sheet_name: str) -> bool:
    """Delete a saved sheet folder. Returns True if removed."""
    import shutil
    safe_name = _sanitize_name(sheet_name)
    sheet_dir = os.path.join(str(project_dir), "sheets", safe_name)
    if os.path.isdir(sheet_dir):
        shutil.rmtree(sheet_dir, ignore_errors=True)
        return True
    return False
