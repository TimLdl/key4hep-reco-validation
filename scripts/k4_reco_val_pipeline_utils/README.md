# `scripts/k4_reco_val_pipeline_utils/` - Pipeline Utilities

This directory contains the GitLab stage scripts and shared pipeline helpers.

## Pipeline Stages

The pipeline runs in this order. Each stage reads the `validation_flows.tsv`
manifest written by `setup.sh` and iterates over it. In GitLab CI, the default
mode generates a child pipeline with one workflow DAG chain per discovered
validation flow (`simulation -> validation -> plot`), while `setup`, `web`,
deployment, and cleanup remain shared serial stages.

| Script | Stage | Purpose |
|---|---|---|
| `setup.sh` | `setup` | Cleans workspace, runs `config_discovery.py` (including processor and plot validation) to build the TSV manifest and `generated_web.yaml`, clones FCC-config steering repo, creates per-variant work directories |
| `simulation.sh` | `simulation` | Processes the manifest shard assigned to the job; sources `sim_digi.sh` per flow with particle/energy/seed from manifest; emits a warning summary instead of failing the whole pipeline when individual flows fail |
| `validation.sh` | `validation` | Processes the manifest shard assigned to the job; runs `hist.py` to extract histograms from digi ROOT files into histogram ROOT files; optionally saves references; warns on recoverable flow failures |
| `plot.sh` | `plot` | Processes the manifest shard assigned to the job; runs `plotting.py` to render PNGs from histogram ROOT files; warns on recoverable flow failures |
| `workflow_gate.sh` | `gate` | Verifies at least one plot PNG exists before shared web build; fails pipeline if all workflow chains produced no plots |
| `web.sh` | `web` | Copies metadata files; runs `build_website.py` with the `generated_web.yaml` from setup; sends a stage summary mail and fails if the website build fails |
| `cleanup.sh` | `cleanup` | Sends final success mail when no warning/error markers were recorded; removes scratch files from workspace (`validation_flows.tsv`, `repo_root.txt`, `generated_web.yaml`, `metadata.yaml`, `FCC-config/`, `.pipeline-state/`) |

## Shared Utilities

| File | Purpose |
|---|---|
| `utils.sh` | Sourced by all stage scripts: colored logging helpers, Key4hep stack init, `K4_LOG_DIR` setup, flow selection helpers, and centralized notification/marker functions |
| `config_discovery.py` | Discovers all validation flows from `config/<DET>/<VAR>/*.yaml`, validates scripts, processor references, plot definitions, directory identities, and duplicates, then writes the TSV manifest and generated web config |
| `generate_dynamic_pipeline.py` | Builds a child `.gitlab-ci.yml` with one DAG chain per workflow (`MAX_DYNAMIC_SHARDS` can cap the number of chains) |
| `logger.py` | Python logging setup; writes console (INFO) and file (DEBUG) logs; respects `K4_LOG_DIR` env var |
| `send_mail.py` | SMTP email notifications for pipeline failures |

`utils.sh` supports two flow-selection modes:
- `FLOW_SHARD_TOTAL=<n>` and `FLOW_SHARD_INDEX=<i>` select a generated DAG shard slice.
- `CI_NODE_TOTAL` / `CI_NODE_INDEX` select a runner-provided shard slice (used by static fallback `parallel:` jobs).
- `SOFT_FAIL_ON_EMPTY_SHARD=true` keeps per-chain jobs non-fatal when their selected flow fails, while `workflow_gate.sh` enforces the global "at least one successful workflow" requirement.
- `SUPPRESS_SHARD_MAILS=true` suppresses high-volume per-shard stage emails so notifications come mainly from shared gate/web summaries.

`MAX_DYNAMIC_SHARDS` limits the number of generated chains, but all manifest rows
remain assigned: each chain processes its modulo slice of the manifest.

The web stage fails the pipeline when the site builder returns a non-zero status;
partial workflow results are handled by `workflow_gate.sh`, not by silently
deploying a failed website build. Deployment is generated in the child pipeline
after the web artifact is available and is restricted to successful
default-branch push pipelines.

Mailing policy:
- SUCCESS mail is sent once at `cleanup.sh` when the whole pipeline finishes cleanly.
- WARNING mails are sent for soft-fail conditions (recoverable issues).
- ERROR mails are sent for hard-fail conditions (pipeline-blocking issues).

Warning/error markers are written per job under `$WORKAREA/.pipeline-state/` and merged through CI artifacts so the final cleanup stage can reliably detect whether any upstream stage emitted warnings/errors.

## Manifest Format (`validation_flows.tsv`)

The TSV manifest has 15 columns (no header):

```
detector  version  slug  validation  config_path  config_dir  config_rel_dir  particle  output_tag  energy  seed  n_events  run_track_validation  sim_script  hist_script
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
| `seed` | `42` | Random seed for reproducibility (config `simulation.seed`, default `42`) |
| `n_events` | `100` | Number of events to simulate (config `simulation.n_events`, default `10` when omitted) |
| `run_track_validation` | `false` | Whether to pass `--runTrackValidation` to the digi/reco step (config `simulation.run_track_validation`, default `false`) |
| `sim_script` | `/repo/scripts/detectors/ALLEGRO/ALLEGRO_o1_v03/sim_digi.sh` | Absolute path to simulation script |
| `hist_script` | `/repo/scripts/detectors/ALLEGRO/ALLEGRO_o1_v03/hist.py` | Absolute path to histogram extraction script |

## File Naming Convention

| File type | Pattern | Example |
|---|---|---|
| Digi ROOT file | `<DET>_<output_tag>_particleGun_digi.root` | `ALLEGRO_e_particleGun_digi.root` |
| Histogram ROOT file | `<DET>_<validation>_particleGun_hist.root` | `ALLEGRO_electron_particleGun_hist.root` |
| Reference hist file | same as histogram file, stored under `$REFERENCE_SAMPLE/<DET>/<VER>/` | |

## Logging

Python scripts write log files to `$K4_LOG_DIR` (normally `$WORKAREA/logs/`).
Shell scripts write to stdout/stderr (captured by the CI runner).
