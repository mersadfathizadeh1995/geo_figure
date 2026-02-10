"""PyQtGraph-based plot canvas for dispersion curves with subplot support.

Slim orchestrator that delegates to sub-modules in plot_canvas_modules/.
"""
import pyqtgraph as pg
import numpy as np
from PySide6.QtWidgets import QWidget, QVBoxLayout, QInputDialog, QFileDialog
from PySide6.QtCore import Signal, Qt, QRectF
from PySide6.QtGui import QColor, QImage, QPainter
from typing import Dict, Optional, List

from geo_figure.core.models import CurveData, EnsembleData, VsProfileData

from .plot_canvas_modules.constants import (
    VEL_FACTORS, VEL_LABELS, VEL_UNIT_STR,
    LAYOUT_COMBINED, LAYOUT_SPLIT_WAVE, LAYOUT_GRID, LAYOUT_VS_PROFILE,
    LEGEND_ANCHORS,
)
from .plot_canvas_modules.log_freq_axis import LogFreqAxis
from .plot_canvas_modules import layout_builder
from .plot_canvas_modules import curve_renderer
from .plot_canvas_modules import ensemble_renderer
from .plot_canvas_modules import vs_profile_renderer
from .plot_canvas_modules import legend_manager
from .plot_canvas_modules import canvas_export


