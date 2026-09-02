# Key4hep Reconstruction Validation Framework (key4hep-reco-validation)

An automated validation framework designed for evaluating detector simulation and reconstruction performance within the Key4hep ecosystem. The pipeline prouces and processes digitized PODIO ROOT event samples, extracts physics performance metrics, generates standardized histograms and vector graphics, and builds a static HTML dashboard for analysis and distribution.

---

## Project Structure

```text
.
├── config/                         # Configuration specifications for detectors, styles, and web layout
│   ├── ALLEGRO/                    # ALLEGRO detector concept configurations
│   │   └── ALLEGRO_o1_v03/
│   │       ├── electron.yaml       # Electron validation flow: simulation settings, collections, plots, and processors
│   │       └── muon.yaml           # Muon validation flow: simulation settings, collections, plots, and processors
│   ├── IDEA/                       # IDEA detector concept configurations
│   │   └── IDEA_o1_v03/
│   │       ├── electron.yaml       # Electron validation flow: simulation settings, collections, plots, and processors
│   │       └── muon.yaml           # Muon validation flow: simulation settings, collections, plots, and processors
│   ├── plotting.yaml               # Global ROOT plotting and styling specifications
│   └── web.yaml                    # Global web dashboard branding, site metadata, and detector index
├── scripts/                        # Framework logic and executable modules
│   ├── detectors/                  # Detector-specific wrapper scripts and processing entrypoints
│   │   ├── ALLEGRO/
│   │   │   └── ALLEGRO_o1_v03/
│   │   │       ├── sim_digi.sh     # Forwards arguments to FCC-config CTest simulation script
│   │   │       ├── hist.py         # Thin wrapper: calls shared hist_runner.run(__file__)
│   │   │       └── processors.py  # ALLEGRO-specific metric processor functions
│   │   ├── IDEA/
│   │   │   └── IDEA_o1_v03/
│   │   │       ├── sim_digi.sh     # Forwards arguments to FCC-config CTest simulation script
│   │   │       ├── hist.py         # Thin wrapper: calls shared hist_runner.run(__file__)
│   │   │       └── processors.py  # IDEA-specific metric processor functions
│   │   └── k4_reco_val_utils/      # Shared processing, plotting, and I/O utilities
│   │       ├── engine.py           # Main event loop and processor dynamic loader
│   │       ├── helpers.py          # Histogram building, config discovery, and ROOT helpers
│   │       ├── hist_runner.py      # Shared histogram extraction logic used by all hist.py wrappers
│   │       ├── plotting.py         # ROOT canvas styling and plot rendering engine
│   │       ├── context.py          # EventContext builder
│   │       └── io.py               # PODIO event reading and ROOT I/O handlers│   ├── k4_reco_val_pipeline_utils/ # Pipeline stage scripts and notification helpers
│   │   ├── setup.sh                # Workspace init, config discovery, FCC-config clone
│   │   ├── simulation.sh           # Particle gun simulation loop
│   │   ├── validation.sh           # Histogram generation and optional reference saving
│   │   ├── plot.sh                 # Plot rendering with optional KS reference comparison
│   │   ├── web.sh                  # Metadata collection and website build
│   │   ├── cleanup.sh              # Post-pipeline scratch data removal
│   │   ├── config_discovery.py     # Auto-discovers validation flows from config tree; writes manifest
│   │   ├── send_mail.py            # SMTP status notification helper
│   │   ├── logger.py               # Python logging setup (console + file, respects K4_LOG_DIR)
│   │   └── utils.sh                # Shared shell logging helpers, Key4hep stack init, K4_LOG_DIR export
│   └── web/                        # Web site generation tools
│       ├── build_website.py        # CLI interface for static site building
│       └── web_builder.py          # Metadata parser and Jinja2 template rendering engine
├── web/                            # Web frontend source code
│   ├── static/                     # Static CSS styling, main JS scripts, and images/logos
│   │   ├── css/style.css           # CSS design system
│   │   ├── js/main.js              # Lightbox viewer and UI interaction logic
│   │   └── img/                    # Logos and image assets
│   └── templates/                  # Jinja2 HTML layout templates
│       ├── base.html.j2            # Root layout containing header, navbar, and footer
│       ├── index.html.j2           # Global landing page showing available detector concepts
│       ├── detector.html.j2        # Concept overview listing particle validation dashboards
│       ├── particle_dashboard.html.j2 # Plot gallery with sticky quick-jump bar
│       └── components/
│           └── particle_nav.html.j2# Tabbed navigation component for switching particles
├── local-run-script.sh             # End-to-end pipeline execution script for local runs (uses gitlab-ci-local)
└── validation-test.sh              # Lightweight standalone test: histogram extraction + plotting only
```

