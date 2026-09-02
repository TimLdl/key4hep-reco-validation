# Key4hep Reconstruction Validation (`key4hep-reco-validation`)

This repository runs detector validation workflows end-to-end:

1. simulation/digitization,
2. histogram extraction,
3. plot rendering,
4. static website build.

The most important concept is: **the pipeline is config-driven**.  
What runs is discovered from [`config/`](config), not hardcoded in CI jobs.

---

## How workflow discovery works

Every `*.yaml` file under:

```text
config/<DETECTOR>/<VARIANT>/*.yaml
```

is treated as one validation workflow (typically one particle flow such as `electron` or `muon`).

At runtime, [`setup.sh`](scripts/k4_reco_val_pipeline_utils/setup.sh) calls [`config_discovery.py`](scripts/k4_reco_val_pipeline_utils/config_discovery.py), which:

- discovers all workflows,
- validates required scripts exist,
- writes `validation_flows.tsv`,
- generates `generated_web.yaml` for the web stage.

If `USE_DYNAMIC_SHARDS=true` (default in CI), the pipeline generates one DAG chain per workflow (or up to `MAX_DYNAMIC_SHARDS` chains when capped):

```text
setup -> (sim_i -> val_i -> plot_i)* -> workflow_gate -> web -> cleanup
```

So adding config files directly increases discovered workflows and parallel chains.
With `USE_DYNAMIC_SHARDS=false`, the same stages run through four static shards;
the workflow gate still prevents an empty website from being built or deployed.

---

## Required repository layout

For detector `XDET` and variant `XDET_o1_v01`, these are the required paths:

```text
config/XDET/XDET_o1_v01/<flow>.yaml
scripts/detectors/XDET/XDET_o1_v01/sim_digi.sh
scripts/detectors/XDET/XDET_o1_v01/hist.py
scripts/detectors/XDET/XDET_o1_v01/processors.py
```

If a required script, processor reference, plot definition, or directory identity is invalid, discovery fails early.

Use existing implementations as templates:

- [`config/ALLEGRO/ALLEGRO_o1_v03/electron.yaml`](config/ALLEGRO/ALLEGRO_o1_v03/electron.yaml)
- [`scripts/detectors/ALLEGRO/ALLEGRO_o1_v03/sim_digi.sh`](scripts/detectors/ALLEGRO/ALLEGRO_o1_v03/sim_digi.sh)
- [`scripts/detectors/ALLEGRO/ALLEGRO_o1_v03/hist.py`](scripts/detectors/ALLEGRO/ALLEGRO_o1_v03/hist.py)
- [`scripts/detectors/ALLEGRO/ALLEGRO_o1_v03/processors.py`](scripts/detectors/ALLEGRO/ALLEGRO_o1_v03/processors.py)

---

## Add a new detector family

Example: add detector family `XDET`.

1. Create config root:
   - `config/XDET/`
2. Add at least one variant directory:
   - `config/XDET/XDET_o1_v01/`
3. Add at least one workflow YAML in that variant.
4. Add matching script directory:
   - `scripts/detectors/XDET/XDET_o1_v01/`
5. Implement:
   - `sim_digi.sh`
   - `hist.py` (usually thin wrapper around shared runner)
   - `processors.py`

Optional: add display metadata in [`config/web.yaml`](config/web.yaml) (`id`, `version`, `name`, `description`).

---

## Add a new detector variant

Example: add `ALLEGRO_o1_v04`.

1. Create:
   - `config/ALLEGRO/ALLEGRO_o1_v04/`
2. Add one or more workflow YAML files (one per flow/particle).
3. Create:
   - `scripts/detectors/ALLEGRO/ALLEGRO_o1_v04/`
4. Add/port:
   - `sim_digi.sh`
   - `hist.py`
   - `processors.py`
5. Ensure YAML fields `detector` and `version` match directory/script names.

No CI YAML change is needed for discovery.

---

## Add a new validation workflow (particle/config)

Inside an existing variant directory, add `<flow>.yaml`, for example:

```text
config/ALLEGRO/ALLEGRO_o1_v03/pion.yaml
```

Minimum required keys:

