"""Histogram extraction execution engine.

Orchestrates the full event loop over a PODIO simulation file:

1. Loads detector configuration (YAML).
2. Resolves histogram definitions from the ``plots`` config block.
3. Dynamically imports and runs processor functions from the ``processors`` config block.
4. Calls :func:`build_and_fill_histograms` to produce ROOT TH1 objects.
5. Writes the histogram registry to a ROOT file.

Entry points:

- :func:`run_detector_pipeline` — used by ``hist.py`` / ``hist_runner.py``
- :func:`analyze_detector_simulation_file` — used internally by :func:`run_detector_pipeline`
"""

import importlib
import sys
from typing import Callable, List, Optional

import ROOT
import yaml

from detectors.k4_reco_val_utils.context import build_event_context
from detectors.k4_reco_val_utils.helpers import (
    build_and_fill_histograms,
    init_bitfield_coder,
    resolve_histogram_definitions,
)
from detectors.k4_reco_val_utils.io import (
    open_podio_root_reader,
    write_histograms_to_file,
)
from k4_reco_val_pipeline_utils.logger import setup_logger

logger = setup_logger("engine")


def resolve_processors(
    det_cfg: dict, explicit_processors: Optional[List[Callable]] = None
) -> List[Callable]:
    """Resolves active metric processor functions from argument list or YAML imports."""
    if explicit_processors:
        return explicit_processors

    cfg_processors = det_cfg.get("processors", [])
    if not cfg_processors:
        logger.warning("No processors explicitly provided or configured in YAML.")
        return []

    resolved = []
    for proc_path in cfg_processors:
        try:
            module_name, func_name = proc_path.rsplit(".", 1)
            mod = importlib.import_module(module_name)
            resolved.append(getattr(mod, func_name))
            logger.debug(f"Loaded processor: {proc_path}")
        except Exception as e:
            logger.error(f"Failed to import processor '{proc_path}': {e}")
            sys.exit(1)

    return resolved


def analyze_detector_simulation_file(
    podio_reader,
    particle_prefix: str,
    det_cfg: dict,
    bitfield_decoder=None,
    max_pseudorapidity_override: Optional[float] = None,
    processors: Optional[List[Callable]] = None,
):
    """Executes event loop over detector simulation data and dispatches registered processors."""
    active_processors = resolve_processors(det_cfg, processors)

    det_params = det_cfg.get("detector_parameters", {})
    sigma_multiplier = det_params.get("sigma_multiplier", 3.0)
    max_eta = (
        max_pseudorapidity_override
        if max_pseudorapidity_override is not None
        else det_params.get("max_pseudorapidity")
    )
    if max_eta is None:
        for sub_cfg in det_cfg.get("subdetectors", {}).values():
            if isinstance(sub_cfg, dict) and "max_pseudorapidity" in sub_cfg:
                max_eta = sub_cfg["max_pseudorapidity"]
                break

    if bitfield_decoder is None:
        bitfield_decoder = init_bitfield_coder(det_cfg, logger)

    histo_defs = resolve_histogram_definitions(det_cfg, logger)
    data_registry = {key: [] for key in histo_defs.keys()}
    accepted_count_total, accepted_count_eta = 0, 0

    events = podio_reader.get("events")
    logger.info(
        f"[{particle_prefix}] Processing events with {len(active_processors)} processor(s)..."
    )

    for event_data in events:
        accepted_count_total += 1

        ctx = build_event_context(
            event_data=event_data,
            config=det_cfg,
            bitfield_decoder=bitfield_decoder,
            max_eta=max_eta,
        )

        if not ctx:
            continue

        if ctx.is_accepted_eta:
            accepted_count_eta += 1

        for proc in active_processors:
            proc(ctx, data_registry)

    logger.info(
        f"[{particle_prefix}] Event processing complete. Generating histograms..."
    )
    return build_and_fill_histograms(
        data_registry=data_registry,
        histo_defs=histo_defs,
        particle_prefix=particle_prefix,
        accepted_count_total=accepted_count_total,
        accepted_count_eta=accepted_count_eta,
        sigma_multiplier=sigma_multiplier,
        logger=logger,
        config=det_cfg,
    )


def run_detector_pipeline(
    input_file: str,
    output_file: str,
    config_path: str,
    detector_name: str = "Detector",
    particle_prefix: Optional[str] = None,
    max_pseudorapidity: Optional[float] = None,
    processors: Optional[List[Callable]] = None,
    mode: str = "UPDATE",
):
    """Executes histogram generation pipeline using direct Python parameters."""
    ROOT.gROOT.SetBatch(True)

    try:
        with open(config_path, "r") as f:
            det_cfg = yaml.safe_load(f)
        logger.debug(f"Loaded detector configuration YAML from '{config_path}'.")
    except Exception as e:
        logger.error(f"Failed to load detector configuration '{config_path}': {e}")
        sys.exit(1)

    prefix = particle_prefix or det_cfg.get("validation", "general")

    logger.info(f"Starting {detector_name} histogram generation execution.")
    logger.info(f"Input file:       {input_file}")
    logger.info(f"Output file:      {output_file}")
    logger.info(f"Particle prefix:  {prefix}")
    logger.info(f"Detector config:  {config_path}")

    reader = open_podio_root_reader(input_file)
    if not reader:
        logger.error(f"Could not initialize PODIO reader for: {input_file}")
        sys.exit(1)

    histogram_registry = analyze_detector_simulation_file(
        podio_reader=reader,
        particle_prefix=prefix,
        det_cfg=det_cfg,
        max_pseudorapidity_override=max_pseudorapidity,
        processors=processors,
    )

    write_histograms_to_file(histogram_registry, output_file, mode=mode)
    logger.info(f"{detector_name} histogram extraction completed for [{prefix}].")
