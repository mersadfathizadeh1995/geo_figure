"""Sheet persistence: save and load self-contained sheet folders.

Each saved sheet is a folder containing:
    manifest.json      -- layout, display settings, data object metadata
    canvas_config.json -- legend, axis ranges, vs internal ratios
    curves/            -- per-curve numpy arrays + copied source files
    ensembles/         -- per-ensemble stats (.npz) + individual profiles
    vs_profiles/       -- per-profile stats (.npz) + raw profiles (.pkl)

The sheet folder is fully self-contained and portable.
"""
import json
import os
import pickle
import re
import shutil
from dataclasses import dataclass, field
from typing import Dict, List, Tuple

import numpy as np

from geo_figure.core.models import (
    CurveData, CurveType, EnsembleData, EnsembleLayer,
    FigureState, SourceType, VsProfileData, WaveType,
)

SHEET_STATE_VERSION = 2


# ── Canvas config ─────────────────────────────────────────────

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
            "legend_offset": list(self.legend_offset),
            "legend_font_size": self.legend_font_size,
            "legend_mode": self.legend_mode,
            "vs_internal_ratios": list(self.vs_internal_ratios),
            "axis_ranges": {
                k: [list(xr), list(yr)] for k, (xr, yr) in self.axis_ranges.items()
            },
        }

    @classmethod
    def from_dict(cls, d: dict) -> "CanvasConfig":
        if d is None:
            return cls()
        raw_ranges = d.get("axis_ranges", {})
        axis_ranges = {}
        for k, v in raw_ranges.items():
            axis_ranges[k] = (tuple(v[0]), tuple(v[1]))
        return cls(
            legend_visible=d.get("legend_visible", True),
            legend_position=d.get("legend_position", "top-right"),
            legend_offset=tuple(d.get("legend_offset", (-10, 10))),
            legend_font_size=d.get("legend_font_size", 9),
            legend_mode=d.get("legend_mode", "per_subplot"),
            vs_internal_ratios=tuple(d.get("vs_internal_ratios", (0.75, 0.25))),
            axis_ranges=axis_ranges,
        )


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


# ── Helpers ───────────────────────────────────────────────────

def _sanitize_name(name: str) -> str:
    safe = re.sub(r'[<>:"/\\|?*]', '_', name).strip()
    return safe or "sheet"


def _layer_to_dict(layer: EnsembleLayer) -> dict:
    return {
        "visible": layer.visible, "color": layer.color,
        "alpha": layer.alpha, "line_width": layer.line_width,
        "legend_label": layer.legend_label,
    }


def _layer_from_dict(d: dict) -> EnsembleLayer:
    if d is None:
        return EnsembleLayer()
    return EnsembleLayer(
        visible=d.get("visible", True), color=d.get("color", "#888888"),
        alpha=d.get("alpha", 255), line_width=d.get("line_width", 2.0),
        legend_label=d.get("legend_label", ""),
    )


def _enum_to_str(val) -> str:
    return val.value if hasattr(val, 'value') else str(val)


def _write_json(filepath: str, data: dict):
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def _read_json(filepath: str) -> dict:
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


# ── Save: curves ──────────────────────────────────────────────

def _save_curve(curve: CurveData, curves_dir: str) -> dict:
    """Save one curve's arrays + copy source file. Returns metadata dict."""
    uid = curve.uid

    # Save numpy arrays
    arrays = {}
    for key in ("frequency", "velocity", "slowness", "stddev", "point_mask"):
        arr = getattr(curve, key, None)
        if arr is not None:
            arr_path = os.path.join(curves_dir, f"{uid}_{key}.npy")
            np.save(arr_path, arr)
            arrays[key] = f"{uid}_{key}.npy"

    # Copy source file if it exists
    source_copy = None
    if curve.filepath and os.path.isfile(curve.filepath):
        ext = os.path.splitext(curve.filepath)[1]
        dest = os.path.join(curves_dir, f"{uid}_source{ext}")
        if not os.path.exists(dest):
            shutil.copy2(curve.filepath, dest)
        source_copy = f"{uid}_source{ext}"

    return {
        "uid": uid, "name": curve.name, "custom_name": curve.custom_name,
        "curve_type": _enum_to_str(curve.curve_type),
        "wave_type": _enum_to_str(curve.wave_type),
        "source_type": _enum_to_str(curve.source_type),
        "mode": curve.mode, "subplot_key": curve.subplot_key,
        "color": curve.color, "line_width": curve.line_width,
        "marker_size": curve.marker_size, "visible": curve.visible,
        "show_error_bars": curve.show_error_bars,
        "resample_enabled": curve.resample_enabled,
        "resample_n_points": curve.resample_n_points,
        "resample_method": curve.resample_method,
        "stddev_type": curve.stddev_type, "stddev_mode": curve.stddev_mode,
        "fixed_logstd": curve.fixed_logstd, "fixed_cov": curve.fixed_cov,
        "stddev_ranges": curve.stddev_ranges,
        "filepath_original": curve.filepath,
        "arrays": arrays,
        "source_copy": source_copy,
    }


