"""Ensemble rendering: add, remove, update, layer visibility."""
import numpy as np
import pyqtgraph as pg
from PySide6.QtGui import QColor

from geo_figure.core.models import EnsembleData
from .constants import VEL_FACTORS


def add_ensemble(canvas, ensemble: EnsembleData):
    """Add or update a theoretical ensemble with controllable layers."""
    if not ensemble.has_data:
        return

    plot = canvas._plots.get(ensemble.subplot_key)
    if plot is None:
        plot = list(canvas._plots.values())[0] if canvas._plots else None
    if plot is None:
        return

    remove_ensemble_items(canvas, ensemble.uid)

    freq = ensemble.freq
    vf = VEL_FACTORS.get(canvas._velocity_unit, 1.0)
    with np.errstate(divide="ignore", invalid="ignore"):
        log_freq = np.where(freq > 0, np.log10(freq), -10)

    layers = {}

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
        env_label = env.legend_label or "Theoretical Range"
        env_ghost = pg.PlotDataItem(
            [], [], pen=pg.mkPen(QColor(env.color), width=6),
            name=env_label,
        )
        env_ghost.setVisible(env.visible)
        plot.addItem(env_ghost)
        env_items.append(env_ghost)
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
        pct_label = pct.legend_label or "16-84 Percentile"
        pct_ghost = pg.PlotDataItem(
            [], [], pen=pg.mkPen(QColor(pct.color), width=6),
            name=pct_label,
        )
        pct_ghost.setVisible(pct.visible)
        plot.addItem(pct_ghost)
        pct_items.append(pct_ghost)
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
        n_total = len(ensemble.individual_freqs)
        ind_label = ind.legend_label or f"{n_total} Profiles"
        ind_ghost = pg.PlotDataItem(
            [], [], pen=pg.mkPen(QColor(ind.color), width=ind.line_width),
            name=ind_label,
        )
        ind_ghost.setVisible(ind.visible)
        plot.addItem(ind_ghost)
        ind_items.append(ind_ghost)
    layers["individual"] = ind_items

    # 4. Median line (on top, bold)
    med = ensemble.median_layer
    med_items = []
    if ensemble.median is not None:
        med_pen = pg.mkPen(QColor(med.color), width=med.line_width)
        med_label = med.legend_label or "Median"
        med_line = plot.plot(
            log_freq, ensemble.median * vf, pen=med_pen,
            name=med_label,
        )
        med_line.setVisible(med.visible)
        med_items.append(med_line)
    layers["median"] = med_items

    canvas._ensembles[ensemble.uid] = {
        "plot": plot,
        "layers": layers,
        "data": ensemble,
    }


def set_ensemble_layer_visible(canvas, uid: str, layer_name: str,
                                visible: bool):
    """Toggle visibility of a specific ensemble layer."""
    info = canvas._ensembles.get(uid)
    if not info:
        return
    items = info["layers"].get(layer_name, [])
    for item in items:
        item.setVisible(visible)
    plot = info.get("plot")
    if plot:
        plot.vb.updateAutoRange()


def remove_ensemble(canvas, uid: str):
    """Remove an ensemble overlay."""
    remove_ensemble_items(canvas, uid)
    canvas._ensembles.pop(uid, None)


def remove_ensemble_items(canvas, uid: str):
    """Remove all plot items for an ensemble."""
    info = canvas._ensembles.get(uid)
    if not info:
        return
    plot = info["plot"]
    for layer_items in info["layers"].values():
        for item in layer_items:
            try:
                plot.removeItem(item)
            except Exception:
                pass
