# `scripts/detectors/` - Detector Implementations

Each detector variant has one directory:

```text
scripts/detectors/<DETECTOR>/<VARIANT>/
├── sim_digi.sh
├── hist.py
└── processors.py
```

`sim_digi.sh` adapts the detector's FCC-config simulation command to the
pipeline interface. `hist.py` delegates to the shared histogram runner.
`processors.py` contains detector-specific event metrics.

## Adding a detector or variant

1. Copy an existing variant directory and update its simulation wrapper.
2. Keep directory names identical to the `detector` and `version` fields in
   each workflow YAML.
3. Implement processors accepting `(ctx, data_registry)` and append values
   using the configured plot keys.
4. Add the matching workflow YAML under `config/<DETECTOR>/<VARIANT>/`.
5. Run `config_discovery.py` before submitting the change.

Shared event context, ROOT I/O, histogram creation, and plotting belong in
[`k4_reco_val_utils/`](k4_reco_val_utils), not in detector directories.