# ── Save: ensembles ──────────────────────────────────────────

def _save_ensemble(ens: EnsembleData, ens_dir: str) -> dict:
    """Save one ensemble's stats + individual profiles. Returns metadata dict."""
    uid = ens.uid

    # Save statistics arrays as .npz
    stats = {}
    for key in ("freq", "median", "p_low", "p_high",
                "envelope_min", "envelope_max", "sigma_ln"):
        arr = getattr(ens, key, None)
        if arr is not None:
            stats[key] = arr
    if stats:
        np.savez_compressed(os.path.join(ens_dir, f"{uid}_stats.npz"), **stats)

    # Save individual profiles (list of arrays) as pickle
    has_individual = False
    if ens.individual_freqs and ens.individual_vels:
        ind_path = os.path.join(ens_dir, f"{uid}_individual.pkl")
        with open(ind_path, "wb") as f:
            pickle.dump({
                "freqs": ens.individual_freqs,
                "vels": ens.individual_vels,
            }, f, protocol=pickle.HIGHEST_PROTOCOL)
        has_individual = True

    return {
        "uid": uid, "name": ens.name, "custom_name": ens.custom_name,
        "wave_type": _enum_to_str(ens.wave_type), "mode": ens.mode,
        "n_profiles": ens.n_profiles, "subplot_key": ens.subplot_key,
        "max_individual": ens.max_individual,
        "median_layer": _layer_to_dict(ens.median_layer),
        "percentile_layer": _layer_to_dict(ens.percentile_layer),
        "envelope_layer": _layer_to_dict(ens.envelope_layer),
        "individual_layer": _layer_to_dict(ens.individual_layer),
        "has_stats": bool(stats),
        "has_individual": has_individual,
    }


# ── Save: vs_profiles ────────────────────────────────────────

def _save_vs_profile(prof: VsProfileData, vs_dir: str) -> dict:
    """Save one Vs profile's stats + raw profiles. Returns metadata dict."""
    uid = prof.uid

    # Save statistics arrays
    stats = {}
    for key in ("depth_grid", "median", "p_low", "p_high", "sigma_ln",
                "median_depth_paired", "median_vel_paired",
                "vs30_values", "vs100_values"):
        arr = getattr(prof, key, None)
        if arr is not None:
            stats[key] = arr
    if stats:
        np.savez_compressed(os.path.join(vs_dir, f"{uid}_stats.npz"), **stats)

    # Save paired-format raw profiles as pickle
    has_profiles = False
    if prof.profiles:
        prof_path = os.path.join(vs_dir, f"{uid}_profiles.pkl")
        with open(prof_path, "wb") as f:
            pickle.dump(prof.profiles, f, protocol=pickle.HIGHEST_PROTOCOL)
        has_profiles = True

    return {
        "uid": uid, "name": prof.name, "custom_name": prof.custom_name,
        "profile_type": prof.profile_type, "subplot_key": prof.subplot_key,
        "n_profiles": prof.n_profiles,
        "depth_max_plot": prof.depth_max_plot,
        "max_individual": prof.max_individual,
        "median_layer": _layer_to_dict(prof.median_layer),
        "percentile_layer": _layer_to_dict(prof.percentile_layer),
        "individual_layer": _layer_to_dict(prof.individual_layer),
        "sigma_layer": _layer_to_dict(prof.sigma_layer),
        "has_stats": bool(stats),
        "has_profiles": has_profiles,
    }


# ── Top-level save ────────────────────────────────────────────