```yaml
detector: "ALLEGRO"
version: "ALLEGRO_o1_v03"
validation: "pion"

simulation:
  particle: "pi-"
  output_tag: "pi"
  energy: "10*GeV"
  seed: 42
```

Also define:

- `collections` used by your processors,
- `plots` entries to be rendered,
- `processors` list (Python import paths).

Reference schema/documentation: [`config/README.md`](config/README.md)

---

## Add new plots

Plots are configured in workflow YAML under `plots:` and populated by processor functions.

### 1) Add the plot spec in YAML

Each plot entry includes at least:

- `key`
- `title`
- `x_title`
- `type` (`asymmetric`, `symmetric`, or `integer`)
- `bins`, `xmin`, `xmax`
- `per_collection` (bool)
- `system` (used for web grouping)
- `apply_eta_cut` (bool)

See concrete examples in [`electron.yaml`](config/ALLEGRO/ALLEGRO_o1_v03/electron.yaml).

### 2) Fill the corresponding data in `processors.py`

If the plot key is `momentum_resolution`, your processor must append values into:

- `data_registry["momentum_resolution"]` when `per_collection: false`, or
- `data_registry["momentum_resolution_<collection>"]` when `per_collection: true`.

The shared extraction runner is [`hist_runner.py`](scripts/detectors/k4_reco_val_utils/hist_runner.py), which is invoked by each variant `hist.py`.

### 3) Run and verify output paths

Plot images are written under:

```text
<plots-root>/<DETECTOR>/<VARIANT>/<validation_slug>/<system_slug>/*.png
```

The website stage reads this structure directly.

---

## Pipeline behavior and controls

Main pipeline entrypoint: [`.gitlab-ci.yml`](.gitlab-ci.yml)

GitLab jobs run for merge-request pipelines and pushes to the default branch.
Merge requests build and validate but never publish to EOS. Default-branch pushes
deploy the generated website after a successful child-pipeline web stage.

Relevant CI variables:

- `VERSIONS`: optional filter (`ALLEGRO_o1_v03` or `ALLEGRO/ALLEGRO_o1_v03`)
- `USE_DYNAMIC_SHARDS`: `true` to generate per-workflow DAG chains
- `MAX_DYNAMIC_SHARDS`: optional cap on discovered workflow chains
- `CI_OUTPUT_DIR`: website output directory (defaults to `$WORKAREA/web`)
- `MAKE_REFERENCE_SAMPLE`: `yes` to save references instead of comparison mode
- `WORKAREA`, `PLOTAREA`, `REFERENCE_SAMPLE`: output locations

Notification policy:

- one final SUCCESS mail in cleanup if no warnings/errors,
- WARNING/ERROR mails only when stages degrade/fail.

Additional module documentation:

- [`config/README.md`](config/README.md)
- [`scripts/detectors/README.md`](scripts/detectors/README.md)
- [`scripts/detectors/k4_reco_val_utils/README.md`](scripts/detectors/k4_reco_val_utils/README.md)
- [`scripts/web/README.md`](scripts/web/README.md)

Pipeline utility scripts are documented in:
- [`scripts/k4_reco_val_pipeline_utils/README.md`](scripts/k4_reco_val_pipeline_utils/README.md)

---

## Local execution

Run CI stages locally:

```bash
./local-run-script.sh
./local-run-script.sh --runTask web
./local-run-script.sh --runTask plot --only
```

Run validation+plot only (no simulation, using pre-existing digi files):

```bash
./validation-test.sh --data-dir /path/to/digi
```

Useful checks while extending configs:

```bash
python3 scripts/k4_reco_val_pipeline_utils/config_discovery.py \
  --repo-root "$PWD" --format tsv --output /tmp/validation_flows.tsv
```

If this command fails, fix config/script path mismatches before running CI.

---

## Quick extension checklist

Before opening an MR, verify:

- [ ] New config file is under `config/<DETECTOR>/<VARIANT>/`.
- [ ] Matching script directory exists under `scripts/detectors/<DETECTOR>/<VARIANT>/`.
- [ ] `simulation.particle`, `simulation.output_tag`, `simulation.energy` are set.
- [ ] Every new plot key is actually filled by a processor.
- [ ] `config_discovery.py` runs successfully, including processor and plot validation.
- [ ] Local pipeline run reaches at least `plot` stage.
