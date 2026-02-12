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
        canvas = self.sheet_tabs.get_current_canvas()
        subplot_info = canvas.get_subplot_info() if canvas else None
        dlg = VsProfileDialog(self, subplot_info=subplot_info)
        dlg.extraction_complete.connect(self._on_multi_extraction_complete)
        dlg.extraction_complete_single.connect(
            self._on_profile_extraction_complete
        )
        dlg.exec()

    def _on_multi_extraction_complete(self, results_list):
        """Handle multi-property extraction results.

        Parameters
        ----------
        results_list : list of (profiles, params)
            One entry per extracted property.
        """
        if len(results_list) == 1:
            # Single property -- use legacy path
            profiles, params = results_list[0]
            self._on_profile_extraction_complete(profiles, params)
            return

        from geo_figure.core.profile_processing import process_profiles
        from geo_figure.core.models import VsProfileData
        from geo_figure.gui.canvas.plot_canvas import LAYOUT_GRID

        canvas = self.sheet_tabs.get_current_canvas()
        ptype_labels = {"vs": "Vs", "vp": "Vp", "rho": "Density"}
        created_profiles = {}

        for profiles, params in results_list:
            profile_type = params.get("profile_type", "vs")
            depth_max = params.get("depth_max", 200.0)
            units = params.get("units", "m")
            target_key = params.get("target_subplot")
            ptype_label = ptype_labels.get(profile_type, "Vs")

            try:
                results = process_profiles(
                    profiles, dz=0.1, z_max=depth_max
                )
            except Exception as e:
                self.log_panel.log_error(
                    f"{ptype_label} processing failed: {e}"
                )
                continue

            # Auto-detect actual data depth
            data_depth = 0.0
            for d, v in profiles:
                finite = d[np.isfinite(d) & (d > 0)]
                if len(finite) > 0:
                    data_depth = max(data_depth, float(np.max(finite)))
            if data_depth <= 0:
                data_depth = depth_max

            # Determine subplot target
            if target_key is None:
                target_key = canvas.active_subplot or "main"

            # Convert target cell to vs_profile type
            if canvas._subplot_types.get(target_key) != "vs_profile":
                canvas.set_subplot_type(target_key, "vs_profile")
            canvas.rename_subplot(target_key, ptype_label)

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
            created_profiles[profile_type] = prof

            # Save outputs
            self._save_profile_csv(prof, units=units)

            raw_text = params.get("raw_text", "")
            if raw_text:
                self._save_raw_profile_txt(ptype_label, raw_text)

            # Save Geopsy-format median txt (per property)
            self._save_geopsy_median_txt(prof, ptype_label)

            # Save Dinver-style paired-format txt (per property)
            self._save_dinver_style_txt(prof, ptype_label)

            vs30_str = (
                f"Vs30={prof.vs30_mean:.1f} m/s" if prof.vs30_mean else ""
            )
            self.log_panel.log_success(
                f"{ptype_label} Profile: {len(profiles)} models. {vs30_str}"
            )

        # Save combined Geopsy-format file with all properties
        if len(created_profiles) > 1:
            self._save_combined_geopsy_txt(created_profiles)

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
        units = params.get("units", "m")
        self._save_profile_csv(prof, units=units)

        # Save raw gpprofile output text to Profile folder
        raw_text = params.get("raw_text", "")
        if raw_text:
            self._save_raw_profile_txt(ptype_label, raw_text)

        # Save Geopsy-format median txt
        self._save_geopsy_median_txt(prof, ptype_label)

        # Save Dinver-style paired-format txt
        self._save_dinver_style_txt(prof, ptype_label)

        vs30_str = f"Vs30={prof.vs30_mean:.1f} m/s" if prof.vs30_mean else ""
        self.log_panel.log_success(
            f"{ptype_label} Profile: {len(profiles)} models extracted. {vs30_str}"
        )

    def _save_profile_csv(self, prof, units="m"):
        """Save comprehensive profile outputs to project/Profile/ dir.

        Generates the same files as the old vs_profile_analysis package:
        - Paired-format median CSV
        - Layer table CSV
        - Multi-sheet Excel results file with formatted headers
        """
        from pathlib import Path
        import numpy as np
        import pandas as pd

        project_dir = getattr(self, '_project_dir', None)
        if project_dir is None or prof.depth_grid is None:
            return

        vs_dir = Path(project_dir) / "Profile"
        vs_dir.mkdir(parents=True, exist_ok=True)
        name = prof.display_name.replace(" ", "_").replace("/", "_")

        conv = 3.28084 if units == "ft" else 1.0
        d_unit = "ft" if units == "ft" else "m"
        v_unit = "ft/s" if units == "ft" else "m/s"

        # ── 1. Paired-format median CSV ──
        if prof.median_depth_paired is not None and prof.median_vel_paired is not None:
            df_med = pd.DataFrame({
                f"Depth({d_unit})": np.asarray(prof.median_depth_paired) * conv,
                f"Vs({v_unit})": np.asarray(prof.median_vel_paired) * conv,
            })
            fpath = vs_dir / f"{name}_median.csv"
            df_med.to_csv(fpath, index=False, float_format="%.4f")
            self.log_panel.log_info(f"Saved: {fpath.name}")

        # ── 2. Layer table from paired median ──
        if prof.median_depth_paired is not None and prof.median_vel_paired is not None:
            try:
                depth_p = np.asarray(prof.median_depth_paired)
                vel_p = np.asarray(prof.median_vel_paired)
                layers = []
                for i in range(0, len(depth_p) - 1, 2):
                    if i < len(depth_p) - 1:
                        top = (depth_p[i - 1] if i > 0 else 0.0) * conv
                        bot = depth_p[i + 1] * conv
                        vs = vel_p[i + 1] * conv
                        layers.append({
                            "Layer": i // 2 + 1,
                            f"Top Depth ({d_unit})": round(top, 2),
                            f"Bottom Depth ({d_unit})": round(bot, 2),
                            f"Thickness ({d_unit})": round(bot - top, 2),
                            f"Median Vs ({v_unit})": round(vs, 1),
                        })
                if layers:
                    df_layer = pd.DataFrame(layers)
                    fpath = vs_dir / f"{name}_layer_table.csv"
                    df_layer.to_csv(fpath, index=False, float_format="%.1f")
                    self.log_panel.log_info(f"Saved: {fpath.name}")
            except Exception:
                pass

        # ── 3. Multi-sheet Excel results ──
        vsn_label = "Vs100" if units == "ft" else "Vs30"
        vsn_arr = prof.vs100_values if units == "ft" else prof.vs30_values
        vsn_unit = "ft/s" if units == "ft" else "m/s"

        excel_path = vs_dir / f"{name}_results.xlsx"
        try:
            with pd.ExcelWriter(excel_path, engine="xlsxwriter") as writer:
                # Sheet 1: Median Profile (on depth grid)
                df_median = pd.DataFrame({
                    f"Depth({d_unit})": prof.depth_grid * conv,
                    f"Median Vs({v_unit})": prof.median * conv,
                })
                df_median.to_excel(writer, sheet_name="Median_Profile", index=False)

                # Sheet 2: Percentiles
                df_pct = pd.DataFrame({
                    f"Depth({d_unit})": prof.depth_grid * conv,
                    f"Vs5({v_unit})": prof.p_low * conv,
                    f"Vs50({v_unit})": prof.median * conv,
                    f"Vs95({v_unit})": prof.p_high * conv,
                    "Sigma_ln": prof.sigma_ln,
                })
                df_pct.to_excel(writer, sheet_name="Percentiles", index=False)

                # Sheet 3: Summary
                summary_rows = {
                    "Parameter": [
                        "Number of Profiles",
                        f"Mean {vsn_label}",
                        f"Median {vsn_label}",
                        f"Std {vsn_label}",
                        f"{vsn_label} p5",
                        f"{vsn_label} p95",
                    ],
                    "Value": [],
                    "Units": [
                        "count", vsn_unit, vsn_unit,
                        vsn_unit, vsn_unit, vsn_unit,
                    ],
                }
                if vsn_arr is not None and len(vsn_arr) > 0:
                    valid = vsn_arr[np.isfinite(vsn_arr)]
                    nv = len(valid)
                    summary_rows["Value"] = [
                        str(len(vsn_arr)),
                        f"{np.mean(valid):.1f}" if nv else "N/A",
                        f"{np.median(valid):.1f}" if nv else "N/A",
                        f"{np.std(valid):.1f}" if nv else "N/A",
                        f"{np.percentile(valid, 5):.1f}" if nv else "N/A",
                        f"{np.percentile(valid, 95):.1f}" if nv else "N/A",
                    ]
                else:
                    summary_rows["Value"] = ["0"] + ["N/A"] * 5
                df_summary = pd.DataFrame(summary_rows)
                df_summary.to_excel(writer, sheet_name="Summary", index=False)

                # Sheet 4: Individual VsN values
                if vsn_arr is not None and len(vsn_arr) > 0:
                    df_vsn = pd.DataFrame({
                        "Profile": range(1, len(vsn_arr) + 1),
                        f"{vsn_label}({vsn_unit})": vsn_arr,
                    })
                    df_vsn.to_excel(writer, sheet_name="Vs_Values", index=False)

                # Format headers with bold green background
                workbook = writer.book
                hdr_fmt = workbook.add_format({
                    "bold": True,
                    "bg_color": "#D7E4BC",
                    "border": 1,
                })
                for sname in writer.sheets:
                    ws = writer.sheets[sname]
                    # Re-write header row with format
                    df_for_sheet = {
                        "Median_Profile": df_median,
                        "Percentiles": df_pct,
                        "Summary": df_summary,
                    }
                    if "Vs_Values" in writer.sheets and vsn_arr is not None:
                        df_for_sheet["Vs_Values"] = df_vsn
                    df_src = df_for_sheet.get(sname)
                    if df_src is not None:
                        for col_num, col_name in enumerate(df_src.columns):
                            ws.write(0, col_num, col_name, hdr_fmt)

            self.log_panel.log_info(f"Saved: {excel_path.name}")
        except Exception as exc:
            # Fallback: save the stats as plain CSV
            df_stats = pd.DataFrame({
                f"Depth({d_unit})": prof.depth_grid * conv,
                f"Vs5({v_unit})": prof.p_low * conv,
                f"Vs50({v_unit})": prof.median * conv,
                f"Vs95({v_unit})": prof.p_high * conv,
                "Sigma_ln": prof.sigma_ln,
            })
            fpath = vs_dir / f"{name}_stats.csv"
            df_stats.to_csv(fpath, index=False, float_format="%.6f")
            self.log_panel.log_info(f"Saved: {fpath.name} (Excel failed: {exc})")

        # ── 4. VsN histogram ──
        self._save_vsn_histogram(prof, vs_dir, name, units)

    def _save_vsn_histogram(self, prof, vs_dir, name, units="m"):
        """Save VsN histogram (Vs30 or Vs100) as PNG to the Vs output dir."""
        import numpy as np
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import matplotlib.ticker as mtick

        vsn_label = "Vs100" if units == "ft" else "Vs30"
        vsn_unit = "ft/s" if units == "ft" else "m/s"
        vsn_arr = prof.vs100_values if units == "ft" else prof.vs30_values

        if vsn_arr is None or len(vsn_arr) == 0:
            return
        vsn_finite = vsn_arr[np.isfinite(vsn_arr)]
        if len(vsn_finite) == 0:
            return

        fig, ax = plt.subplots(figsize=(10, 7))
        ax.hist(
            vsn_finite, bins=15,
            edgecolor="black", alpha=0.7, color="white", linewidth=1.2,
        )

        mean_v = np.mean(vsn_finite)
        std_v = np.std(vsn_finite)
        stats_text = (
            f"Mean: {mean_v:.0f} {vsn_unit}\n"
            f"Std: {std_v:.0f} {vsn_unit}\n"
            f"N: {len(vsn_finite)}"
        )
        ax.text(
            0.75, 0.75, stats_text,
            transform=ax.transAxes,
            bbox=dict(boxstyle="round", facecolor="white",
                      edgecolor="black", alpha=0.9),
            fontsize=11, verticalalignment="top",
        )

        ax.set_xlabel(f"{vsn_label} ({vsn_unit})", fontsize=14)
        ax.set_ylabel("Count", fontsize=14)
        ax.set_title(f"{vsn_label} Distribution", fontsize=16, pad=15)
        ax.tick_params(direction="in", which="both", length=4)
        ax.grid(True, alpha=0.3)
        for spine in ax.spines.values():
            spine.set_color("black")
            spine.set_linewidth(1.0)

        plt.tight_layout()

        fpath = vs_dir / f"{name}_{vsn_label}_histogram.png"
        fig.savefig(fpath, dpi=300, bbox_inches="tight",
                    facecolor="white", edgecolor="none")
        plt.close(fig)
        self.log_panel.log_info(f"Saved: {fpath.name}")

    def _save_raw_profile_txt(self, ptype_label, raw_text):
        """Save the raw gpprofile output text to the Profile output dir."""
        from pathlib import Path
        project_dir = getattr(self, '_project_dir', None)
        if not project_dir or not raw_text:
            return
        out_dir = Path(project_dir) / "Profile"
        out_dir.mkdir(parents=True, exist_ok=True)
        name = ptype_label.replace(" ", "_")
        fpath = out_dir / f"{name}_gpprofile_raw.txt"
        fpath.write_text(raw_text, encoding="utf-8")
        self.log_panel.log_info(f"Saved: {fpath.name}")

    @staticmethod
    def _paired_to_layers(depth_paired, vel_paired):
        """Convert paired step-function arrays to a list of (thickness, value).

        The paired format stores each layer as two consecutive points:
        ``[d_top, d_bot, d_bot, d_next_bot, ...]`` with matching values.
        We step through in increments of 2 to preserve every layer boundary,
        even when adjacent layers share the same value.
        The last entry gets thickness=0 (halfspace).
        """
        import numpy as np
        depth_p = np.asarray(depth_paired, dtype=float)
        vel_p = np.asarray(vel_paired, dtype=float)
        layers = []
        for k in range(0, len(depth_p) - 1, 2):
            thickness = depth_p[k + 1] - depth_p[k]
            val = vel_p[k]
            layers.append((thickness, val))
        if layers:
            layers[-1] = (0.0, layers[-1][1])
        return layers

    def _save_geopsy_median_txt(self, prof, ptype_label):
        """Save a Geopsy-format median model txt file for one property.

        Format:
            N_layers+1
            thickness  Vp  Vs  density
            ...
            0  Vp_hs  Vs_hs  density_hs
        Only the column matching the extracted property has real values;
        the other columns are filled with 0.
        """
        from pathlib import Path

        project_dir = getattr(self, '_project_dir', None)
        if not project_dir:
            return
        if prof.median_depth_paired is None or prof.median_vel_paired is None:
            return

        out_dir = Path(project_dir) / "Profile"
        out_dir.mkdir(parents=True, exist_ok=True)

        layers = self._paired_to_layers(
            prof.median_depth_paired, prof.median_vel_paired
        )

        if not layers:
            return

        # Last layer is halfspace (thickness = 0)
        layers[-1] = (0.0, layers[-1][1])

        n_entries = len(layers)
        ptype = prof.profile_type

        lines = [str(n_entries)]
        for thickness, val in layers:
            if ptype == "vs":
                lines.append(f"{thickness:.6g} 0 {val:.6g} 0")
            elif ptype == "vp":
                lines.append(f"{thickness:.6g} {val:.6g} 0 0")
            elif ptype == "rho":
                lines.append(f"{thickness:.6g} 0 0 {val:.6g}")
            else:
                lines.append(f"{thickness:.6g} 0 {val:.6g} 0")

        name = ptype_label.replace(" ", "_")
        fpath = out_dir / f"{name}_median_model.txt"
        fpath.write_text("\n".join(lines) + "\n", encoding="utf-8")
        self.log_panel.log_info(f"Saved: {fpath.name}")

    def _save_dinver_style_txt(self, prof, ptype_label):
        """Save a Dinver-style paired-format text file for one property.

        Format::
            # Vs
                value   depth
                value   depth
                ...
                value     inf
        """
        from pathlib import Path
        import numpy as np

        project_dir = getattr(self, '_project_dir', None)
        if not project_dir:
            return
        if prof.median_depth_paired is None or prof.median_vel_paired is None:
            return

        out_dir = Path(project_dir) / "Profile"
        out_dir.mkdir(parents=True, exist_ok=True)

        depth_p = np.asarray(prof.median_depth_paired, dtype=float)
        vel_p = np.asarray(prof.median_vel_paired, dtype=float)

        header = {"vs": "Vs", "vp": "Vp", "rho": "Density"}.get(
            prof.profile_type, "Vs"
        )
        lines = [f"# {header}"]
        for i in range(len(depth_p)):
            d = depth_p[i]
            v = vel_p[i]
            d_str = "inf" if (np.isinf(d) or (i == len(depth_p) - 1)) else f"{d}"
            lines.append(f"    {v}    {d_str}")

        name = ptype_label.replace(" ", "_")
        fpath = out_dir / f"{name}_median_dinver.txt"
        fpath.write_text("\n".join(lines) + "\n", encoding="utf-8")
        self.log_panel.log_info(f"Saved: {fpath.name}")

    def _save_combined_geopsy_txt(self, prof_dict):
        """Save a combined Geopsy-format file with all extracted properties.

        Parameters
        ----------
        prof_dict : dict
            Mapping of profile_type ('vs', 'vp', 'rho') to VsProfileData.
            Must contain at least one entry.

        Format::
            N_layers+1
            thickness  Vp  Vs  density
            ...
            0  Vp_hs  Vs_hs  density_hs
        """
        from pathlib import Path

        project_dir = getattr(self, '_project_dir', None)
        if not project_dir or not prof_dict:
            return

        out_dir = Path(project_dir) / "Profile"
        out_dir.mkdir(parents=True, exist_ok=True)

        # Extract layer tables from each available property
        layer_tables = {}
        for ptype, prof in prof_dict.items():
            if prof.median_depth_paired is None or prof.median_vel_paired is None:
                continue
            layer_tables[ptype] = self._paired_to_layers(
                prof.median_depth_paired, prof.median_vel_paired
            )

        if not layer_tables:
            return

        # Use the property with the most layers as the reference for thicknesses
        ref_type = max(layer_tables, key=lambda k: len(layer_tables[k]))
        ref_layers = layer_tables[ref_type]
        n = len(ref_layers)

        def get_val(ptype, idx):
            tbl = layer_tables.get(ptype)
            if tbl and idx < len(tbl):
                return tbl[idx][1]
            return 0.0

        lines = [str(n)]
        for idx in range(n):
            thickness = ref_layers[idx][0]
            vp = get_val("vp", idx)
            vs = get_val("vs", idx)
            rho = get_val("rho", idx)
            lines.append(f"{thickness:.6g} {vp:.6g} {vs:.6g} {rho:.6g}")

        fpath = out_dir / "combined_median_model.txt"
        fpath.write_text("\n".join(lines) + "\n", encoding="utf-8")
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

    # ── Soil Profile handlers ────────────────────────────────────

    def _on_soil_profile_selected(self, uid: str):
        """Handle soil profile selection from tree."""
        sd = self._sheet_data.get(self._current_sheet_idx, {})
        sp_dict = sd.get("soil_profiles", {})
        profile = sp_dict.get(uid)
        if profile:
            # Find the group this profile belongs to (if any)
            group = self._find_group_for_profile(uid)
            self.properties.show_soil_profile(uid, profile, group=group)
            self.status_bar.showMessage(
                f"Selected: {profile.display_name} | {profile.n_layers} layers"
            )

    def _on_soil_profile_visibility(self, uid: str, visible: bool):
        """Toggle visibility of a soil profile."""
        sd = self._sheet_data.get(self._current_sheet_idx, {})
        sp_dict = sd.get("soil_profiles", {})
        profile = sp_dict.get(uid)
        if profile:
            profile.visible = visible
        canvas = self.sheet_tabs.get_current_canvas()
        canvas.set_soil_profile_visible(uid, visible)

    def _on_remove_soil_profile(self, uid: str):
        """Remove a soil profile from data and canvas."""
        sd = self._sheet_data.get(self._current_sheet_idx, {})
        sp_dict = sd.get("soil_profiles", {})
        sp_dict.pop(uid, None)
        canvas = self.sheet_tabs.get_current_canvas()
        canvas.remove_soil_profile(uid)
        self.curve_tree.remove_soil_profile(uid)
        self.log_panel.log_info("Removed soil profile")

    def _on_soil_profile_updated(self, uid: str, profile):
        """Handle soil profile display settings change from properties panel."""
        sd = self._sheet_data.get(self._current_sheet_idx, {})
        sp_dict = sd.get("soil_profiles", {})
        sp_dict[uid] = profile
        canvas = self.sheet_tabs.get_current_canvas()
        canvas._rebuild_soil_profile(uid)

    def _find_group_for_profile(self, uid: str):
        """Find the SoilProfileGroup that contains the profile with the given uid."""
        sd = self._sheet_data.get(self._current_sheet_idx, {})
        for grp in sd.get("soil_profile_groups", {}).values():
            for prof in grp.profiles:
                if prof.uid == uid:
                    return grp
        return None

    def _on_group_stats_requested(self, group_uid: str):
        """Compute or update group statistics for a SoilProfileGroup."""
        sd = self._sheet_data.get(self._current_sheet_idx, {})
        groups = sd.get("soil_profile_groups", {})
        group = groups.get(group_uid)
        if group is None:
            self.log_panel.log_error(f"Group not found: {group_uid}")
            return

        # Update toggles and style from properties panel
        group.show_median = self.properties.sp_show_median_check.isChecked()
        group.show_percentile = self.properties.sp_show_percentile_check.isChecked()
        group.show_individual = self.properties.sp_show_individual_check.isChecked()
        group.median_color = self.properties.sp_median_color_hex.text()
        group.median_line_width = self.properties.sp_median_width_spin.value()
        group.percentile_color = self.properties.sp_pct_color_hex.text()
        group.percentile_alpha = round(
            self.properties.sp_pct_alpha_spin.value() * 255 / 100
        )

        # Apply individual visibility based on show_individual toggle
        for prof in group.profiles:
            prof.visible = group.show_individual

        # Compute statistics if not yet done
        if not group.has_statistics:
            from geo_figure.core.soil_profile_stats import compute_group_statistics
            ok = compute_group_statistics(
                group,
                depth_step=0.5,
                render_property=group.profiles[0].render_property if group.profiles else "vs",
            )
            if ok:
                self.log_panel.log_success(
                    f"Computed statistics for {group.display_name}: "
                    f"{len(group.depth_grid)} depth points, "
                    f"{len([p for p in group.profiles if p.visible])} profiles"
                )
            else:
                self.log_panel.log_error(
                    f"Failed to compute statistics for {group.display_name}: "
                    f"need at least 2 visible profiles"
                )

        # Rebuild canvas rendering
        canvas = self.sheet_tabs.get_current_canvas()
        from geo_figure.gui.canvas.plot_canvas_modules.soil_profile_renderer import (
            rebuild_group_stats,
        )
        for prof in group.profiles:
            canvas._rebuild_soil_profile(prof.uid)
        rebuild_group_stats(canvas, group)

        # Update properties panel
        self.properties.show_soil_profile_group(group_uid, group)
