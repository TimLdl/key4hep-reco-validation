# `scripts/k4_reco_val_pipeline_utils/` — Pipeline Stage Utilities

This package contains the CI/CD pipeline stage shell scripts and shared Python helpers.

## Pipeline Stages

The pipeline runs in this order. Each stage reads the `validation_flows.tsv`
manifest written by `setup.sh` and iterates over it.

| Script | Stage | What it does |
|---|---|---|
| `setup.sh` | `setup` | Cleans workspace, runs `config_discovery.py` to build the TSV manifest and `generated_web.yaml`, clones FCC-config steering repo, creates per-variant work directories |
| `simulation.sh` | `simulation` | Iterates manifest; sources `sim_digi.sh` per flow with particle/energy/seed from manifest; removes failed flows from manifest |
| `validation.sh` | `validation` | Iterates manifest; runs `hist.py` to extract histograms from digi ROOT files into histogram ROOT files; optionally saves references |
| `plot.sh` | `plot` | Iterates manifest; runs `plotting.py` to render PNGs from histogram ROOT files |
| `web.sh` | `web` | Copies metadata files; runs `build_website.py` with the `generated_web.yaml` from setup |
| `cleanup.sh` | `cleanup` | Removes scratch files from workspace (`validation_flows.tsv`, `repo_root.txt`, `generated_web.yaml`, `metadata.yaml`, `FCC-config/`) |

## Shared Utilities

| File | Purpose |
|---|---|
| `utils.sh` | Sourced by all stage scripts: colored logging helpers, Key4hep stack init, `K4_LOG_DIR` setup |
| `config_discovery.py` | Discovers all validation flows from `config/<DET>/<VAR>/*.yaml`, validates required scripts exist, writes TSV manifest and generated web config |
| `logger.py` | Python logging setup; writes console (INFO) and file (DEBUG) logs; respects `K4_LOG_DIR` env var |
| `send_mail.py` | SMTP email notifications for pipeline failures |

## Manifest Format (`validation_flows.tsv`)

The TSV manifest has 13 columns (no header):

```
detector  version  slug  validation  config_path  config_dir  config_rel_dir  particle  output_tag  energy  seed  sim_script  hist_script
```

| Column | Example | Description |
|---|---|---|
| `detector` | `ALLEGRO` | Detector family name |
| `version` | `ALLEGRO_o1_v03` | Detector variant (directory name) |
| `slug` | `ALLEGRO_o1_v03` | URL-safe identifier for web builder |
| `validation` | `electron` | Particle name; used for histogram/plot filenames and web dashboard grouping |
| `config_path` | `/repo/config/ALLEGRO/ALLEGRO_o1_v03/electron.yaml` | Absolute path to the validation config |
| `config_dir` | `/repo/config/ALLEGRO/ALLEGRO_o1_v03` | Absolute path to the config directory |
| `config_rel_dir` | `config/ALLEGRO/ALLEGRO_o1_v03` | Repo-relative config dir (for web display) |
| `particle` | `e-` | Particle gun species (passed to `sim_digi.sh`) |
| `output_tag` | `e` | Short tag for digi filename: `<DET>_<output_tag>_particleGun_digi.root` |
| `energy` | `10*GeV` | Beam energy (passed to `sim_digi.sh`) |
| `seed` | `42` | Random seed for reproducibility |
| `sim_script` | `/repo/scripts/detectors/ALLEGRO/ALLEGRO_o1_v03/sim_digi.sh` | Absolute path to simulation script |
| `hist_script` | `/repo/scripts/detectors/ALLEGRO/ALLEGRO_o1_v03/hist.py` | Absolute path to histogram extraction script |

## File Naming Convention

| File type | Pattern | Example |
|---|---|---|
| Digi ROOT file | `<DET>_<output_tag>_particleGun_digi.root` | `ALLEGRO_e_particleGun_digi.root` |
| Histogram ROOT file | `<DET>_<validation>_particleGun_hist.root` | `ALLEGRO_electron_particleGun_hist.root` |
| Reference hist file | same as histogram file, stored under `$REFERENCE_SAMPLE/<DET>/<VER>/` | |

## Logging

Python scripts write log files to `$K4_LOG_DIR` (set by `utils.sh` to `$WORKAREA/logs/`).
Shell scripts write to stdout/stderr (captured by the CI runner).
