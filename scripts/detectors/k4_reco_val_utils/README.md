# `scripts/detectors/k4_reco_val_utils/` — Shared Detector Utilities

This package contains the shared processing, histogram generation, and plotting
utilities used by all detector variants. It is **detector-agnostic** and must
not contain any detector-specific logic.

## Modules

| File | Purpose |
|---|---|
| `engine.py` | Main execution driver: runs the event loop, dispatches processors, and calls histogram builders |
| `helpers.py` | ROOT histogram helpers, bitfield decoder init, KS test, axis formatting, config-driven histogram definition resolver |
| `hist_runner.py` | Shared histogram extraction entrypoint; each per-detector `hist.py` is a 8-line wrapper that calls `hist_runner.run(__file__)` |
| `context.py` | Builds an `EventContext` dataclass per event (primary MC, track-MC map, eta acceptance) |
| `io.py` | PODIO ROOT file reader and ROOT histogram file writer/reader |
| `plotting.py` | CLI-driven PNG rendering engine; reads histogram ROOT files and writes PNGs in the structure expected by `web_builder.py` |

## Plot Output Structure

`plotting.py` writes PNGs to:
```
<output_dir>/<DETECTOR>/<VARIANT>/<validation>/<system>/<plot_key>.png
```

Example:
```
plots/ALLEGRO/ALLEGRO_o1_v03/electron/tracking/momentum_resolution.png
plots/ALLEGRO/ALLEGRO_o1_v03/electron/calorimetry/total_calo_energy_linearity.png
```

This structure is consumed directly by `scripts/web/web_builder.py`.

## Adding a New Processor

Processor functions live in the per-detector `processors.py` file and are
dynamically loaded from the `processors:` list in the validation config YAML.
Each processor receives an `EventContext` and a `data_registry` dict:

```python
def process_my_metric(ctx: EventContext, data_registry: dict):
    for hit in ctx.event_data.get("MyCollection") or []:
        data_registry["my_metric_key"].append(hit.getValue())
```

Register it in the per-particle config YAML:
```yaml
processors:
  - "detectors.ALLEGRO.ALLEGRO_o1_v03.processors.process_my_metric"
```
