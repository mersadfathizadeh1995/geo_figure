"""Canvas layout and view actions."""
from PySide6.QtWidgets import QInputDialog


class LayoutActionsMixin:
    """Layout-related actions: fit, new sheet, grid, link axes."""

    def _on_fit_to_data(self):
        canvas = self.sheet_tabs.get_current_canvas()
        canvas.auto_range()

    def _on_new_sheet(self):
        n = self.sheet_tabs.count() + 1
        self.sheet_tabs.add_sheet(f"Sheet {n}")

    def _set_layout(self, mode: str):
        """Switch canvas layout mode."""
        canvas = self.sheet_tabs.get_current_canvas()
        canvas.set_layout_mode(mode)
        self._layout_combined.setChecked(mode == "combined")
        self._layout_split.setChecked(mode == "split_wave")
        self.log_panel.log_info(
            f"Layout: {'Combined' if mode == 'combined' else 'Split (Rayleigh | Love)'}"
        )

    def _on_custom_grid(self):
        """Prompt for rows x columns grid layout."""
        text, ok = QInputDialog.getText(
            self, "Custom Grid Layout",
            "Enter rows x columns (e.g. 2x2):",
            text="1x2"
        )
        if ok and text:
            try:
                parts = text.lower().replace(',', 'x').split('x')
                rows, cols = int(parts[0].strip()), int(parts[1].strip())
                canvas = self.sheet_tabs.get_current_canvas()
                canvas.set_grid(rows, cols)
                self._layout_combined.setChecked(False)
                self._layout_split.setChecked(False)
                self.log_panel.log_info(f"Layout: {rows}x{cols} grid")
            except (ValueError, IndexError):
                self.log_panel.log_error("Invalid grid format. Use NxM (e.g. 2x2)")

    def _on_toggle_link_y(self):
        """Toggle Y-axis linking across subplots."""
        canvas = self.sheet_tabs.get_current_canvas()
        linked = self._link_y_action.isChecked()
        canvas.set_link_y(linked)
        self.log_panel.log_info(
            f"Y-axes {'linked' if linked else 'independent'}"
        )

    def _on_toggle_link_x(self):
        """Toggle X-axis linking across subplots."""
        canvas = self.sheet_tabs.get_current_canvas()
        linked = self._link_x_action.isChecked()
        canvas.set_link_x(linked)
        self.log_panel.log_info(
            f"X-axes {'linked' if linked else 'independent'}"
        )

    def _on_legend_changed(self, config: dict):
        """Apply legend settings to the current canvas."""
        canvas = self.sheet_tabs.get_current_canvas()
        canvas.set_legend_visible(config["visible"])
        canvas.set_legend_position(config["position"], config["offset"])
        canvas.set_legend_font_size(config["font_size"])
