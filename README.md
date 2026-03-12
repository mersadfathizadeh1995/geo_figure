# GeoFigure

**Geophysical Data Visualization Studio**

GeoFigure is a desktop application for visualizing and analyzing geophysical dispersion curves, shear-wave velocity (Vs) profiles, and soil layered models. It provides an interactive plotting environment built on PyQtGraph for real-time exploration, plus a Matplotlib Studio for producing publication-quality figures.

---

## Features

### Data Import
- **Dispersion curves** — read experimental curves from `.txt`, `.csv`, and Dinver `.target` files with auto-detection of slowness vs. velocity, stddev type, weight, and dummy columns
- **Theoretical DC** — load Geopsy `gpdc` output files containing one or more layered-model dispersion curves
- **Vs / Vp / density profiles** — import Geopsy layered-model files and `.report` extractions with full ensemble statistics (median, percentiles, sigma_ln, Vs30/Vs100)
- **Soil profile groups** — load collections of deterministic soil models with automatic group statistics
- **Flexible column mapping** — interactive data-mapper dialog for non-standard file layouts

### Interactive Canvas (PyQtGraph)
- Multi-sheet tabbed workspace with per-sheet data isolation
- Configurable subplot grid (combined, split Rayleigh/Love, custom N×M)
- Subplot type enforcement (Dispersion Curve, Vs Extraction, Soil Profile)
- Linked or independent X/Y axes across subplots
- Curve visibility toggling, point masking, and per-curve styling
- Ensemble visualization with median, percentile bands, envelope, and spaghetti plots
- Real-time error bars with support for log-normal stddev, COV, and absolute uncertainty
- Drag-and-drop subplot reassignment from the data tree

### Matplotlib Studio
- Render any sheet as a publication-ready Matplotlib figure
- Full control over typography (font family, weight, sizes), axis limits, scales, grid, and tick marks
- Per-subplot axis and legend configuration
- Legend placement options: inside, outside (left/right/top/bottom), and adjacent
- Built-in presets: **Publication** (Times New Roman) and **Compact** (DejaVu Sans)
- Export to PNG, PDF, SVG, EPS, and TIFF at configurable DPI
- Save/load render configurations per sheet

### Analysis
- **DC Compare** — load `.report` files and overlay theoretical ensembles against experimental data with statistical bands
- **Misfit Residual** — compute quantitative misfit between observed and theoretical curves
- **Vs Profile Extraction** — extract Vs profiles from inversion reports with Vs30 and Vs100 computation

### General
- Project-based workflow with organized subdirectories (`theoretical/`, `experimental/`, `figures/`, `csv/`, `session/`)
- Session persistence — save and restore full sheet state (curves, ensembles, profiles, layout)
- Export data as CSV
- Light and dark themes
- Keyboard shortcuts for common operations

---

## Requirements

- **Python** 3.10+
- **PySide6** — Qt 6 bindings for the GUI
- **NumPy** — numerical computation
- **pyqtgraph** — interactive real-time plotting
- **Matplotlib** — publication-quality figure rendering

### Optional

- **Geopsy CLI tools** (`gpdcreport`, `gpdc`, `gpprofile`) — required for `.report` file processing

---

## Installation

```bash
# Clone the repository
git clone https://github.com/mersadfathizadeh1995/geo_figure.git
cd geo_figure

# Create a virtual environment (recommended)
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # Linux / macOS

# Install dependencies
pip install PySide6 numpy pyqtgraph matplotlib
```

---

## Usage

```bash
# Run from the repository root
python -m geo_figure
```

On launch, a **Project Dialog** prompts you to select or create a project directory. The main window then opens with:

- **Data panel** (left) — tree view of all loaded curves, ensembles, and profiles
- **Plot canvas** (center) — interactive PyQtGraph sheets with tabs
- **Properties panel** (right) — per-item styling and configuration
- **Sheet panel** (right tab) — subplot layout, legend, and column-ratio settings
- **Log panel** (bottom) — operation log and status messages

### Quick workflow

1. **File → Open Curve File** (`Ctrl+O`) to load experimental dispersion curves
2. **File → Open Theoretical DC** to load Geopsy theoretical curves
3. **Analysis → DC Compare** to overlay ensemble statistics from a `.report` file
4. **Analysis → Extract Vs Profile** to compute Vs profiles with statistics
5. **Analysis → Render to Matplotlib** (`Ctrl+M`) to open the Studio and produce a publication figure
6. **File → Save Sheet** (`Ctrl+S`) to persist the full session

---

## Project Structure

```
geo_figure/
├── __init__.py              # Package metadata and version
├── __main__.py              # Entry point: python -m geo_figure
├── app.py                   # Application bootstrap (QApplication setup)
├── core/
│   ├── models.py            # Data models (CurveData, EnsembleData, VsProfileData, SoilProfile, FigureState)
│   ├── profile_processing.py# Vs profile statistics (median, percentiles, Vs30/Vs100)
│   ├── soil_profile_stats.py# SoilProfileGroup statistics computation
│   └── subplot_types.py     # Subplot type registry and validation
├── gui/
│   ├── main_window.py       # Main application window
│   ├── main_window_modules/ # Modular mixins (menus, file I/O, handlers, persistence)
│   ├── theme.py             # Dark and light QSS themes
│   ├── canvas/              # PyQtGraph interactive canvas and sheet tabs
│   ├── dialogs/             # Project setup, settings, DC compare, Vs profile dialogs
│   ├── panels/              # Data tree, properties, sheet settings, log panels
│   └── studio/              # Matplotlib Studio (renderer, settings, presets, UI panels)
├── io/
│   ├── curve_reader.py      # Dispersion curve file readers (txt, csv, target, theoretical)
│   ├── report_reader.py     # Geopsy .report file extraction via CLI
│   ├── vs_reader.py         # Vs/Vp/density profile readers (layered models)
│   ├── target_reader.py     # Dinver .target file parser
│   ├── converters.py        # Unit conversions (slowness↔velocity, stddev normalization, ft↔m)
│   ├── sheet_persistence.py # Sheet state serialization / deserialization
│   └── data_mapper/         # Interactive column-mapping dialog and parser
```

---

## License

This project is licensed under the **GNU General Public License v3.0**. See the [LICENSE](LICENSE) file for details.

---

## Contributing

Contributions are welcome! Please open an issue or submit a pull request.

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/my-feature`)
3. Commit your changes (`git commit -m "Add my feature"`)
4. Push to the branch (`git push origin feature/my-feature`)
5. Open a Pull Request

---

## Author

**Mersad Fathizadeh**

---

## Acknowledgments

- [PySide6](https://doc.qt.io/qtforpython-6/) — Qt for Python
- [pyqtgraph](https://www.pyqtgraph.org/) — scientific graphics
- [Matplotlib](https://matplotlib.org/) — publication-quality plotting
- [Geopsy](https://www.geopsy.org/) — geophysical analysis tools