def save_sheet(
    project_dir: str,
    sheet_name: str,
    figure_state: FigureState,
    canvas=None,
) -> str:
    """Save a complete sheet to project_dir/sheets/{sheet_name}/.

    Creates a self-contained folder with all data files + manifest.
    Returns the path to the sheet directory.
    """
    safe_name = _sanitize_name(sheet_name)
    sheet_dir = os.path.join(str(project_dir), "sheets", safe_name)

    # Clean previous save
    if os.path.isdir(sheet_dir):
        shutil.rmtree(sheet_dir)

    # Create subdirectories
    curves_dir = os.path.join(sheet_dir, "curves")
    ens_dir = os.path.join(sheet_dir, "ensembles")
    vs_dir = os.path.join(sheet_dir, "vs_profiles")
    sp_dir = os.path.join(sheet_dir, "soil_profiles")
    for d in (curves_dir, ens_dir, vs_dir, sp_dir):
        os.makedirs(d, exist_ok=True)

    # Save data objects
    curve_metas = [_save_curve(c, curves_dir) for c in figure_state.curves]
    ens_metas = [_save_ensemble(e, ens_dir) for e in figure_state.ensembles]
    vs_metas = [_save_vs_profile(p, vs_dir) for p in figure_state.vs_profiles]
    sp_metas = [_save_soil_profile(s, sp_dir)
                for s in getattr(figure_state, 'soil_profiles', []) or []]

    # Build manifest
    manifest = {
        "version": SHEET_STATE_VERSION,
        "sheet_name": sheet_name,
        "layout": {
            "layout_mode": figure_state.layout_mode,
            "grid_rows": figure_state.grid_rows,
            "grid_cols": figure_state.grid_cols,
            "grid_col_ratios": list(figure_state.grid_col_ratios),
            "link_y": figure_state.link_y,
            "link_x": figure_state.link_x,
            "subplot_names": dict(figure_state.subplot_names),
            "subplot_types": dict(figure_state.subplot_types),
        },
        "display": {
            "theme": figure_state.theme,
            "velocity_unit": figure_state.velocity_unit,
        },
        "curves": curve_metas,
        "ensembles": ens_metas,
        "vs_profiles": vs_metas,
        "soil_profiles": sp_metas,
    }
    _write_json(os.path.join(sheet_dir, "manifest.json"), manifest)

    # Save canvas config
    canvas_cfg = capture_canvas_config(canvas) if canvas is not None else CanvasConfig()
    _write_json(os.path.join(sheet_dir, "canvas_config.json"), canvas_cfg.to_dict())

    return sheet_dir


# ── Load: curves ──────────────────────────────────────────────

_CURVE_TYPE_MAP = {v.value: v for v in CurveType}
_WAVE_TYPE_MAP = {v.value: v for v in WaveType}
_SOURCE_TYPE_MAP = {v.value: v for v in SourceType}


def _load_curve(meta: dict, curves_dir: str) -> CurveData:
    """Reconstruct a CurveData from saved metadata + numpy files."""
    c = CurveData(uid=meta["uid"], name=meta["name"])
    c.custom_name = meta.get("custom_name", "")
    c.curve_type = _CURVE_TYPE_MAP.get(meta.get("curve_type", ""), CurveType.RAYLEIGH)
    c.wave_type = _WAVE_TYPE_MAP.get(meta.get("wave_type", ""), WaveType.RAYLEIGH)
    c.source_type = _SOURCE_TYPE_MAP.get(meta.get("source_type", ""), SourceType.PASSIVE)
    c.mode = meta.get("mode", 0)
    c.subplot_key = meta.get("subplot_key", "main")
    c.color = meta.get("color", "#2196F3")
    c.line_width = meta.get("line_width", 1.5)
    c.marker_size = meta.get("marker_size", 6.0)
    c.visible = meta.get("visible", True)
    c.show_error_bars = meta.get("show_error_bars", True)
    c.resample_enabled = meta.get("resample_enabled", False)
    c.resample_n_points = meta.get("resample_n_points", 50)
    c.resample_method = meta.get("resample_method", "log")
    c.stddev_type = meta.get("stddev_type", "logstd")
    c.stddev_mode = meta.get("stddev_mode", "file")
    c.fixed_logstd = meta.get("fixed_logstd", 1.1)
    c.fixed_cov = meta.get("fixed_cov", 0.1)
    c.stddev_ranges = meta.get("stddev_ranges", [])

    # Point filepath to the copied source inside the sheet folder
    source_copy = meta.get("source_copy")
    if source_copy:
        c.filepath = os.path.join(curves_dir, source_copy)
    else:
        c.filepath = meta.get("filepath_original")

    # Load numpy arrays
    for key, filename in meta.get("arrays", {}).items():
        arr_path = os.path.join(curves_dir, filename)
        if os.path.isfile(arr_path):
            setattr(c, key, np.load(arr_path, allow_pickle=False))

    # Recalculate derived fields
    if c.frequency is not None and len(c.frequency) > 0:
        c.n_points = len(c.frequency)
        c.freq_min = float(np.min(c.frequency))
        c.freq_max = float(np.max(c.frequency))

    return c


# ── Load: ensembles ──────────────────────────────────────────

