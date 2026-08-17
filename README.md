# Key4hep Reconstruction Validation Framework (k4_reco_val)

An automated validation framework designed for evaluating detector simulation and reconstruction performance within the Key4hep ecosystem. The pipeline prouces and processes digitized PODIO ROOT event samples, extracts physics performance metrics, generates standardized histograms and vector graphics, and builds a static HTML dashboard for analysis and distribution.

---

## Project Structure

```text
.
├── config/                         # Configuration specifications for detectors, styles, and web layout
│   ├── ALLEGRO/                    # Detector concept configurations
│   │   └── ALLEGRO_o1_v03/
│   │       └── config.yaml         # Subdetector geometry, collection mappings, plot definitions, and processor list
│   ├── IDEA/                       # IDEA detector concept configurations
│   │   └── IDEA_o1_vo3/
│   │       └── config.yaml
│   ├── plotting.yaml               # Global ROOT plotting and styling specifications
│   └── web.yaml                    # Global web dashboard branding, site metadata, and detector index
├── scripts/                        # Framework logic and executable modules
│   ├── detectors/                  # Detector-specific wrapper scripts and execution shells
│   │   └── ALLEGRO/
│   │       └── ALLEGRO_o1_v03/
│   │           ├── sim_digi.sh     # Key4hep environment setup and CTest simulation trigger
│   │           └── hist.py         # Entrypoint for running the processing engine on ALLEGRO samples
│   ├── k4_reco_val_utils/          # Core processing, plotting, and extraction utilities
│   │   ├── engine.py               # Main processing engine loop and processor dynamic loader
│   │   ├── processors.py           # Subdetector metric extraction functions
│   │   ├── plotting.py             # ROOT canvas styling and plot rendering engine
│   │   └── io.py                   # PODIO event reading and ROOT I/O handlers
│   ├── k4_reco_val_pipeline_utils/ # Logging and pipeline notification helper tools
│   └── web/                        # Web site generation tools
│       ├── build_website.py        # CLI interface for static web building
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
│       ├── particle_dashboard.html.j2 # Plot gallery hierarchy with sticky quick-jump bar
│       ├── plot_card.html.j2       # Reusable component card for rendering plot images
│       ├── navbar.html.j2          # Reusable navigation bar component
│       └── components/
│           └── particle_nav.html.j2# Tabbed navigation component for switching particles
└── local-run.sh                    # End-to-end execution script for local validation runs
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
   * Scans the rendered plot directory hierarchy and extracts categorical metadata.
   * Constructs an in-memory hierarchy tree grouping plots by Subdetector, Algorithm, and Region/Module.
   * Renders Jinja2 HTML pages (`index.html`, `detector.html`, `particle_dashboard.html`) styled with a responsive CSS design system.
   * Copies static web assets to the output site directory, producing a self-contained static site ready for deployment.

---

## Adding New Features

### 1. Adding a New Histogram

To add a new histogram metric to an existing detector:

1. Open the detector configuration file (`config/<DETECTOR_FAMILY>/<VARIANT>/config.yaml`).
2. Add a new plot entry under the `plots` key:

```yaml
plots:
  - key: "my_new_metric_key"
    title: "My New Metric Title"
    x_title: "X-Axis Unit Label"
    type: "asymmetric"            # Options: asymmetric, symmetric, integer
    per_collection: false          # If true, generates one histogram per collection
    system: "tracking"            # Subdetector category (used in web hierarchy)
    technology: "drift_chamber"   # Algorithm or technology group
    region: "barrel"              # Module or spatial region
    apply_eta_cut: true           # Enforces pseudorapidity acceptance
```

3. Update or implement a processor function in `scripts/k4_reco_val_utils/processors.py` (or a detector-specific processor file) to fill the corresponding histogram key:

```python
def process_my_new_metric(ctx):
    for hit in ctx.get_collection("MyCollection"):
        val = hit.getValue()
        ctx.fill_histogram("my_new_metric_key", val)
```

### 2. Adding a New Detector Variant

To introduce a new variant of an existing detector family:

1. Create a new configuration directory under `config/<DETECTOR_FAMILY>/<NEW_VARIANT>/`.
2. Add a `config.yaml` file defining detector parameters, collection mappings, plot specifications, and the list of active processor module paths.
3. Create execution wrappers under `scripts/detectors/<DETECTOR_FAMILY>/<NEW_VARIANT>/`.
4. Register the new variant in `config/web.yaml` under the appropriate detector concept list.

### 3. Adding a New Detector Concept

To add an entirely new detector concept:

1. Create a configuration directory `config/<NEW_CONCEPT>/<VARIANT>/` containing a valid `config.yaml`.
2. Create execution scripts in `scripts/detectors/<NEW_CONCEPT>/<VARIANT>/`.
3. Add custom processor modules if the subdetector technologies require specialized extraction logic.
4. Update `config/web.yaml` to register the new concept:

```yaml
detectors:
  - id: "NEW_CONCEPT"
    name: "New Detector Concept"
    version: "NEW_CONCEPT_o1_v01"
    description: "Detector concept description"
    config_path: "config/NEW_CONCEPT/NEW_CONCEPT_o1_v01/config.yaml"
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

### Running the Full Pipeline

Execute the end-to-end pipeline locally (processing ROOT samples, generating histograms, rendering plots, and building the website):

```bash
./local-run.sh
```

### Individual Execution Steps

Pipeline steps can be executed individually:

* **Histogram Extraction:**
  ```bash
  python3 scripts/detectors/ALLEGRO/ALLEGRO_o1_v03/hist.py \
      --input path/to/input_digi.root \
      --output path/to/output_hist.root \
      --particle-prefix electron \
      --config config/ALLEGRO/ALLEGRO_o1_v03/config.yaml
  ```

* **Plot Rendering:**
  ```bash
  python3 scripts/k4_reco_val_utils/plotting.py \
      --inputs electron=path/to/output_hist.root \
      --style-config config/plotting.yaml \
      --detector-config config/ALLEGRO/ALLEGRO_o1_v03/config.yaml \
      --output-dir path/to/plots_dir
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