---

## Data and Logic Flow

```text
+-----------------------+     +-----------------------+     +-----------------------+     +-----------------------+
|  1. Simulation &      |     |  2. Metric Extraction |     |  3. Plot Generation   |     |  4. Web Dashboard     |
|     Digitization      | --> |     (engine.py)       | --> |     (plotting.py)     | --> |     (build_website)   |
|  (sim_digi.sh)        |     |  PODIO -> TH1 ROOT    |     |  ROOT -> PNG Images   |     |  PNG -> Static HTML   |
+-----------------------+     +-----------------------+     +-----------------------+     +-----------------------+
```

1. **Simulation and Digitization (`sim_digi.sh`)**
   * Sources the Key4hep software stack via CVMFS.
   * Triggers CTest simulation/digitization workflows to generate PODIO ROOT files containing event collections (e.g., generator particles, tracking hits, calorimetry hits, topoclusters).

2. **Metric Extraction (`engine.py`, `processors.py`, `hist.py`)**
   * Opens the digitized PODIO ROOT files and initializes an `EventContext`.
   * Reads cell bitfield specifications from the detector configuration to decode readout identifiers.
   * Loads configured processors dynamically to calculate physics and reconstruction metrics.
   * Evaluates event kinematic acceptance cuts and populates standard ROOT `TH1` histograms.
   * Exports the histograms along with event processing metadata into a processed ROOT file.

3. **Plot Generation (`plotting.py`)**
   * Reads extracted ROOT histogram datasets for specified particles.
   * Applies global ROOT graphics options configured in `plotting.yaml`.
   * Renders standalone PNG images and organizes them into a structured directory hierarchy based on plot metadata (`detector/particle/system/technology/region/plot_key.png`).

4. **Web Dashboard Build (`build_website.py`, `web_builder.py`)**
   * Scans the rendered plot directory hierarchy and extracts categorical metadata for each detector variant.
   * Constructs an in-memory hierarchy tree grouping plots by Subdetector, Algorithm, and Region/Module.
   * Renders Jinja2 HTML pages (`index.html`, `detector.html`, `particle_dashboard.html`) styled with a responsive CSS design system.
   * Copies static web assets to the output site directory, producing a self-contained static site ready for deployment.

---

## Adding New Features

### 1. Adding a New Histogram

To add a new histogram metric to an existing detector:

1. Open the relevant per-particle config file (`config/<DETECTOR_FAMILY>/<VARIANT>/<particle>.yaml`).
2. Add a new plot entry under the `plots` key:

```yaml
plots:
  - key: "my_new_metric_key"
    title: "My New Metric Title"
    x_title: "X-Axis Unit Label"
    type: "asymmetric"            # Options: asymmetric, symmetric, integer
    per_collection: false          # If true, generates one histogram per track collection
    system: "tracking"            # Subdetector category (used in web hierarchy)
    technology: "drift_chamber"   # Algorithm or technology group
    region: "barrel"              # Module or spatial region
    apply_eta_cut: true           # Enforces pseudorapidity acceptance
```

3. Update or implement a processor function in `scripts/detectors/<FAMILY>/<VARIANT>/processors.py` to fill the corresponding histogram key:

```python
def process_my_new_metric(ctx, data_registry):
    for hit in ctx.get_collection("MyCollection"):
        val = hit.getValue()
        data_registry["my_new_metric_key"].append(val)
```

### 2. Adding a New Detector Variant

To introduce a new variant of an existing detector family:

1. Create a new configuration directory under `config/<DETECTOR_FAMILY>/<NEW_VARIANT>/`.
2. Add one YAML file per validation flow (e.g., `electron.yaml`, `muon.yaml`), each containing:
   - `detector`, `version`, and `validation` fields
   - a `simulation` block with `particle`, `output_tag`, and `energy` (optional `seed`)
   - `detector_parameters`, `subdetectors`, `collections`
   - a `plots` list and a `processors` list referencing the processor module paths
3. Create execution scripts under `scripts/detectors/<DETECTOR_FAMILY>/<NEW_VARIANT>/`:
   - `sim_digi.sh` — forwards arguments to the FCC-config CTest script
   - `hist.py` — thin wrapper (copy the 8-line template from any existing variant); path resolution is automatic
   - `processors.py` — implement detector-specific metric extraction