def _load_ensemble(meta: dict, ens_dir: str) -> EnsembleData:
    """Reconstruct an EnsembleData from saved metadata + npz files."""
    e = EnsembleData(uid=meta["uid"], name=meta["name"])
    e.custom_name = meta.get("custom_name", "")
    e.wave_type = _WAVE_TYPE_MAP.get(meta.get("wave_type", ""), WaveType.RAYLEIGH)
    e.mode = meta.get("mode", 0)
    e.n_profiles = meta.get("n_profiles", 0)
    e.subplot_key = meta.get("subplot_key", "main")
    e.max_individual = meta.get("max_individual", 200)

    for lk in ("median_layer", "percentile_layer", "envelope_layer", "individual_layer"):
        if lk in meta:
            setattr(e, lk, _layer_from_dict(meta[lk]))

    # Load stats arrays
    stats_path = os.path.join(ens_dir, f"{e.uid}_stats.npz")
    if os.path.isfile(stats_path):
        with np.load(stats_path) as data:
            for key in ("freq", "median", "p_low", "p_high",
                        "envelope_min", "envelope_max", "sigma_ln"):
                if key in data:
                    setattr(e, key, data[key])

    # Load individual profiles
    ind_path = os.path.join(ens_dir, f"{e.uid}_individual.pkl")
    if os.path.isfile(ind_path):
        with open(ind_path, "rb") as f:
            ind = pickle.load(f)
        e.individual_freqs = ind.get("freqs")
        e.individual_vels = ind.get("vels")

    return e


# ── Load: vs_profiles ────────────────────────────────────────

def _load_vs_profile(meta: dict, vs_dir: str) -> VsProfileData:
    """Reconstruct a VsProfileData from saved metadata + files."""
    p = VsProfileData(uid=meta.get("uid", ""), name=meta.get("name", ""))
    p.custom_name = meta.get("custom_name", "")
    p.profile_type = meta.get("profile_type", "vs")
    p.subplot_key = meta.get("subplot_key", "main")
    p.n_profiles = meta.get("n_profiles", 0)
    p.depth_max_plot = meta.get("depth_max_plot", 100.0)
    p.max_individual = meta.get("max_individual", 5000)

    for lk in ("median_layer", "percentile_layer", "individual_layer", "sigma_layer"):
        if lk in meta:
            setattr(p, lk, _layer_from_dict(meta[lk]))

    # Load stats arrays
    stats_path = os.path.join(vs_dir, f"{p.uid}_stats.npz")
    if os.path.isfile(stats_path):
        with np.load(stats_path) as data:
            for key in ("depth_grid", "median", "p_low", "p_high", "sigma_ln",
                        "median_depth_paired", "median_vel_paired",
                        "vs30_values", "vs100_values"):
                if key in data:
                    setattr(p, key, data[key])

    # Load raw paired profiles
    prof_path = os.path.join(vs_dir, f"{p.uid}_profiles.pkl")
    if os.path.isfile(prof_path):
        with open(prof_path, "rb") as f:
            p.profiles = pickle.load(f)

    return p


# ── Save: soil_profiles ──────────────────────────────────────

def _save_soil_profile(sp, sp_dir: str) -> dict:
    """Save a SoilProfile to disk and return metadata dict."""
    meta = {
        "uid": sp.uid,
        "name": sp.name,
        "custom_name": sp.custom_name,
        "n_layers": sp.n_layers,
        "visible": sp.visible,
        "color": sp.color,
        "line_width": sp.line_width,
        "alpha": sp.alpha,
        "show_uncertainty": sp.show_uncertainty,
        "render_property": getattr(sp, "render_property", "vs"),
        "subplot_key": sp.subplot_key,
        "depth_max_display": sp.depth_max_display,
        "halfspace_extension": sp.halfspace_extension,
        "filepath": sp.filepath,
        "model_id": sp.model_id,
        "profile_index": sp.profile_index,
    }
    # Save numpy arrays
    arrays = {}
    for k in ("thickness", "top_depth", "bot_depth", "vs", "vp", "density",
              "vs_low", "vs_high", "depth_low", "depth_high"):
        arr = getattr(sp, k, None)
        if arr is not None:
            arrays[k] = arr
    if arrays:
        np.savez_compressed(os.path.join(sp_dir, f"{sp.uid}.npz"), **arrays)
    return meta


# ── Load: soil_profiles ──────────────────────────────────────

