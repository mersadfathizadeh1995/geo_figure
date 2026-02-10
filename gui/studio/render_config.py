"""Render config persistence: save and load Matplotlib Studio settings.

Saves StudioSettings as human-readable JSON files in project_dir/render/.
Each config is a named style template that can be applied to any sheet.
"""
import dataclasses
import json
import os
import re
from typing import get_type_hints, get_origin, get_args

from geo_figure.gui.studio.models import (
    StudioSettings, FigureConfig, TypographyConfig, AxisConfig,
    GridConfig, TickConfig, LegendConfig, ExportOptions,
)

CONFIG_VERSION = 1
RENDER_DIR = "render"

# Mapping of field type annotation to dataclass constructor
_DATACLASS_MAP = {
    "FigureConfig": FigureConfig,
    "TypographyConfig": TypographyConfig,
    "AxisConfig": AxisConfig,
    "GridConfig": GridConfig,
    "TickConfig": TickConfig,
    "LegendConfig": LegendConfig,
    "ExportOptions": ExportOptions,
    "StudioSettings": StudioSettings,
}


# ── Generic dataclass <-> dict conversion ─────────────────────

def _to_dict(obj) -> dict:
    """Recursively convert a dataclass instance to a plain dict."""
    if not dataclasses.is_dataclass(obj) or isinstance(obj, type):
        return obj
    result = {}
    for f in dataclasses.fields(obj):
        val = getattr(obj, f.name)
        if dataclasses.is_dataclass(val) and not isinstance(val, type):
            result[f.name] = _to_dict(val)
        elif isinstance(val, dict):
            result[f.name] = {
                k: _to_dict(v) if dataclasses.is_dataclass(v) else v
                for k, v in val.items()
            }
        elif isinstance(val, (list, tuple)):
            result[f.name] = [
                _to_dict(v) if dataclasses.is_dataclass(v) else v
                for v in val
            ]
        else:
            result[f.name] = val
    return result


def _from_dict(cls, d: dict):
    """Reconstruct a dataclass instance from a plain dict."""
    if d is None:
        return cls()
    hints = get_type_hints(cls)
    kwargs = {}
    for f in dataclasses.fields(cls):
        if f.name not in d:
            continue
        val = d[f.name]
        ftype = hints.get(f.name)
        # Nested dataclass field
        type_name = getattr(ftype, "__name__", "")
        if type_name in _DATACLASS_MAP and isinstance(val, dict):
            kwargs[f.name] = _from_dict(_DATACLASS_MAP[type_name], val)
        # Dict[str, SomeDataclass]
        elif get_origin(ftype) is dict and isinstance(val, dict):
            args = get_args(ftype)
            if len(args) == 2:
                val_type_name = getattr(args[1], "__name__", "")
                if val_type_name in _DATACLASS_MAP:
                    kwargs[f.name] = {
                        k: _from_dict(_DATACLASS_MAP[val_type_name], v)
                        if isinstance(v, dict) else v
                        for k, v in val.items()
                    }
                else:
                    kwargs[f.name] = val
            else:
                kwargs[f.name] = val
        # Tuple (e.g. vs_width_ratios)
        elif get_origin(ftype) is tuple and isinstance(val, list):
            kwargs[f.name] = tuple(val)
        # Optional[Tuple[float, float]]
        elif _is_optional_tuple(ftype):
            if val is None:
                kwargs[f.name] = None
            elif isinstance(val, list):
                kwargs[f.name] = tuple(val)
            else:
                kwargs[f.name] = val
        # Optional[List[str]]
        elif _is_optional_list(ftype):
            kwargs[f.name] = val
        else:
            kwargs[f.name] = val
    return cls(**kwargs)


def _is_optional_tuple(ftype) -> bool:
    """Check if type is Optional[Tuple[...]]."""
    origin = get_origin(ftype)
    if origin is not None:
        args = get_args(ftype)
        for a in args:
            if get_origin(a) is tuple:
                return True
    return False


def _is_optional_list(ftype) -> bool:
    """Check if type is Optional[List[...]]."""
    origin = get_origin(ftype)
    if origin is not None:
        args = get_args(ftype)
        for a in args:
            if get_origin(a) is list:
                return True
    return False


# ── Public API ────────────────────────────────────────────────

def settings_to_dict(settings: StudioSettings) -> dict:
    """Convert StudioSettings to a JSON-serializable dict."""
    d = _to_dict(settings)
    d["_config_version"] = CONFIG_VERSION
    return d


def settings_from_dict(d: dict) -> StudioSettings:
    """Reconstruct StudioSettings from a dict (ignores unknown keys)."""
    d.pop("_config_version", None)
    return _from_dict(StudioSettings, d)


def save_render_config(project_dir: str, config_name: str,
                       settings: StudioSettings) -> str:
    """Save StudioSettings as JSON in project_dir/render/{config_name}.json.

    Returns the path to the saved file.
    """
    render_dir = os.path.join(project_dir, RENDER_DIR)
    os.makedirs(render_dir, exist_ok=True)
    safe_name = _sanitize_name(config_name)
    filepath = os.path.join(render_dir, f"{safe_name}.json")
    data = settings_to_dict(settings)
    data["_config_name"] = config_name
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    return filepath


def load_render_config(filepath: str) -> StudioSettings:
    """Load StudioSettings from a JSON config file."""
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)
    data.pop("_config_name", None)
    return settings_from_dict(data)


def list_render_configs(project_dir: str) -> list:
    """List available render configs as [(name, filepath), ...].

    Reads _config_name from each JSON file for display names.
    """
    render_dir = os.path.join(project_dir, RENDER_DIR)
    if not os.path.isdir(render_dir):
        return []
    configs = []
    for fname in sorted(os.listdir(render_dir)):
        if not fname.endswith(".json"):
            continue
        fpath = os.path.join(render_dir, fname)
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                data = json.load(f)
            display_name = data.get("_config_name", fname[:-5])
        except Exception:
            display_name = fname[:-5]
        configs.append((display_name, fpath))
    return configs


def _sanitize_name(name: str) -> str:
    safe = re.sub(r'[<>:"/\\|?*]', '_', name).strip()
    return safe or "config"