4. Optionally add a metadata override in `config/web.yaml` if you want a custom display name or description. The pipeline and website variant discovery are automatic.

### 3. Adding a New Detector Concept

To add an entirely new detector concept:

1. Create a configuration directory `config/<NEW_CONCEPT>/<VARIANT>/` containing per-particle YAML files.
2. Create execution scripts in `scripts/detectors/<NEW_CONCEPT>/<VARIANT>/`.
3. Add custom processor modules if the subdetector technologies require specialized extraction logic.
4. Optionally add a metadata override in `config/web.yaml` for a custom display name or description:

```yaml
# config/web.yaml  (optional — for custom display name/description only)
detectors:
  - id: "NEW_CONCEPT"
    version: "NEW_CONCEPT_o1_v01"
    name: "New Detector Concept"
    description: "Detector concept description"
```

---

## Local Development and Testing

### Prerequisites

Source the Key4hep software environment to ensure ROOT, PODIO, Python 3, and required dependencies are available:

```bash
source /cvmfs/sw-nightlies.hsf.org/key4hep/setup.sh
```

Ensure Python dependencies for web generation and configuration parsing are installed:

```bash
pip install jinja2 pyyaml
```

### Running the Full Pipeline (via `gitlab-ci-local`)

`local-run-script.sh` mirrors the CI pipeline using `gitlab-ci-local`. By default it runs all stages up to and including `plot`:

```bash
./local-run-script.sh                         # setup → simulation → validation → plot
./local-run-script.sh --runTask web           # includes website build
./local-run-script.sh --runTask validation    # stops after histogram extraction
./local-run-script.sh --runTask plot --only   # runs only the plot stage (manifest must exist)
./local-run-script.sh --help                  # show all options
```

Key environment variable overrides:

| Variable | Default | Description |
|---|---|---|
| `WORKAREA` | `~/local-k4-validation` | Workspace root |
| `VERSIONS` | *(all)* | Comma-separated variant filter, e.g. `ALLEGRO_o1_v03` |
| `MAKE_REFERENCE_SAMPLE` | `yes` | Set to `no` to enable reference comparison instead |
| `TAG` | *(latest nightly)* | Key4hep nightly release tag |

### Lightweight Validation Test (no simulation)

`validation-test.sh` runs only histogram extraction and plotting against pre-existing digi files, without invoking simulation. It auto-discovers all validation flows from `config/`:

```bash
./validation-test.sh                                      # uses ./data/ for input
./validation-test.sh --data-dir /path/to/digi/files
./validation-test.sh --versions ALLEGRO_o1_v03            # limit to one variant
./validation-test.sh --help
```

Input digi files are expected at:
```
<data-dir>/<DETECTOR>/<VARIANT>/<DETECTOR>_<output_tag>_particleGun_digi.root
```

### Individual Execution Steps

Pipeline steps can be executed individually:

* **Histogram Extraction:**
  ```bash
  python3 scripts/detectors/ALLEGRO/ALLEGRO_o1_v03/hist.py \
      --input path/to/ALLEGRO_e_particleGun_digi.root \
      --output path/to/ALLEGRO_electron_particleGun_hist.root \
      --config-source config/ALLEGRO/ALLEGRO_o1_v03/electron.yaml
  ```

* **Plot Rendering:**
  ```bash
  python3 scripts/detectors/k4_reco_val_utils/plotting.py \
      --inputs electron=path/to/ALLEGRO_electron_particleGun_hist.root \
      --style-config config/plotting.yaml \
      --detector-config config/ALLEGRO/ALLEGRO_o1_v03/electron.yaml \
      --output-dir path/to/plots_dir
  ```

  To overlay a reference histogram for KS comparison, also pass:
  ```bash
      --ref-dir path/to/references/ALLEGRO/ALLEGRO_o1_v03
  ```

* **Website Build:**
  ```bash
  python3 scripts/web/build_website.py \
      --web-config config/web.yaml \
      --templates-dir web/templates \
      --static-dir web/static \
      --plots-dir path/to/plots_dir \
      --output-dir path/to/www_dir
  ```

### Local Inspection

To view the generated web dashboard locally:

```bash
python3 -m http.server 8000 --directory path/to/www_dir
```

Open `http://localhost:8000` in a web browser.