def _load_soil_profile(meta: dict, sp_dir: str):
    """Reconstruct a SoilProfile from saved metadata + files."""
    from geo_figure.core.models import SoilProfile

    sp = SoilProfile(
        uid=meta.get("uid", ""),
        name=meta.get("name", "Soil Profile"),
        custom_name=meta.get("custom_name", ""),
        n_layers=meta.get("n_layers", 0),
        visible=meta.get("visible", True),
        color=meta.get("color", "#2196F3"),
        line_width=meta.get("line_width", 1.5),
        alpha=meta.get("alpha", 255),
        show_uncertainty=meta.get("show_uncertainty", True),
        render_property=meta.get("render_property", "vs"),
        subplot_key=meta.get("subplot_key", "main"),
        depth_max_display=meta.get("depth_max_display", 0.0),
        halfspace_extension=meta.get("halfspace_extension", 0.15),
        filepath=meta.get("filepath"),
        model_id=meta.get("model_id"),
        profile_index=meta.get("profile_index", 0),
    )
    arr_path = os.path.join(sp_dir, f"{sp.uid}.npz")
    if os.path.isfile(arr_path):
        with np.load(arr_path) as data:
            for key in ("thickness", "top_depth", "bot_depth", "vs", "vp", "density",
                        "vs_low", "vs_high", "depth_low", "depth_high"):
                if key in data:
                    setattr(sp, key, data[key])
    return sp


# ── Top-level load ────────────────────────────────────────────

def load_sheet(sheet_path: str) -> Tuple[str, FigureState, CanvasConfig]:
    """Load a sheet from a saved sheet directory or manifest.json path.

    Returns (sheet_name, FigureState, CanvasConfig).
    """
    if os.path.isdir(sheet_path):
        sheet_dir = sheet_path
    else:
        sheet_dir = os.path.dirname(sheet_path)

    manifest = _read_json(os.path.join(sheet_dir, "manifest.json"))
    sheet_name = manifest.get("sheet_name", "Loaded Sheet")

    layout = manifest.get("layout", {})
    display = manifest.get("display", {})

    curves_dir = os.path.join(sheet_dir, "curves")
    ens_dir = os.path.join(sheet_dir, "ensembles")
    vs_dir = os.path.join(sheet_dir, "vs_profiles")
    sp_dir = os.path.join(sheet_dir, "soil_profiles")

    curves = [_load_curve(m, curves_dir) for m in manifest.get("curves", [])]
    ensembles = [_load_ensemble(m, ens_dir) for m in manifest.get("ensembles", [])]
    vs_profiles = [_load_vs_profile(m, vs_dir) for m in manifest.get("vs_profiles", [])]
    soil_profiles = []
    for m in manifest.get("soil_profiles", []):
        try:
            soil_profiles.append(_load_soil_profile(m, sp_dir))
        except Exception:
            pass

    figure_state = FigureState(
        layout_mode=layout.get("layout_mode", "combined"),
        grid_rows=layout.get("grid_rows", 1),
        grid_cols=layout.get("grid_cols", 1),
        grid_col_ratios=layout.get("grid_col_ratios", []),
        link_y=layout.get("link_y", False),
        link_x=layout.get("link_x", False),
        subplot_names=layout.get("subplot_names", {}),
        subplot_types=layout.get("subplot_types", {}),
        curves=curves,
        ensembles=ensembles,
        vs_profiles=vs_profiles,
        soil_profiles=soil_profiles,
        theme=display.get("theme", "light"),
        velocity_unit=display.get("velocity_unit", "metric"),
    )

    cc_path = os.path.join(sheet_dir, "canvas_config.json")
    if os.path.isfile(cc_path):
        canvas_config = CanvasConfig.from_dict(_read_json(cc_path))
    else:
        canvas_config = CanvasConfig()

    return sheet_name, figure_state, canvas_config


# ── Listing ───────────────────────────────────────────────────

def list_saved_sheets(project_dir: str) -> List[Tuple[str, str]]:
    """List available saved sheets.

    Returns list of (sheet_name, sheet_dir_path) tuples.
    """
    sheets_dir = os.path.join(str(project_dir), "sheets")
    if not os.path.isdir(sheets_dir):
        return []
    results = []
    for entry in sorted(os.listdir(sheets_dir)):
        manifest_path = os.path.join(sheets_dir, entry, "manifest.json")
        if os.path.isfile(manifest_path):
            try:
                manifest = _read_json(manifest_path)
                name = manifest.get("sheet_name", entry)
            except Exception:
                name = entry
            results.append((name, os.path.join(sheets_dir, entry)))
    return results


def delete_saved_sheet(project_dir: str, sheet_name: str) -> bool:
    """Delete a saved sheet folder. Returns True if removed."""
    safe_name = _sanitize_name(sheet_name)
    sheet_dir = os.path.join(str(project_dir), "sheets", safe_name)
    if os.path.isdir(sheet_dir):
        shutil.rmtree(sheet_dir, ignore_errors=True)
        return True
    return False
