# Key4hep Reconstruction Validation (key4hep-reco-validation)

An automated validation framework for evaluating detector simulation and reconstruction performance within the key4hep ecosystem. The pipeline processes digitized ROOT event samples, generates standardized validation histograms and performance plots, and publishes a static HTML web report dashboard.

---

## Project Structure

```text
.
├── config/                         # Detector configurations (expandable for new detectors, options and variants), plotting, and web layout configs
│   ├── ALLEGRO/                    # ALLEGRO detector variant configurations (config.yaml)
│   ├── IDEA/                       # IDEA detector variant configurations (config.yaml)
│   ├── plotting.yaml               # Plot formatting and canvas properties
│   └── web.yaml                    # Web dashboard navigation and page layout mapping
├── data/                           # Input digitized ROOT files (_digi.root) indexed by detector and variant
├── output/                         # Processed ROOT histogram files (_hist.root)
├── plots/                          # Generated PNG performance plots categorized by particle, subdetector, and algorithm
├── logs/                           # Log outputs generated during pipeline execution
├── scripts/                        # Execution and utility modules
│   ├── detectors/                  # Detector-specific histogramming scripts and sim/digi shell scripts
│   ├── k4_reco_val_utils/          # Core histogramming, I/O, and plotting utility libraries
│   ├── k4_reco_val_pipeline_utils/ # Pipeline logging and notification utilities
│   └── web/                        # Web dashboard generator scripts (`build_website.py`, `web_builder.py`)
├── web/                            # Dashboard source files
│   ├── static/                     # Static web assets (CSS styling, JavaScript, logos)
│   └── templates/                  # Jinja2 HTML layout templates (`base`, `detector`, `particle_dashboard`)
├── www/                            # Rendered static website output ready for HTTP deployment
└── local-run.sh                    # Local execution script running full processing and web build
```

---

## Prerequisites

Ensure a key4hep environment is sourced (or ROOT, Python 3, and required dependencies are available):

```bash
# Example sourcing key4hep environment on CVMFS
source /cvmfs/sw.hsf.org/key4hep/setup.sh
```

Ensure required Python dependencies are installed:

```bash
pip install jinja2 pyyaml
```

---

## Local Execution & Testing

### 1. Running the Full Pipeline

To execute the full end-to-end pipeline (processing ROOT samples, generating histograms, rendering plots, and building the website):

```bash
./local-run.sh
```

### 2. Running Individual Pipeline Components

* **Histogram Generation:**
  ```bash
  python3 "scripts/detectors/${DET_FAMILY}/${DET}/hist.py" \
        --input "${INPUT_FILE}" \
        --output "${OUTPUT_FILE}" \
        --particle-prefix "${PARTICLE}" \
        --config "${CONFIG_PATH}"
  ```

* **Plot Generation:**
  ```bash
  python3 scripts/detectors/k4_reco_val_utils/plotting.py \
        --inputs "${PLOT_INPUTS[@]}" \
        --style-config config/plotting.yaml \
        --detector-config "${CONFIG_PATH}" \
        --output-dir "plots/${DET_FAMILY}/${DET}"
  ```

* **Website Build:**
  ```bash
  python3 scripts/web/build_website.py \
        --web-config config/web.yaml \
        --templates-dir web/templates \
        --static-dir web/static \
        --plots-dir plots \
        --output-dir www
  ```

### 3. Serving the Dashboard Locally

To test and view the generated validation web dashboard (`www/`) locally:

```bash
python3 -m http.server 8000 --directory www
```

Open `http://localhost:8000` in your web browser.