class PlotCanvas(QWidget):
    """Central plot widget with configurable subplot layouts."""

    curve_clicked = Signal(str)
    layout_changed = Signal(list)

    # Expose legend anchors as class attr for backward compat
    _LEGEND_ANCHORS = LEGEND_ANCHORS

    def __init__(self, parent=None):
        super().__init__(parent)
        self._curves: Dict[str, dict] = {}
        self._ensembles: Dict[str, dict] = {}
        self._vs_profiles: Dict[str, dict] = {}
        self._layout_mode = LAYOUT_COMBINED
        self._grid_rows = 1
        self._grid_cols = 1
        self._grid_col_ratios: List[float] = []
        self._vs_internal_ratios = (0.75, 0.25)
        self._link_y = False
        self._link_x = False
        self._plots: Dict[str, pg.PlotItem] = {}
        self._subplot_names: Dict[str, str] = {}
        self._subplot_types: Dict[str, str] = {}
        self._active_subplot: Optional[str] = None
        self._velocity_unit: str = "metric"
        self._legends: Dict[str, pg.LegendItem] = {}
        self._legend_visible: bool = True
        self._legend_pos: str = "top-right"
        self._legend_offset: tuple = (-10, 10)
        self._legend_font_size: int = 9
        self._legend_mode: str = "per_subplot"
        self._legend_mode_subplot: str = ""
        self._legend_position = "top-right"
        self._setup_ui()

    # ── UI Setup ──────────────────────────────────────────────

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.graphics_layout = pg.GraphicsLayoutWidget()
        layout.addWidget(self.graphics_layout)
        self._build_layout()

    def _build_layout(self):
        layout_builder.build_layout(self)

    def _configure_plot(self, plot, subplot_key=None):
        layout_builder.configure_dc_plot(self, plot, subplot_key)

    def _configure_vs_plot(self, plot, subplot_key):
        layout_builder.configure_vs_plot(self, plot, subplot_key)

    def _configure_sigma_plot(self, plot, subplot_key):
        layout_builder.configure_sigma_plot(self, plot, subplot_key)

    def _build_context_menu(self, plot):
        return layout_builder.build_context_menu(self, plot)

    # ── Layout & Subplot Management ───────────────────────────

    def rebuild(self):
        """Rebuild all plots (e.g. after theme change)."""
        saved_curves = {uid: info["data"] for uid, info in self._curves.items()}
        saved_ensembles = {eid: info["data"] for eid, info in self._ensembles.items()}
        saved_profiles = {uid: info["data"] for uid, info in self._vs_profiles.items()}
        self._curves.clear()
        self._ensembles.clear()
        self._vs_profiles.clear()
        self._build_layout()
        for uid, curve in saved_curves.items():
            self.add_curve(curve)
        for eid, ens in saved_ensembles.items():
            self.add_ensemble(ens)
        for uid, prof in saved_profiles.items():
            self.add_vs_profile(prof)
        self._apply_legend_mode()
        self.auto_range()

    def set_layout_mode(self, mode: str):
        if mode == self._layout_mode:
            return
        old_mode = self._layout_mode
        self._layout_mode = mode
        if old_mode == LAYOUT_VS_PROFILE and mode != LAYOUT_GRID:
            for uid, entry in self._vs_profiles.items():
                data = entry.get("data")
                if data:
                    data.subplot_key = "main"
        self.rebuild()

    def set_grid(self, rows: int, cols: int):
        old_mode = self._layout_mode
        self._grid_rows = max(1, rows)
        self._grid_cols = max(1, cols)
        self._layout_mode = LAYOUT_GRID
        self._grid_col_ratios = [1.0] * self._grid_cols
        if old_mode == LAYOUT_VS_PROFILE:
            self._subplot_types["cell_0_0"] = "vs_profile"
            for uid, entry in self._vs_profiles.items():
                data = entry.get("data")
                if data:
                    data.subplot_key = "cell_0_0"
        self.rebuild()

    def set_grid_col_ratios(self, ratios: list):
        self._grid_col_ratios = list(ratios)
        self.rebuild()

    def set_vs_internal_ratios(self, vs_ratio: float, sig_ratio: float):
        self._vs_internal_ratios = (vs_ratio, sig_ratio)
        self.rebuild()

    def set_subplot_type(self, key: str, stype: str):
        self._subplot_types[key] = stype
        self.rebuild()

    def set_link_y(self, linked: bool):
        self._link_y = linked
        self.rebuild()

    def set_link_x(self, linked: bool):
        self._link_x = linked
        self.rebuild()

    def get_subplot_info(self) -> list:
        return [
            (k, self._subplot_names.get(k, k))
            for k in self._plots.keys()
            if not k.endswith("_sigma") and k != "sigma_ln"
        ]

    def get_subplot_keys(self) -> list:
        return [
            k for k in self._plots.keys()
            if not k.endswith("_sigma") and k != "sigma_ln"
        ]

    def rename_subplot(self, key: str, name: str):
        self._subplot_names[key] = name
        if key in self._plots:
            self._plots[key].setTitle(name)

    @property
    def layout_mode(self) -> str:
        return self._layout_mode

    def get_layout_config(self) -> dict:
        return {
            "layout_mode": self._layout_mode,
            "grid_rows": self._grid_rows,
            "grid_cols": self._grid_cols,
            "grid_col_ratios": list(self._grid_col_ratios),
            "link_y": self._link_y,
            "link_x": self._link_x,
            "subplot_names": dict(self._subplot_names),
            "subplot_types": dict(self._subplot_types),
        }

    def _get_plot_column(self, plot):
        try:
            ci = self.graphics_layout.ci
            for r in range(ci.layout.rowCount()):
                for c in range(ci.layout.columnCount()):
                    item = ci.layout.itemAt(r, c)
                    if item and item.graphicsItem() is plot:
                        return c
        except Exception:
            pass
        return None

    # ── Curve rendering (delegates to curve_renderer) ─────────

    def _get_plot_for_curve(self, curve):
        return curve_renderer.get_plot_for_curve(self, curve)

    def add_curve(self, curve: CurveData):
        curve_renderer.add_curve(self, curve)

    def remove_curve(self, uid: str):
        curve_renderer.remove_curve(self, uid)

    def set_curve_visible(self, uid: str, visible: bool):
        curve_renderer.set_curve_visible(self, uid, visible)

    def highlight_curve(self, uid: str, selected: bool):
        curve_renderer.highlight_curve(self, uid, selected)

    def update_curve_style(self, uid: str, curve: CurveData):
        if uid in self._curves:
            self.add_curve(curve)

    def _remove_plot_items(self, uid: str):
        curve_renderer.remove_plot_items(self, uid)

    # ── Ensemble rendering (delegates to ensemble_renderer) ───

    def add_ensemble(self, ensemble: EnsembleData):
        ensemble_renderer.add_ensemble(self, ensemble)

    def set_ensemble_layer_visible(self, uid: str, layer_name: str,
                                    visible: bool):
        ensemble_renderer.set_ensemble_layer_visible(self, uid, layer_name,
                                                      visible)

    def update_ensemble(self, ensemble: EnsembleData):
        self.add_ensemble(ensemble)

    def remove_ensemble(self, uid: str):
        ensemble_renderer.remove_ensemble(self, uid)

    def _remove_ensemble_items(self, uid: str):
        ensemble_renderer.remove_ensemble_items(self, uid)

    # ── Vs Profile rendering (delegates to vs_profile_renderer) ──

    def add_vs_profile(self, prof_data: VsProfileData):
        vs_profile_renderer.add_vs_profile(self, prof_data)

    def remove_vs_profile(self, uid: str):
        vs_profile_renderer.remove_vs_profile(self, uid)

    def set_vs_profile_layer_visible(self, uid: str, layer_name: str,
                                      visible: bool):
        vs_profile_renderer.set_vs_profile_layer_visible(self, uid,
                                                          layer_name, visible)

    def _rebuild_vs_profile(self, uid: str):
        vs_profile_renderer._rebuild_vs_profile(self, uid)

    def clear_vs_profiles(self):
        for uid in list(self._vs_profiles.keys()):
            self.remove_vs_profile(uid)

    # ── Legend management (delegates to legend_manager) ────────

    def set_legend_visible(self, visible: bool):
        self._legend_visible = visible
        self.rebuild()

    def set_legend_position(self, position: str, offset: tuple = None):
        self._legend_pos = position
        if offset is not None:
            self._legend_offset = offset
        else:
            default_offsets = {
                "top-right": (-10, 10), "top-left": (10, 10),
                "bottom-right": (-10, -10), "bottom-left": (10, -10),
            }
            self._legend_offset = default_offsets.get(position, (-10, 10))
        anchor = LEGEND_ANCHORS.get(self._legend_pos, ((1, 0), (1, 0)))
        for legend in self._legends.values():
            legend.anchor(*anchor)
            legend.setOffset(self._legend_offset)

    def set_legend_font_size(self, size: int):
        self._legend_font_size = max(6, min(24, size))
        for legend in self._legends.values():
            legend.setLabelTextSize(f"{self._legend_font_size}pt")

    def set_legend_mode(self, mode: str):
        if mode != self._legend_mode:
            self._legend_mode = mode
            self.rebuild()

    def get_legend_config(self) -> dict:
        return {
            "visible": self._legend_visible,
            "position": self._legend_pos,
            "offset": self._legend_offset,
            "font_size": self._legend_font_size,
            "mode": self._legend_mode,
        }

    def apply_canvas_config(self, config):
        """Restore canvas display settings from a CanvasConfig object."""
        self._legend_visible = getattr(config, 'legend_visible', True)
        self._legend_pos = getattr(config, 'legend_position', 'top-right')
        self._legend_offset = getattr(config, 'legend_offset', (-10, 10))
        self._legend_font_size = getattr(config, 'legend_font_size', 9)
        self._legend_mode = getattr(config, 'legend_mode', 'per_subplot')
        vs_ratios = getattr(config, 'vs_internal_ratios', (0.75, 0.25))
        self._vs_internal_ratios = tuple(vs_ratios)
        self.set_legend_visible(self._legend_visible)
        self.set_legend_position(self._legend_pos, self._legend_offset)
        self.set_legend_font_size(self._legend_font_size)
        # Apply axis ranges after data is loaded
        axis_ranges = getattr(config, 'axis_ranges', {})
        for key, ((xmin, xmax), (ymin, ymax)) in axis_ranges.items():
            if key in self._plots:
                self._plots[key].setXRange(xmin, xmax, padding=0)
                self._plots[key].setYRange(ymin, ymax, padding=0)

    def _apply_legend_mode(self):
        """After rebuild, rearrange legends according to the current mode."""
        if not self._legend_visible or not self._legends:
            return
        keys = list(self._plots.keys())
        if len(keys) <= 1:
            return

        if self._legend_mode == "per_subplot":
            return

        if self._legend_mode == "combined_first":
            target_key = keys[0]
        elif self._legend_mode == "combined_second":
            target_key = keys[1] if len(keys) > 1 else keys[0]
        elif self._legend_mode == "combined_outside":
            target_key = keys[0]
        else:
            return

        target_legend = self._legends.get(target_key)
        if target_legend is None:
            return

        for key in keys:
            if key == target_key:
                continue
            legend = self._legends.get(key)
            if legend is None:
                continue
            for sample, label in list(legend.items):
                name = label.text
                if name:
                    target_legend.addItem(sample, name)
            legend.setVisible(False)

        if self._legend_mode == "combined_outside":
            target_legend.setVisible(False)
            standalone = pg.LegendItem()
            standalone.setLabelTextSize(f"{self._legend_font_size}pt")
            for key in keys:
                legend = self._legends.get(key)
                if legend is None:
                    continue
                for sample, label in list(legend.items):
                    name = label.text
                    if name:
                        standalone.addItem(sample, name)
            max_col = max(
                (c for r in range(self.graphics_layout.ci.layout.rowCount())
                 for c in range(self.graphics_layout.ci.layout.columnCount())
                 if self.graphics_layout.ci.layout.itemAt(r, c) is not None),
                default=0,
            )
            self.graphics_layout.ci.addItem(standalone, row=0, col=max_col + 1)
            self._legends["__combined__"] = standalone

    # ── Utility ───────────────────────────────────────────────

    def clear_all(self):
        for uid in list(self._curves.keys()):
            self._remove_plot_items(uid)
        self._curves.clear()

    def auto_range(self):
        for plot in self._plots.values():
            plot.enableAutoRange()

    @property
    def active_subplot(self) -> str:
        if self._active_subplot and self._active_subplot in self._plots:
            return self._active_subplot
        keys = list(self._plots.keys())
        return keys[0] if keys else "main"

    @property
    def velocity_unit(self) -> str:
        return self._velocity_unit

    def set_velocity_unit(self, unit: str):
        if unit == self._velocity_unit:
            return
        self._velocity_unit = unit
        self.rebuild()

    # ── Export ────────────────────────────────────────────────

    def export_canvas(self, filepath: str, dpi: int = 150):
        scene = self.graphics_layout.scene()
        source = scene.sceneRect()
        scale = dpi / 96.0
        w = int(source.width() * scale)
        h = int(source.height() * scale)
        image = QImage(w, h, QImage.Format_ARGB32)
        image.fill(QColor(255, 255, 255))
        image.setDotsPerMeterX(int(dpi / 0.0254))
        image.setDotsPerMeterY(int(dpi / 0.0254))
        painter = QPainter(image)
        painter.setRenderHint(QPainter.Antialiasing)
        scene.render(painter, QRectF(0, 0, w, h), source)
        painter.end()
        image.save(filepath)

    def _on_export_action(self):
        dpi, ok = QInputDialog.getInt(
            self, "Export DPI", "Resolution (DPI):", 150, 72, 600, 1,
        )
        if not ok:
            return
        filepath, _ = QFileDialog.getSaveFileName(
            self, "Export Canvas Image", "",
            "PNG (*.png);;JPEG (*.jpg);;TIFF (*.tiff);;All files (*.*)",
        )
        if filepath:
            self.export_canvas(filepath, dpi)

    # ── Click handling ────────────────────────────────────────

    def _on_plot_clicked(self, event, clicked_plot):
        for key, plot in self._plots.items():
            if plot is clicked_plot:
                self._active_subplot = key
                break
        pos = event.scenePos()
        items_at = self.graphics_layout.scene().items(pos)
        hit_scatter = any(
            isinstance(item, pg.ScatterPlotItem) for item in items_at
        )
        if not hit_scatter:
            pass

    def _toggle_legend_from_menu(self):
        self.set_legend_visible(not self._legend_visible)

    def _rename_subplot_from_menu(self, plot):
        key = None
        for k, p in self._plots.items():
            if p is plot:
                key = k
                break
        if key is None:
            return
        current_name = self._subplot_names.get(key, key)
        new_name, ok = QInputDialog.getText(
            self, "Rename Subplot", "New name:", text=current_name,
        )
        if ok and new_name.strip():
            self.rename_subplot(key, new_name.strip())
