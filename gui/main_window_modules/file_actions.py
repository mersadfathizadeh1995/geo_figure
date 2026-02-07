"""File I/O actions: open curves, load target."""
from pathlib import Path

from PySide6.QtWidgets import QFileDialog

from geo_figure.core.models import CurveType
from geo_figure.io.curve_reader import detect_and_read, read_theoretical_dc_txt


class FileActionsMixin:
    """File loading actions."""

    def _on_open_file(self):
        """Open one or more dispersion curve files (auto-detect format)."""
        files, _ = QFileDialog.getOpenFileNames(
            self, "Open Dispersion Curve Files",
            "",
            "All supported (*.txt *.csv *.target);;Text files (*.txt);;"
            "CSV files (*.csv);;Target files (*.target);;All files (*.*)"
        )
        if not files:
            return

        canvas = self.sheet_tabs.get_current_canvas()
        for filepath in files:
            try:
                curves = detect_and_read(filepath)
                for curve in curves:
                    if curve.curve_type != CurveType.THEORETICAL:
                        curve.color = self.curve_tree.get_next_color()
                    self._add_curve(curve, canvas)
                n = len(curves)
                fname = Path(filepath).name
                self.log_panel.log_success(
                    f"Loaded {n} curve(s) from {fname}"
                )
            except Exception as e:
                self.log_panel.log_error(f"Failed to load {filepath}: {e}")

        canvas.auto_range()

    def _on_open_theoretical(self):
        """Open a theoretical DC file (gpdc output format)."""
        filepath, _ = QFileDialog.getOpenFileName(
            self, "Open Theoretical DC File",
            "",
            "Text files (*.txt);;All files (*.*)"
        )
        if not filepath:
            return

        canvas = self.sheet_tabs.get_current_canvas()
        try:
            curves = read_theoretical_dc_txt(filepath)
            for curve in curves:
                self._add_curve(curve, canvas)
            self.log_panel.log_success(
                f"Loaded {len(curves)} theoretical models from {Path(filepath).name}"
            )
            canvas.auto_range()
        except Exception as e:
            self.log_panel.log_error(f"Failed to load theoretical DC: {e}")

    def _on_load_target(self):
        """Load a Dinver .target file."""
        filepath, _ = QFileDialog.getOpenFileName(
            self, "Load Target File",
            "",
            "Target files (*.target);;All files (*.*)"
        )
        if not filepath:
            return
        canvas = self.sheet_tabs.get_current_canvas()
        try:
            from geo_figure.io.target_reader import read_target_file
            curves, summary = read_target_file(filepath)
            for curve in curves:
                curve.color = self.curve_tree.get_next_color()
                self._add_curve(curve, canvas)
            n = summary['total_curves']
            self.log_panel.log_success(
                f"Loaded {n} curve(s) from target: "
                f"{summary['rayleigh_count']} Rayleigh, {summary['love_count']} Love"
            )
            canvas.auto_range()
        except Exception as e:
            self.log_panel.log_error(f"Failed to load target: {e}")

    def _on_export_csv(self):
        """Export current sheet data (curves + ensembles) as CSV files."""
        import numpy as np

        project_csv = getattr(self, '_project_dir', None)
        default_dir = str(project_csv / "csv") if project_csv else ""

        # Curves
        curves = self._curves
        ensembles = self._ensembles

        if not curves and not ensembles:
            self.log_panel.log_info("Nothing to export.")
            return

        save_dir = QFileDialog.getExistingDirectory(
            self, "Select CSV Export Directory", default_dir
        )
        if not save_dir:
            return

        count = 0
        save_path = Path(save_dir)

        # Export experimental curves
        for uid, curve in curves.items():
            if not curve.has_data:
                continue
            name = curve.display_name.replace(" ", "_").replace("/", "_")
            mask = curve.point_mask if curve.point_mask is not None else np.ones(len(curve.frequency), dtype=bool)
            freq = curve.frequency[mask]
            vel = curve.velocity[mask]
            lines = ["Frequency_Hz,Phase_Velocity_mps"]
            if curve.stddev is not None and len(curve.stddev) == len(curve.frequency):
                lines[0] += ",StdDev"
                std = curve.stddev[mask]
                for f, v, s in zip(freq, vel, std):
                    lines.append(f"{f:.6f},{v:.4f},{s:.6f}")
            else:
                for f, v in zip(freq, vel):
                    lines.append(f"{f:.6f},{v:.4f}")
            fpath = save_path / f"{name}.csv"
            fpath.write_text("\n".join(lines), encoding="utf-8")
            count += 1

        # Export ensemble statistics
        for uid, ens in ensembles.items():
            if not ens.has_data:
                continue
            name = ens.display_name.replace(" ", "_").replace("/", "_")
            # Median + percentiles
            header = "Frequency_Hz,Median_mps"
            cols = [ens.freq, ens.median]
            if ens.p_low is not None:
                header += ",P16_mps"
                cols.append(ens.p_low)
            if ens.p_high is not None:
                header += ",P84_mps"
                cols.append(ens.p_high)
            if ens.envelope_min is not None:
                header += ",Min_mps"
                cols.append(ens.envelope_min)
            if ens.envelope_max is not None:
                header += ",Max_mps"
                cols.append(ens.envelope_max)
            if ens.sigma_ln is not None:
                header += ",Sigma_ln"
                cols.append(ens.sigma_ln)
            lines = [header]
            for i in range(len(ens.freq)):
                row = ",".join(f"{c[i]:.6f}" for c in cols)
                lines.append(row)
            fpath = save_path / f"{name}_stats.csv"
            fpath.write_text("\n".join(lines), encoding="utf-8")
            count += 1

        self.log_panel.log_success(f"Exported {count} CSV file(s) to {save_dir}")
