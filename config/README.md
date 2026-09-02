# `config/` - Validation Configuration

The directory tree is the authoritative source for active detectors, variants,
and validation workflows. CI discovers workflows from this tree.

## Directory Layout

```
config/
├── <DETECTOR>/
│   └── <VARIANT>/
│       ├── electron.yaml
│       └── muon.yaml
├── plotting.yaml
└── web.yaml
```

## Per-Particle Validation Config

Each `<particle>.yaml` file fully defines one validation flow:

```yaml
detector:  "ALLEGRO"
version:   "ALLEGRO_o1_v03"
validation: "electron"

simulation:
  particle:   "e-"
  output_tag: "e"
  energy:     "10*GeV"
  seed:       42

detector_parameters:
  magnetic_field_tesla: 2.0
  sigma_multiplier:     3.0

subdetectors:
  drift_chamber:
    max_pseudorapidity: 0.88
    bitfield_string: "system:5,side:-2,..."

collections:
  mc_particles: "MCParticles"
  track_collections:
    - "FittedTracks"
  track_mc_assoc: "TracksFromGenParticlesAssociation"

plots:
  - key:   "momentum_resolution"
    title: "Momentum Resolution"
    x_title: "(p_reco - p_true) / p_true"
    type:  "symmetric"
    bins:  50
    xmin:  -0.25
    xmax:  0.25
    per_collection: true
    system: "tracking"
    apply_eta_cut: false

processors:
  - "detectors.ALLEGRO.ALLEGRO_o1_v03.processors.process_track_reconstruction"
```

## `plotting.yaml` - Global Style Settings

Controls ROOT canvas size, margins, fonts, axis styles, legend placement,
KS test visualization, and sample line colors. Shared across all detectors.

## `web.yaml` - Branding and Display Overrides

This file is **optional** metadata. Detectors are discovered automatically
from the `config/<DETECTOR>/<VARIANT>/` tree. `web.yaml` only provides
human-readable display names and descriptions:

```yaml
site_title:    "key4hep Reconstruction Validation"
organization:  "CERN / FCC Collaboration"
footer_text:   "key4hep Reconstruction Validation"

# Optional overrides; discovery is automatic without these entries
detectors:
  - id:          "ALLEGRO"
    version:     "ALLEGRO_o1_v03"
    name:        "ALLEGRO Detector"
    description: "A Lepton Lepton collider Experiment with Granular Read-Out"
```

## Adding a New Detector Variant

1. Create `config/<DETECTOR>/<NEW_VARIANT>/<particle>.yaml` with the required fields.
2. Create `scripts/detectors/<DETECTOR>/<NEW_VARIANT>/sim_digi.sh`, `hist.py`, and `processors.py`.
3. The pipeline will auto-discover the new variant on the next run.
4. Optionally add an entry to `web.yaml` for a custom display name.
