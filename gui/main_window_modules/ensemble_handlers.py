"""Ensemble / DC Compare handlers."""
import numpy as np
from geo_figure.core.models import WaveType, EnsembleData


class EnsembleHandlersMixin:
    """Handlers for DC Compare extraction and ensemble management."""

    def _on_dc_compare(self):
        """Open DC Compare dialog to extract theoretical curves from .report."""
        from geo_figure.gui.dialogs.dc_compare_dialog import DCCompareDialog
        dlg = DCCompareDialog(self)
        dlg.extraction_complete.connect(self._on_extraction_complete)
        dlg.exec()

    def _on_extraction_complete(self, results: dict):
        """Handle completed DC Compare extraction -- create EnsembleData with layers."""
        from geo_figure.io.report_reader import compute_ensemble_statistics
        results.pop("__include_individual", False)
        canvas = self.sheet_tabs.get_current_canvas()
        target_key = canvas.active_subplot

        for wave_key, parsed in results.items():
            n_profiles = parsed.get("n_profiles", 0)
            modes = parsed.get("modes", {0})
            wave_type_str = parsed.get("wave_type", "Rayleigh")
            wt = WaveType.LOVE if "love" in wave_key else WaveType.RAYLEIGH

            for mode in sorted(modes):
                try:
                    stats = compute_ensemble_statistics(parsed, mode=mode)
                except ValueError as e:
                    self.log_panel.log_error(
                        f"Stats failed for {wave_key} M{mode}: {e}"
                    )
                    continue

                mode_label = f" M{mode}" if mode > 0 else ""
                ens = EnsembleData.from_stats(
                    stats, parsed=parsed,
                    name=f"Theoretical {wave_type_str}{mode_label}",
                    wave_type=wt,
                    mode=mode,
                    subplot_key=target_key,
                )

                # Store and render
                self._ensembles[ens.uid] = ens
                canvas.add_ensemble(ens)
                self.curve_tree.add_ensemble(ens)
                self._save_ensemble_temp(ens)

                # Save theoretical CSV to project dir
                self._save_ensemble_csv(ens)

                self.log_panel.log_success(
                    f"DC Compare: {wave_type_str}{mode_label} -- "
                    f"{n_profiles} profiles, median + percentile bands"
                )

        canvas.auto_range()

    def _save_ensemble_csv(self, ens: EnsembleData):
        """Save ensemble statistics CSV in the project theoretical/ dir."""
        from pathlib import Path
        project_dir = getattr(self, '_project_dir', None)
        if project_dir is None:
            return
        theo_dir = Path(project_dir) / "theoretical"
        theo_dir.mkdir(parents=True, exist_ok=True)
        name = ens.display_name.replace(" ", "_").replace("/", "_")
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
        fpath = theo_dir / f"{name}_stats.csv"
        fpath.write_text("\n".join(lines), encoding="utf-8")
        self.log_panel.log_info(f"Saved: {fpath.name}")

    def _on_new_dc_compare_sheet(self):
        """Create a new sheet pre-configured for DC Compare work."""
        from geo_figure.gui.canvas.plot_canvas import LAYOUT_COMBINED
        idx = self.sheet_tabs.count()
        name = f"DC Compare {idx}"
        canvas = self.sheet_tabs.add_sheet(name)
        new_idx = self.sheet_tabs.indexOf(canvas)
        self.sheet_tabs.setCurrentIndex(new_idx)
        self._ensure_sheet_data(new_idx)
        canvas.set_layout_mode(LAYOUT_COMBINED)
        self.log_panel.log_info("Created DC Compare sheet")

    def _on_compute_misfit(self):
        """Compute per-frequency misfit between experimental curve and ensemble median."""
        from PySide6.QtWidgets import QDialog, QVBoxLayout, QComboBox, QDialogButtonBox, QFormLayout, QLabel

        # Collect experimental curves and ensembles on current sheet
        exp_curves = {uid: c for uid, c in self._curves.items()
                      if c.has_data and c.curve_type.value != "Theoretical"}
        ens_list = {uid: e for uid, e in self._ensembles.items() if e.has_data}

        if not exp_curves or not ens_list:
            self.log_panel.log_info("Need at least one experimental curve and one ensemble for misfit.")
            return

        # Simple dialog to pick which pair
        dlg = QDialog(self)
        dlg.setWindowTitle("Compute Misfit Residual")
        dlg.setMinimumWidth(400)
        layout = QVBoxLayout(dlg)

        form = QFormLayout()
        exp_combo = QComboBox()
        for uid, c in exp_curves.items():
            exp_combo.addItem(c.display_name, uid)
        form.addRow("Experimental:", exp_combo)

        ens_combo = QComboBox()
        for uid, e in ens_list.items():
            ens_combo.addItem(e.display_name, uid)
        form.addRow("Theoretical:", ens_combo)

        layout.addLayout(form)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)
        layout.addWidget(btns)

        if not dlg.exec():
            return

        exp_uid = exp_combo.currentData()
        ens_uid = ens_combo.currentData()
        curve = exp_curves[exp_uid]
        ens = ens_list[ens_uid]

        # Compute misfit: interpolate ensemble median to experimental frequencies
        mask = curve.point_mask if curve.point_mask is not None else np.ones(len(curve.frequency), dtype=bool)
        exp_freq = curve.frequency[mask]
        exp_vel = curve.velocity[mask]

        # Interpolate median to exp frequencies
        sort_idx = np.argsort(ens.freq)
        ens_freq_sorted = ens.freq[sort_idx]
        ens_med_sorted = ens.median[sort_idx]
        theo_vel_at_exp = np.interp(exp_freq, ens_freq_sorted, ens_med_sorted)

        # Relative residual (%)
        residual_pct = (exp_vel - theo_vel_at_exp) / theo_vel_at_exp * 100.0
        rms_pct = np.sqrt(np.mean(residual_pct ** 2))
        mean_abs_pct = np.mean(np.abs(residual_pct))

        # Save misfit CSV
        from pathlib import Path
        project_dir = getattr(self, '_project_dir', None)
        if project_dir:
            csv_dir = Path(project_dir) / "csv"
            csv_dir.mkdir(parents=True, exist_ok=True)
            ename = curve.display_name.replace(" ", "_")
            tname = ens.display_name.replace(" ", "_")
            lines = ["Frequency_Hz,Exp_Vel_mps,Theo_Vel_mps,Residual_pct"]
            for f, ev, tv, r in zip(exp_freq, exp_vel, theo_vel_at_exp, residual_pct):
                lines.append(f"{f:.6f},{ev:.4f},{tv:.4f},{r:.4f}")
            fpath = csv_dir / f"misfit_{ename}_vs_{tname}.csv"
            fpath.write_text("\n".join(lines), encoding="utf-8")
            self.log_panel.log_info(f"Saved: {fpath.name}")

        self.log_panel.log_success(
            f"Misfit: {curve.display_name} vs {ens.display_name} | "
            f"RMS={rms_pct:.2f}% | Mean|res|={mean_abs_pct:.2f}%"
        )

    def _on_ensemble_selected(self, uid: str):
        """Handle ensemble selection from tree."""
        ens = self._ensembles.get(uid)
        if ens:
            self.properties.show_ensemble(uid, ens)
            self.status_bar.showMessage(
                f"Selected: {ens.display_name} | {ens.n_profiles} models"
            )

    def _on_ensemble_layer_toggled(self, uid: str, layer_name: str, visible: bool):
        """Toggle visibility of an ensemble layer."""
        ens = self._ensembles.get(uid)
        if not ens:
            return
        layer = getattr(ens, f"{layer_name}_layer", None)
        if layer:
            layer.visible = visible
        canvas = self.sheet_tabs.get_current_canvas()
        canvas.set_ensemble_layer_visible(uid, layer_name, visible)

    def _on_remove_ensemble(self, uid: str):
        """Remove an ensemble from data and canvas."""
        if uid in self._ensembles:
            del self._ensembles[uid]
        canvas = self.sheet_tabs.get_current_canvas()
        canvas.remove_ensemble(uid)
        self.curve_tree.remove_ensemble(uid)
        self.log_panel.log_info("Removed ensemble")

    def _on_ensemble_updated(self, uid: str, ens):
        """Handle ensemble style changes from properties panel -- re-render."""
        self._ensembles[uid] = ens
        canvas = self.sheet_tabs.get_current_canvas()
        canvas.update_ensemble(ens)

    # ── Vs Profile handlers ──────────────────────────────────

    def _on_vs_profile(self):
        """Open Vs Profile dialog to extract profiles from .report."""
        from geo_figure.gui.dialogs.vs_profile_dialog import VsProfileDialog
        dlg = VsProfileDialog(self)
        dlg.extraction_complete.connect(self._on_profile_extraction_complete)
        dlg.exec()

    def _on_profile_extraction_complete(self, profiles, params):
        """Handle completed profile extraction -- create Vs Profile sheet + render."""
        from geo_figure.core.profile_processing import process_profiles
        from geo_figure.core.models import VsProfileData
        from geo_figure.gui.canvas.plot_canvas import (
            LAYOUT_VS_PROFILE, LAYOUT_GRID,
        )

        profile_type = params.get("profile_type", "vs")
        depth_max = params.get("depth_max", 200.0)

        ptype_label = {"vs": "Vs", "vp": "Vp", "rho": "Density"}.get(profile_type, "Vs")

        try:
            results = process_profiles(profiles, dz=0.1, z_max=depth_max)
        except Exception as e:
            self.log_panel.log_error(f"Profile processing failed: {e}")
            return

        # Auto-detect actual data depth from profiles
        data_depth = 0.0
        for d, v in profiles:
            finite = d[np.isfinite(d) & (d > 0)]
            if len(finite) > 0:
                data_depth = max(data_depth, float(np.max(finite)))
        if data_depth <= 0:
            data_depth = depth_max

        # Determine where to place the Vs profile
        canvas = self.sheet_tabs.get_current_canvas()
        target_key = "vs_profile"
        use_existing = False

        if canvas and canvas._layout_mode == LAYOUT_GRID:
            # Use the active (selected) subplot in the current grid
            active = canvas.active_subplot
            # Skip sigma companion keys
            if active and not active.endswith("_sigma"):
                target_key = active
                use_existing = True
                # Convert the cell to vs_profile type and rebuild
                if canvas._subplot_types.get(active) != "vs_profile":
                    canvas.set_subplot_type(active, "vs_profile")

        if not use_existing:
            # Create a dedicated Vs Profile sheet with the 2-panel layout
            sheet_name = f"{ptype_label} Profile"
            canvas = self.sheet_tabs.add_sheet(sheet_name)
            new_idx = self.sheet_tabs.indexOf(canvas)
            self.sheet_tabs.setCurrentIndex(new_idx)
            self._ensure_sheet_data(new_idx)
            canvas.set_layout_mode(LAYOUT_VS_PROFILE)

        prof = VsProfileData(
            name=f"{ptype_label} Profile",
            profile_type=profile_type,
            n_profiles=len(profiles),
            subplot_key=target_key,
            profiles=profiles,
            depth_grid=results["depth_grid"],
            median=results["median"],
            p_low=results["p_low"],
            p_high=results["p_high"],
            sigma_ln=results["sigma_ln"],
            median_depth_paired=results.get("median_depth_paired"),
            median_vel_paired=results.get("median_vel_paired"),
            vs30_values=results.get("vs30_values"),
            vs100_values=results.get("vs100_values"),
            depth_max_plot=data_depth,
        )

        self._vs_profiles[prof.uid] = prof
        canvas.add_vs_profile(prof)
        self.curve_tree.add_vs_profile(prof)

        # Save CSV to project dir
        self._save_profile_csv(prof)

        vs30_str = f"Vs30={prof.vs30_mean:.1f} m/s" if prof.vs30_mean else ""
        self.log_panel.log_success(
            f"{ptype_label} Profile: {len(profiles)} models extracted. {vs30_str}"
        )

    def _save_profile_csv(self, prof):
        """Save profile statistics CSV to project/theoretical/ dir."""
        from pathlib import Path
        project_dir = getattr(self, '_project_dir', None)
        if project_dir is None or prof.depth_grid is None:
            return
        theo_dir = Path(project_dir) / "theoretical"
        theo_dir.mkdir(parents=True, exist_ok=True)
        name = prof.display_name.replace(" ", "_").replace("/", "_")
        header = "Depth_m,Median,P_low,P_high,Sigma_ln"
        lines = [header]
        for i in range(len(prof.depth_grid)):
            row = (
                f"{prof.depth_grid[i]:.3f},"
                f"{prof.median[i]:.4f},"
                f"{prof.p_low[i]:.4f},"
                f"{prof.p_high[i]:.4f},"
                f"{prof.sigma_ln[i]:.6f}"
            )
            lines.append(row)
        fpath = theo_dir / f"{name}_stats.csv"
        fpath.write_text("\n".join(lines), encoding="utf-8")
        self.log_panel.log_info(f"Saved: {fpath.name}")

    def _on_vs_profile_layer_toggled(self, uid: str, layer_name: str, visible: bool):
        """Toggle visibility of a Vs profile layer."""
        prof = self._vs_profiles.get(uid)
        if not prof:
            return
        layer = getattr(prof, f"{layer_name}_layer", None)
        if layer:
            layer.visible = visible
        canvas = self.sheet_tabs.get_current_canvas()
        canvas.set_vs_profile_layer_visible(uid, layer_name, visible)

    def _on_remove_vs_profile(self, uid: str):
        """Remove a Vs profile from data and canvas."""
        if uid in self._vs_profiles:
            del self._vs_profiles[uid]
        canvas = self.sheet_tabs.get_current_canvas()
        canvas.remove_vs_profile(uid)
        self.curve_tree.remove_vs_profile(uid)
        self.log_panel.log_info("Removed Vs profile")

    def _on_vs_profile_selected(self, uid: str, layer_name: str = ""):
        """Handle Vs profile selection from tree."""
        prof = self._vs_profiles.get(uid)
        if prof:
            self.properties.show_vs_profile(uid, prof, layer_name or None)
            self.status_bar.showMessage(
                f"Selected: {prof.display_name} | {prof.n_profiles} models"
            )

    def _on_vs_profile_updated(self, uid: str, prof):
        """Handle Vs profile display settings change from properties panel."""
        self._vs_profiles[uid] = prof
        canvas = self.sheet_tabs.get_current_canvas()
        canvas._rebuild_vs_profile(uid)
