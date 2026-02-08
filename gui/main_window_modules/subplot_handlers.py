"""Subplot management: move, rename, activate, layout changes."""
from geo_figure.core.models import WaveType


class SubplotHandlersMixin:
    """Handlers for subplot operations."""

    def _on_curve_subplot_changed(self, uid: str, new_key: str):
        """Move a curve to a different subplot."""
        curve = self._curves.get(uid)
        if not curve:
            return
        old_key = curve.subplot_key
        if old_key == new_key:
            return
        curve.subplot_key = new_key
        # Re-plot: remove from old subplot, add to new
        canvas = self.sheet_tabs.get_current_canvas()
        canvas.remove_curve(uid)
        canvas.add_curve(curve)
        canvas.auto_range()
        # Rebuild tree (block signals to prevent visibility toggle during removal)
        self.curve_tree.tree.blockSignals(True)
        self.curve_tree.remove_curve(uid)
        self.curve_tree.add_curve(curve)
        self.curve_tree.tree.blockSignals(False)
        self.log_panel.log_info(f"Moved '{curve.display_name}' to subplot '{new_key}'")

    def _on_subplot_activated(self, key: str):
        """Set the active subplot when user clicks a subplot root in the tree."""
        canvas = self.sheet_tabs.get_current_canvas()
        canvas._active_subplot = key
        name = canvas._subplot_names.get(key, key)
        self.status_bar.showMessage(f"Active subplot: {name}")

    def _on_ensemble_subplot_changed(self, uid: str, new_key: str):
        """Move an ensemble (with all layers) to a different subplot."""
        ens = self._ensembles.get(uid)
        if not ens:
            return
        if ens.subplot_key == new_key:
            return
        ens.subplot_key = new_key
        canvas = self.sheet_tabs.get_current_canvas()
        canvas.remove_ensemble(uid)
        canvas.add_ensemble(ens)
        canvas.auto_range()
        # Rebuild tree items (block signals to avoid toggle side-effects)
        self.curve_tree.tree.blockSignals(True)
        self.curve_tree.remove_ensemble(uid)
        self.curve_tree.add_ensemble(ens)
        self.curve_tree.tree.blockSignals(False)
        self.log_panel.log_info(
            f"Moved '{ens.display_name}' to subplot '{new_key}'"
        )

    def _on_subplot_renamed(self, key: str, new_name: str):
        """Rename a subplot on the canvas and refresh tree."""
        canvas = self.sheet_tabs.get_current_canvas()
        canvas.rename_subplot(key, new_name)
        self._rebuild_tree()
        self.log_panel.log_info(f"Renamed subplot to '{new_name}'")

    def _on_layout_structure_changed(self, subplot_info: list):
        """Canvas layout changed -- migrate curves and update tree."""
        valid_keys = {k for k, _ in subplot_info}
        first_key = subplot_info[0][0] if subplot_info else "main"

        canvas = self.sheet_tabs.get_current_canvas()
        layout_mode = canvas.layout_mode

        for uid, curve in self._curves.items():
            if curve.subplot_key not in valid_keys:
                if layout_mode == "split_wave":
                    curve.subplot_key = (
                        "love" if curve.wave_type == WaveType.LOVE else "rayleigh"
                    )
                else:
                    curve.subplot_key = first_key

        for uid, ens in self._ensembles.items():
            if ens.subplot_key not in valid_keys:
                ens.subplot_key = first_key

        self._rebuild_tree()

        # Sync column ratio UI
        cols = canvas._grid_cols if layout_mode == "grid" else 0
        ratios = list(canvas._grid_col_ratios)
        self.sheet_panel.set_grid_col_ratios(cols, ratios)

        # Show Vs Profile Layout if any cell is vs_profile
        has_vs = any(
            t == "vs_profile" for t in canvas._subplot_types.values()
        ) or layout_mode == "vs_profile"
        self.sheet_panel.set_vs_visible(has_vs)
        if has_vs:
            self.sheet_panel.set_vs_ratios(*canvas._vs_internal_ratios)
