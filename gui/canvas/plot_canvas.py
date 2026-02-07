"""PyQtGraph-based plot canvas for dispersion curves with subplot support."""
import pyqtgraph as pg
import numpy as np
from PySide6.QtWidgets import QWidget, QVBoxLayout, QFileDialog, QInputDialog
from PySide6.QtCore import Signal, Qt, QRectF
from PySide6.QtGui import QColor, QPen, QImage, QPainter
from typing import Dict, Optional, List
from geo_figure.core.models import CurveData, CurveType, WaveType, EnsembleData

# Velocity unit conversion
_VEL_FACTORS = {"metric": 1.0, "imperial": 3.28084}
_VEL_LABELS = {"metric": "Phase Velocity (m/s)", "imperial": "Phase Velocity (ft/s)"}
_VEL_UNIT_STR = {"metric": "m/s", "imperial": "ft/s"}


class LogFreqAxis(pg.AxisItem):
    """X-axis that displays Hz values from log10-transformed coordinates.

    Generates ticks at "nice" values: 0.1, 0.2, 0.5, 1, 2, 5, 10, 20, 50, 100...
    """

    # Nice number sequence per decade
    _NICE_MAJORS = [1, 2, 5]
    _NICE_MINORS = [1, 1.5, 2, 3, 4, 5, 6, 7, 8, 9]

    def tickValues(self, minVal, maxVal, size):
        """Generate tick positions at nice Hz values."""
        if minVal >= maxVal:
            return []

        # Convert log10 range to Hz
        hz_min = max(10 ** minVal, 0.01)
        hz_max = 10 ** maxVal

        ticks = []

        # Major ticks: 1-2-5 sequence across decades
        major_pos = []
        decade = 10 ** int(np.floor(np.log10(hz_min)))
        while decade <= hz_max * 10:
            for m in self._NICE_MAJORS:
                val = m * decade
                if hz_min <= val <= hz_max:
                    major_pos.append(np.log10(val))
            decade *= 10
        if major_pos:
            ticks.append((None, major_pos))

        # Minor ticks: fill in between
        minor_pos = []
        decade = 10 ** int(np.floor(np.log10(hz_min)))
        while decade <= hz_max * 10:
            for m in self._NICE_MINORS:
                val = m * decade
                lv = np.log10(val)
                if hz_min <= val <= hz_max and lv not in major_pos:
                    minor_pos.append(lv)
            decade *= 10
        if minor_pos:
            ticks.append((None, minor_pos))

        return ticks

    def tickStrings(self, values, scale, spacing):
        strings = []
        for v in values:
            try:
                hz = 10 ** v
                if hz >= 100:
                    strings.append(f"{hz:.0f}")
                elif hz >= 10:
                    strings.append(f"{hz:.0f}")
                elif hz >= 1:
                    strings.append(f"{hz:.1f}")
                else:
                    strings.append(f"{hz:.2f}")
            except (OverflowError, ValueError):
                strings.append("")
        return strings


# Layout modes
LAYOUT_COMBINED = "combined"
LAYOUT_SPLIT_WAVE = "split_wave"
LAYOUT_GRID = "grid"


