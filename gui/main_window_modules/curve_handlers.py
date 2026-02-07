"""Curve selection, visibility, and CRUD handlers."""


class CurveHandlersMixin:
    """Handlers for curve selection, visibility, update, and removal."""

    def _on_curve_selected(self, uid: str):
        """Handle curve selection from tree or canvas."""
        # Unhighlight previous
        if self._selected_uid and self._selected_uid in self._curves:
            canvas = self.sheet_tabs.get_current_canvas()
            canvas.highlight_curve(self._selected_uid, False)

        self._selected_uid = uid
        curve = self._curves.get(uid)
        if curve:
            self.properties.show_curve(uid, curve)
            canvas = self.sheet_tabs.get_current_canvas()
            canvas.highlight_curve(uid, True)
            self.curve_tree.select_curve(uid)
            self.status_bar.showMessage(
                f"Selected: {curve.display_name} | {curve.n_points} pts | "
                f"{curve.freq_min:.2f}\u2013{curve.freq_max:.2f} Hz"
            )

    def _on_curve_visibility(self, uid: str, visible: bool):
        """Toggle curve visibility on canvas."""
        if uid in self._curves:
            self._curves[uid].visible = visible
            canvas = self.sheet_tabs.get_current_canvas()
            canvas.set_curve_visible(uid, visible)

    def _on_point_visibility(self, uid: str, index: int, visible: bool):
        """Toggle individual point visibility and re-plot."""
        curve = self._curves.get(uid)
        if curve and curve.point_mask is not None:
            curve.point_mask[index] = visible
            canvas = self.sheet_tabs.get_current_canvas()
            canvas.add_curve(curve)

    def _on_curve_updated(self, uid: str, curve):
        """Handle curve property changes from the properties panel."""
        old_curve = self._curves.get(uid)
        type_changed = (
            old_curve and old_curve.curve_type != curve.curve_type
        )
        self._curves[uid] = curve
        canvas = self.sheet_tabs.get_current_canvas()
        canvas.update_curve_style(uid, curve)
        if type_changed:
            # Re-categorize in tree (remove + re-add)
            self.curve_tree.remove_curve(uid)
            self.curve_tree.add_curve(curve)
        else:
            self.curve_tree.update_curve(uid, curve)

    def _on_remove_curve(self, uid: str):
        """Remove a curve."""
        if uid in self._curves:
            del self._curves[uid]
            self.curve_tree.remove_curve(uid)
            canvas = self.sheet_tabs.get_current_canvas()
            canvas.remove_curve(uid)
            if self._selected_uid == uid:
                self._selected_uid = None
                self.properties.clear()
            self.log_panel.log_info("Curve removed")
