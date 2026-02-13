"""Subplot management: move, rename, activate, layout changes."""
from geo_figure.core.models import WaveType
from geo_figure.core.subplot_types import (
    subplot_accepts, auto_assign_type, rejection_message,
    KIND_CURVE, KIND_ENSEMBLE, KIND_VS_PROFILE, KIND_SOIL_PROFILE,
    UNSET,
)


def _validate_move(self, new_key: str, data_kind: str) -> bool:
    """Check if data_kind can be placed on new_key. Shows error if not."""
    canvas = self.sheet_tabs.get_current_canvas()
    stype = canvas._subplot_types.get(new_key, UNSET)
    if not subplot_accepts(stype, data_kind):
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.warning(
            self, "Incompatible Subplot",
            rejection_message(stype, data_kind),
        )
        return False
    new_type = auto_assign_type(stype, data_kind)
    if new_type != stype:
        canvas.set_subplot_type(new_key, new_type)
        self._rebuild_tree()
    return True


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
        if not _validate_move(self, new_key, KIND_CURVE):
            return
        curve.subplot_key = new_key
        canvas = self.sheet_tabs.get_current_canvas()
        canvas.remove_curve(uid)
        canvas.add_curve(curve)
        canvas.auto_range()
        self.curve_tree.tree.blockSignals(True)
        self.curve_tree.remove_curve(uid)
        self.curve_tree.add_curve(curve)
        self.curve_tree.tree.blockSignals(False)
        self.log_panel.log_info(f"Moved '{curve.display_name}' to subplot '{new_key}'")

    def _on_subplot_activated(self, key: str):
        """Set the active subplot when user clicks a subplot root in the tree."""
        canvas = self.sheet_tabs.get_current_canvas()
        canvas._active_subplot = key
        self.curve_tree._active_subplot_key = key
        name = canvas._subplot_names.get(key, key)
        self.status_bar.showMessage(f"Active subplot: {name}")

    def _on_ensemble_subplot_changed(self, uid: str, new_key: str):
        """Move an ensemble (with all layers) to a different subplot."""
        ens = self._ensembles.get(uid)
        if not ens:
            return
        if ens.subplot_key == new_key:
            return
        if not _validate_move(self, new_key, KIND_ENSEMBLE):
            return
        ens.subplot_key = new_key
        canvas = self.sheet_tabs.get_current_canvas()
        canvas.remove_ensemble(uid)
        canvas.add_ensemble(ens)
        canvas.auto_range()
        self.curve_tree.tree.blockSignals(True)
        self.curve_tree.remove_ensemble(uid)
        self.curve_tree.add_ensemble(ens)
        self.curve_tree.tree.blockSignals(False)
        self.log_panel.log_info(
            f"Moved '{ens.display_name}' to subplot '{new_key}'"
        )

    def _on_vs_profile_subplot_changed(self, uid: str, new_key: str):
        """Move a Vs profile to a different subplot."""
        prof = self._vs_profiles.get(uid)
        if not prof:
            return
        if prof.subplot_key == new_key:
            return
        if not _validate_move(self, new_key, KIND_VS_PROFILE):
            return
        prof.subplot_key = new_key
        canvas = self.sheet_tabs.get_current_canvas()
        canvas.remove_vs_profile(uid)
        canvas.add_vs_profile(prof)
        canvas.auto_range()
        self.curve_tree.tree.blockSignals(True)
        self.curve_tree.remove_vs_profile(uid)
        self.curve_tree.add_vs_profile(prof)
        self.curve_tree.tree.blockSignals(False)
        self.log_panel.log_info(
            f"Moved '{prof.display_name}' to subplot '{new_key}'"
        )

    def _on_soil_profile_subplot_changed(self, uid: str, new_key: str):
        """Move a soil profile (or group) to a different subplot."""
        if not _validate_move(self, new_key, KIND_SOIL_PROFILE):
            return
        sd = self._sheet_data.get(self._current_sheet_idx, {})
        canvas = self.sheet_tabs.get_current_canvas()

        # Check if uid is a group
        groups = sd.get("soil_profile_groups", {})
        group = groups.get(uid)
        if group is not None:
            if group.subplot_key == new_key:
                return
            group.subplot_key = new_key
            self.curve_tree.tree.blockSignals(True)
            for prof in group.profiles:
                prof.subplot_key = new_key
                canvas.remove_soil_profile(prof.uid)
                canvas.add_soil_profile(prof)
            self.curve_tree.remove_soil_profile(uid)
            self.curve_tree.add_soil_profile_group(group)
            self.curve_tree.tree.blockSignals(False)
            canvas.auto_range()
            self.log_panel.log_info(
                f"Moved group '{group.display_name}' to subplot '{new_key}'"
            )
            return

        # Individual profile
        sp_dict = sd.get("soil_profiles", {})
        profile = sp_dict.get(uid)
        if not profile:
            return
        if profile.subplot_key == new_key:
            return

        # Remove from old group if it was in one
        old_group = None
        for grp in groups.values():
            for i, prof in enumerate(grp.profiles):
                if prof.uid == uid:
                    old_group = grp
                    grp.profiles.pop(i)
                    break
            if old_group:
                break

        profile.subplot_key = new_key
        canvas.remove_soil_profile(uid)
        canvas.add_soil_profile(profile)
        canvas.auto_range()

        self.curve_tree.tree.blockSignals(True)
        if old_group:
            self.curve_tree.remove_soil_profile(old_group.uid)
            if old_group.profiles:
                self.curve_tree.add_soil_profile_group(old_group)
            else:
                groups.pop(old_group.uid, None)
        else:
            self.curve_tree.remove_soil_profile(uid)
        self.curve_tree.add_soil_profile(profile)
        self.curve_tree.tree.blockSignals(False)
        self.log_panel.log_info(
            f"Moved '{profile.display_name}' to subplot '{new_key}'"
        )

    def _on_subplot_renamed(self, key: str, new_name: str):
        """Rename a subplot on the canvas and refresh tree."""
        canvas = self.sheet_tabs.get_current_canvas()
        canvas.rename_subplot(key, new_name)
        self._rebuild_tree()
        self.log_panel.log_info(f"Renamed subplot to '{new_name}'")

    def _on_subplot_clear_from_tree(self, key: str):
        """Clear data from a subplot via data panel context menu."""
        canvas = self.sheet_tabs.get_current_canvas()
        canvas.clear_subplot(key)

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

        # Migrate soil profiles
        sd = self._sheet_data.get(self._current_sheet_idx, {})
        for uid, sp in sd.get('soil_profiles', {}).items():
            if sp.subplot_key not in valid_keys:
                sp.subplot_key = first_key

        self._rebuild_tree()

        # Sync column ratio UI
        cols = canvas._grid_cols if layout_mode == "grid" else 0
        ratios = list(canvas._grid_col_ratios)
        self.sheet_panel.set_grid_col_ratios(cols, ratios)

        # Show Vs Profile Layout if any cell is depth-based
        from geo_figure.core.subplot_types import VS_EXTRACT, PROFILE, SOIL_PROFILE
        has_vs = any(
            t in (VS_EXTRACT, PROFILE, SOIL_PROFILE)
            for t in canvas._subplot_types.values()
        ) or layout_mode == "vs_profile"
        self.sheet_panel.set_vs_visible(has_vs)
        if has_vs:
            self.sheet_panel.set_vs_ratios(*canvas._vs_internal_ratios)