class PlotCanvas(QWidget):
    """Central plot widget with configurable subplot layouts."""

    curve_clicked = Signal(str)  # uid of clicked curve
    layout_changed = Signal(list)  # [(key, name), ...] when subplot structure changes

    def __init__(self, parent=None):
        super().__init__(parent)
        self._curves: Dict[str, dict] = {}  # uid -> {data, plot, items}
        self._ensembles: Dict[str, dict] = {}  # ensemble_id -> {plot, items, stats}
        self._layout_mode = LAYOUT_COMBINED
        self._grid_rows = 1
        self._grid_cols = 1
        self._link_y = False
        self._link_x = False
        self._plots: Dict[str, pg.PlotItem] = {}  # key -> PlotItem
        self._subplot_names: Dict[str, str] = {}   # key -> display name
        self._active_subplot: Optional[str] = None  # currently selected subplot key
        self._velocity_unit: str = "metric"  # "metric" (m/s) or "imperial" (ft/s)
        # Legend settings per subplot
        self._legends: Dict[str, pg.LegendItem] = {}
        self._legend_visible: bool = True
        self._legend_pos: str = "top-right"  # preset position key
        self._legend_offset: tuple = (-10, 10)  # (x, y) pixel offset
        self._legend_font_size: int = 9
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.graphics_layout = pg.GraphicsLayoutWidget()
        layout.addWidget(self.graphics_layout)

        self._build_layout()

    def _build_layout(self):
        """Build plot items based on current layout mode."""
        self.graphics_layout.clear()
        self._plots.clear()
        self._legends.clear()

        if self._layout_mode == LAYOUT_SPLIT_WAVE:
            ray_name = self._subplot_names.get('rayleigh', 'Rayleigh')
            love_name = self._subplot_names.get('love', 'Love')
            p_ray = self.graphics_layout.addPlot(
                row=0, col=0,
                axisItems={'bottom': LogFreqAxis(orientation='bottom')},
                title=ray_name,
            )
            p_love = self.graphics_layout.addPlot(
                row=0, col=1,
                axisItems={'bottom': LogFreqAxis(orientation='bottom')},
                title=love_name,
            )
            self._plots['rayleigh'] = p_ray
            self._plots['love'] = p_love
            self._subplot_names.setdefault('rayleigh', 'Rayleigh')
            self._subplot_names.setdefault('love', 'Love')
            for key in ['rayleigh', 'love']:
                self._configure_plot(self._plots[key], key)
            if self._link_y:
                p_love.setYLink(p_ray)
            if self._link_x:
                p_love.setXLink(p_ray)
        elif self._layout_mode == LAYOUT_GRID:
            first_plot = None
            for r in range(self._grid_rows):
                for c in range(self._grid_cols):
                    key = f"cell_{r}_{c}"
                    default_name = f"Subplot ({r+1},{c+1})"
                    name = self._subplot_names.get(key, default_name)
                    self._subplot_names.setdefault(key, default_name)
                    p = self.graphics_layout.addPlot(
                        row=r, col=c,
                        axisItems={'bottom': LogFreqAxis(orientation='bottom')},
                        title=name,
                    )
                    self._plots[key] = p
                    self._configure_plot(p, key)
                    if first_plot is None:
                        first_plot = p
                    else:
                        if self._link_y:
                            p.setYLink(first_plot)
                        if self._link_x:
                            p.setXLink(first_plot)
        else:
            # Single combined plot
            name = self._subplot_names.get('main', '')
            p = self.graphics_layout.addPlot(
                row=0, col=0,
                axisItems={'bottom': LogFreqAxis(orientation='bottom')},
            )
            if name:
                p.setTitle(name)
            self._plots['main'] = p
            self._subplot_names.setdefault('main', '')
            self._configure_plot(p, 'main')

        # Prune stale keys from subplot_names
        stale = [k for k in self._subplot_names if k not in self._plots]
        for k in stale:
            del self._subplot_names[k]

        # Emit layout change so tree panel can update
        self.layout_changed.emit(self.get_subplot_info())
        # Set default active subplot to first
        keys = list(self._plots.keys())
        if keys:
            self._active_subplot = keys[0]

    def _configure_plot(self, plot: pg.PlotItem, subplot_key: str = None):
        """Apply standard configuration to a plot."""
        plot.setLabel('bottom', 'Frequency (Hz)')
        plot.setLabel('left', _VEL_LABELS.get(self._velocity_unit, "Phase Velocity (m/s)"))
        plot.showGrid(x=True, y=True, alpha=0.15)
        for axis_name in ['bottom', 'left']:
            axis = plot.getAxis(axis_name)
            axis.enableAutoSIPrefix(False)
            axis.setStyle(tickFont=pg.QtGui.QFont("Segoe UI", 9))
        plot.setMouseEnabled(x=True, y=True)
        plot.enableAutoRange()
        # Replace default context menu with our own
        plot.setMenuEnabled(False)
        plot.vb.menu = self._build_context_menu(plot)
        # Track clicks to set active subplot
        plot.scene().sigMouseClicked.connect(
            lambda ev, p=plot: self._on_plot_clicked(ev, p)
        )
        # Add legend
        if self._legend_visible and subplot_key:
            legend = plot.addLegend(offset=self._legend_offset)
            legend.setLabelTextSize(f"{self._legend_font_size}pt")
            self._legends[subplot_key] = legend
        elif self._legend_visible:
            legend = plot.addLegend(offset=self._legend_offset)
            legend.setLabelTextSize(f"{self._legend_font_size}pt")
            for key, p in self._plots.items():
                if p is plot:
                    self._legends[key] = legend
                    break

    def _build_context_menu(self, plot: pg.PlotItem):
        """Build a clean context menu for a plot."""
        from PySide6.QtWidgets import QMenu
        menu = QMenu()
        menu.addAction("Fit to Data", lambda p=plot: p.enableAutoRange())
        menu.addSeparator()
        grid_action = menu.addAction("Toggle Grid")
        grid_action.triggered.connect(
            lambda checked, p=plot: p.showGrid(
                x=not p.ctrl.xGridCheck.isChecked(),
                y=not p.ctrl.yGridCheck.isChecked(),
                alpha=0.15,
            )
        )
        menu.addSeparator()
        menu.addAction("Export Canvas Image...", self._on_export_action)
        return menu

    def rebuild(self):
        """Rebuild all plots (e.g. after theme change)."""
        saved_curves = {uid: info['data'] for uid, info in self._curves.items()}
        saved_ensembles = {eid: info['data'] for eid, info in self._ensembles.items()}
        self._curves.clear()
        self._ensembles.clear()
        self._build_layout()
        for uid, curve in saved_curves.items():
            self.add_curve(curve)
        for eid, ens in saved_ensembles.items():
            self.add_ensemble(ens)
        self.auto_range()

    def set_layout_mode(self, mode: str):
        """Switch layout mode and re-plot all curves."""
        if mode == self._layout_mode:
            return
        self._layout_mode = mode
        self.rebuild()

    def set_grid(self, rows: int, cols: int):
        """Set NxM grid layout."""
        self._grid_rows = max(1, rows)
        self._grid_cols = max(1, cols)
        self._layout_mode = LAYOUT_GRID
        self.rebuild()

    def set_link_y(self, linked: bool):
        """Link or unlink Y-axes across subplots."""
        self._link_y = linked
        self.rebuild()

    def set_link_x(self, linked: bool):
        """Link or unlink X-axes across subplots."""
        self._link_x = linked
        self.rebuild()

    def get_subplot_info(self) -> list:
        """Return [(key, name), ...] for all subplots."""
        return [(k, self._subplot_names.get(k, k)) for k in self._plots.keys()]

    def get_subplot_keys(self) -> list:
        """Return list of subplot keys."""
        return list(self._plots.keys())

    def rename_subplot(self, key: str, name: str):
        """Rename a subplot's title."""
        self._subplot_names[key] = name
        if key in self._plots:
            self._plots[key].setTitle(name)

    @property
    def layout_mode(self) -> str:
        return self._layout_mode

    def get_layout_config(self) -> dict:
        """Return complete layout configuration for FigureState."""
        return {
            "layout_mode": self._layout_mode,
            "grid_rows": self._grid_rows,
            "grid_cols": self._grid_cols,
            "link_y": self._link_y,
            "link_x": self._link_x,
            "subplot_names": dict(self._subplot_names),
        }

    # ── Legend management ─────────────────────────────────────────

    _LEGEND_ANCHORS = {
        "top-right":    ((1, 0), (1, 0)),
        "top-left":     ((0, 0), (0, 0)),
        "bottom-right": ((1, 1), (1, 1)),
        "bottom-left":  ((0, 1), (0, 1)),
    }

    def set_legend_visible(self, visible: bool):
        self._legend_visible = visible
        self.rebuild()

    def set_legend_position(self, position: str, offset: tuple = None):
        """Set legend position. position: 'top-right', 'top-left', etc."""
        self._legend_pos = position
        if offset is not None:
            self._legend_offset = offset
        else:
            default_offsets = {
                "top-right": (-10, 10), "top-left": (10, 10),
                "bottom-right": (-10, -10), "bottom-left": (10, -10),
            }
            self._legend_offset = default_offsets.get(position, (-10, 10))
        self.rebuild()

    def set_legend_font_size(self, size: int):
        self._legend_font_size = max(6, min(24, size))
        for legend in self._legends.values():
            legend.setLabelTextSize(f"{self._legend_font_size}pt")

    def get_legend_config(self) -> dict:
        return {
            "visible": self._legend_visible,
            "position": self._legend_pos,
            "offset": self._legend_offset,
            "font_size": self._legend_font_size,
        }

    def _get_plot_for_curve(self, curve: CurveData) -> pg.PlotItem:
        """Return the correct plot item for a curve based on its subplot_key."""
        # Direct match by subplot_key
        if curve.subplot_key in self._plots:
            return self._plots[curve.subplot_key]
        # Fallback for split_wave mode: route by wave type
        if self._layout_mode == LAYOUT_SPLIT_WAVE:
            if curve.wave_type == WaveType.LOVE:
                return self._plots.get('love', list(self._plots.values())[0])
            return self._plots.get('rayleigh', list(self._plots.values())[0])
        # Default: first subplot
        return list(self._plots.values())[0]

    def add_curve(self, curve: CurveData):
        """Add or update a curve on the canvas."""
        if not curve.has_data:
            return

        if curve.uid in self._curves:
            self._remove_plot_items(curve.uid)

        plot = self._get_plot_for_curve(curve)
        color = QColor(curve.color)
        pen = pg.mkPen(color=color, width=curve.line_width)

        freq = curve.frequency
        vel = curve.velocity

        mask = curve.point_mask if curve.point_mask is not None else np.ones(len(freq), dtype=bool)
        freq_vis = freq[mask]
        vf = _VEL_FACTORS.get(self._velocity_unit, 1.0)
        vel_vis = vel[mask] * vf

        # Resample if enabled
        if curve.resample_enabled and len(freq_vis) >= 2:
            n = curve.resample_n_points
            f_min, f_max = freq_vis.min(), freq_vis.max()
            if curve.resample_method == "log" and f_min > 0:
                new_freq = np.logspace(np.log10(f_min), np.log10(f_max), n)
            else:
                new_freq = np.linspace(f_min, f_max, n)
            new_vel = np.interp(new_freq, freq_vis, vel_vis)
            # Interpolate stddev for error bars
            if curve.stddev is not None and len(curve.stddev) == len(freq):
                stddev_masked = curve.stddev[mask]
                new_stddev = np.interp(new_freq, freq_vis, stddev_masked)
            else:
                new_stddev = None
            freq_vis = new_freq
            vel_vis = new_vel
            # stddev_resampled is used below for error bars
            _stddev_for_plot = new_stddev
        else:
            _stddev_for_plot = curve.stddev[mask] if (
                curve.stddev is not None and len(curve.stddev) == len(freq)
            ) else None

        # Apply range-based stddev override
        if curve.stddev_mode == "range" and curve.stddev_ranges and _stddev_for_plot is not None:
            range_stddev = np.copy(_stddev_for_plot)
            for fmin_r, fmax_r, val in curve.stddev_ranges:
                in_range = (freq_vis >= fmin_r) & (freq_vis <= fmax_r)
                range_stddev[in_range] = val
            _stddev_for_plot = range_stddev
        elif curve.stddev_mode == "fixed_logstd" and _stddev_for_plot is not None:
            _stddev_for_plot = np.full(len(freq_vis), curve.fixed_logstd)
        elif curve.stddev_mode == "fixed_cov" and _stddev_for_plot is not None:
            _stddev_for_plot = np.full(len(freq_vis), curve.fixed_cov)

        if len(freq_vis) == 0:
            self._curves[curve.uid] = {
                'data': curve, 'plot': plot,
                'line': None, 'scatter': None, 'error': None,
            }
            return

        with np.errstate(divide='ignore', invalid='ignore'):
            log_freq = np.where(freq_vis > 0, np.log10(freq_vis), -10)

        is_theoretical = curve.curve_type == CurveType.THEORETICAL
        line_item = None
        scatter = None
        error_item = None

        if is_theoretical:
            line_item = plot.plot(
                log_freq, vel_vis, pen=pen, name=curve.display_name
            )
        else:
            if (_stddev_for_plot is not None and len(_stddev_for_plot) == len(freq_vis)
                    and curve.show_error_bars):
                stddev_vis = _stddev_for_plot
                if curve.stddev_type == "logstd":
                    top_err = vel_vis * (np.exp(stddev_vis) - 1)
                    bottom_err = vel_vis * (1 - np.exp(-stddev_vis))
                else:
                    top_err = stddev_vis
                    bottom_err = stddev_vis

                err_color = QColor(curve.color)
                err_color.setAlpha(160)
                error_item = pg.ErrorBarItem(
                    x=log_freq, y=vel_vis,
                    top=top_err, bottom=bottom_err,
                    pen=pg.mkPen(err_color, width=1.2),
                    beam=0.0,
                )
                plot.addItem(error_item)

            vu = _VEL_UNIT_STR.get(self._velocity_unit, "m/s")
            scatter = pg.ScatterPlotItem(
                log_freq, vel_vis,
                pen=pg.mkPen(color, width=1),
                brush=pg.mkBrush(color),
                size=curve.marker_size,
                hoverable=True,
                tip=lambda x, y, data, u=vu: f"f={10**x:.2f} Hz, v={y:.1f} {u}",
                data=[curve.uid] * len(freq_vis),
            )
            scatter.sigClicked.connect(
                lambda pts, ev, uid=curve.uid: self.curve_clicked.emit(uid)
            )
            plot.addItem(scatter)
            # Add to legend
            for key, p in self._plots.items():
                if p is plot and key in self._legends:
                    self._legends[key].addItem(scatter, curve.display_name)
                    break

        self._curves[curve.uid] = {
            'data': curve,
            'plot': plot,
            'line': line_item,
            'scatter': scatter,
            'error': error_item,
        }

    def remove_curve(self, uid: str):
        """Remove a curve from the canvas."""
        if uid in self._curves:
            self._remove_plot_items(uid)
            del self._curves[uid]

    def set_curve_visible(self, uid: str, visible: bool):
        """Toggle curve visibility."""
        if uid not in self._curves:
            return
        items = self._curves[uid]
        if items['line']:
            items['line'].setVisible(visible)
        if items['scatter']:
            items['scatter'].setVisible(visible)
        if items.get('error'):
            items['error'].setVisible(visible)

    def highlight_curve(self, uid: str, selected: bool):
        """Highlight or unhighlight a curve."""
        if uid not in self._curves:
            return
        items = self._curves[uid]
        curve = items['data']
        color = QColor(curve.color)
        if selected:
            width = curve.line_width * 2.5
            if items['scatter']:
                items['scatter'].setSize(curve.marker_size * 1.5)
            if items['line']:
                items['line'].setPen(pg.mkPen(color, width=width))
        else:
            width = curve.line_width
            if items['scatter']:
                items['scatter'].setSize(curve.marker_size)
            if items['line']:
                items['line'].setPen(pg.mkPen(color, width=width))

    def update_curve_style(self, uid: str, curve: CurveData):
        """Update curve visual style by re-adding."""
        if uid in self._curves:
            self.add_curve(curve)

    def add_ensemble(self, ensemble: EnsembleData):
        """Add or update a theoretical ensemble with individually controllable layers.

        Layers (rendered bottom to top):
          envelope  - min/max fill
          percentile - 16/84 percentile band
          individual - spaghetti lines
          median    - bold median line
        """
        if not ensemble.has_data:
            return

        # Find target plot
        plot = self._plots.get(ensemble.subplot_key)
        if plot is None:
            plot = list(self._plots.values())[0] if self._plots else None
        if plot is None:
            return

        # Remove previous items
        self._remove_ensemble_items(ensemble.uid)

        freq = ensemble.freq
        vf = _VEL_FACTORS.get(self._velocity_unit, 1.0)
        with np.errstate(divide="ignore", invalid="ignore"):
            log_freq = np.where(freq > 0, np.log10(freq), -10)

        layers = {}  # layer_name -> list of plot items

        # 1. Envelope fill (lightest, bottom)
        env = ensemble.envelope_layer
        env_items = []
        if ensemble.envelope_min is not None and ensemble.envelope_max is not None:
            env_color = QColor(env.color)
            env_color.setAlpha(env.alpha)
            env_fill = pg.FillBetweenItem(
                pg.PlotDataItem(log_freq, ensemble.envelope_min * vf),
                pg.PlotDataItem(log_freq, ensemble.envelope_max * vf),
                brush=pg.mkBrush(env_color),
            )
            env_fill.setVisible(env.visible)
            plot.addItem(env_fill)
            env_items.append(env_fill)
        layers["envelope"] = env_items

        # 2. Percentile band fill
        pct = ensemble.percentile_layer
        pct_items = []
        if ensemble.p_low is not None and ensemble.p_high is not None:
            pct_color = QColor(pct.color)
            pct_color.setAlpha(pct.alpha)
            pct_fill = pg.FillBetweenItem(
                pg.PlotDataItem(log_freq, ensemble.p_low * vf),
                pg.PlotDataItem(log_freq, ensemble.p_high * vf),
                brush=pg.mkBrush(pct_color),
            )
            pct_fill.setVisible(pct.visible)
            plot.addItem(pct_fill)
            pct_items.append(pct_fill)
        layers["percentile"] = pct_items

        # 3. Individual curves (spaghetti)
        ind = ensemble.individual_layer
        ind_items = []
        if (ensemble.individual_freqs is not None
                and ensemble.individual_vels is not None):
            ind_color = QColor(ind.color)
            ind_color.setAlpha(ind.alpha)
            pen = pg.mkPen(ind_color, width=ind.line_width)
            count = min(len(ensemble.individual_freqs), ensemble.max_individual)
            for i in range(count):
                f = ensemble.individual_freqs[i]
                v = ensemble.individual_vels[i] * vf
                with np.errstate(divide="ignore", invalid="ignore"):
                    lf = np.where(f > 0, np.log10(f), -10)
                line = pg.PlotDataItem(lf, v, pen=pen)
                line.setVisible(ind.visible)
                plot.addItem(line)
                ind_items.append(line)
        layers["individual"] = ind_items

        # 4. Median line (on top, bold)
        med = ensemble.median_layer
        med_items = []
        if ensemble.median is not None:
            med_pen = pg.mkPen(QColor(med.color), width=med.line_width)
            med_line = plot.plot(
                log_freq, ensemble.median * vf, pen=med_pen,
                name=ensemble.display_name,
            )
            med_line.setVisible(med.visible)
            med_items.append(med_line)
        layers["median"] = med_items

        self._ensembles[ensemble.uid] = {
            "plot": plot,
            "layers": layers,
            "data": ensemble,
        }

    def set_ensemble_layer_visible(self, uid: str, layer_name: str, visible: bool):
        """Toggle visibility of a specific ensemble layer."""
        info = self._ensembles.get(uid)
        if not info:
            return
        items = info["layers"].get(layer_name, [])
        for item in items:
            item.setVisible(visible)

    def update_ensemble(self, ensemble: EnsembleData):
        """Re-render an ensemble (call after changing layer styles)."""
        self.add_ensemble(ensemble)

    def remove_ensemble(self, uid: str):
        """Remove an ensemble overlay."""
        self._remove_ensemble_items(uid)
        self._ensembles.pop(uid, None)

    def _remove_ensemble_items(self, uid: str):
        info = self._ensembles.get(uid)
        if not info:
            return
        plot = info["plot"]
        for layer_items in info["layers"].values():
            for item in layer_items:
                try:
                    plot.removeItem(item)
                except Exception:
                    pass

    def clear_all(self):
        """Remove all curves."""
        for uid in list(self._curves.keys()):
            self._remove_plot_items(uid)
        self._curves.clear()

    def auto_range(self):
        """Fit view to all data."""
        for plot in self._plots.values():
            plot.enableAutoRange()

    def _remove_plot_items(self, uid: str):
        items = self._curves.get(uid)
        if not items:
            return
        plot = items.get('plot')
        if not plot:
            return
        if items.get('line'):
            plot.removeItem(items['line'])
        if items.get('scatter'):
            plot.removeItem(items['scatter'])
        if items.get('error'):
            plot.removeItem(items['error'])

    @property
    def active_subplot(self) -> str:
        """The currently active/selected subplot key."""
        if self._active_subplot and self._active_subplot in self._plots:
            return self._active_subplot
        keys = list(self._plots.keys())
        return keys[0] if keys else "main"

    @property
    def velocity_unit(self) -> str:
        return self._velocity_unit

    def set_velocity_unit(self, unit: str):
        """Set velocity display unit ('metric' or 'imperial') and re-render."""
        if unit == self._velocity_unit:
            return
        self._velocity_unit = unit
        self.rebuild()

    def export_canvas(self, filepath: str, dpi: int = 150):
        """Export the entire canvas (all subplots) as an image."""
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
        """Export dialog: ask DPI then save file."""
        dpi, ok = QInputDialog.getInt(
            self, "Export DPI", "Resolution (DPI):", 150, 72, 600, 1
        )
        if not ok:
            return
        filepath, _ = QFileDialog.getSaveFileName(
            self, "Export Canvas Image", "",
            "PNG (*.png);;JPEG (*.jpg);;TIFF (*.tiff);;All files (*.*)"
        )
        if filepath:
            self.export_canvas(filepath, dpi)

    def _on_plot_clicked(self, event, clicked_plot):
        """Handle click on a subplot — set it as active and check for scatter hits."""
        # Set this plot as active
        for key, plot in self._plots.items():
            if plot is clicked_plot:
                self._active_subplot = key
                # Visual feedback: subtle border highlight
                break

        # Check for scatter clicks (curve selection)
        pos = event.scenePos()
        items_at = self.graphics_layout.scene().items(pos)
        hit_scatter = any(
            isinstance(item, pg.ScatterPlotItem) for item in items_at
        )
        if not hit_scatter:
            pass
