import argparse
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
    detector_name: str = "Detector",
    default_config: Optional[str] = None,
    processors: Optional[List[Callable]] = None,
):
    """Parses CLI arguments, initializes readers, and runs the histogram production pipeline."""
    parser = argparse.ArgumentParser(
        description=f"{detector_name} detector simulation histogram extraction engine."
    )
    parser.add_argument("--input", required=True, help="Input PODIO ROOT file path")
    parser.add_argument(
        "--output", required=True, help="Output ROOT histogram file path"
    )
    parser.add_argument(
        "--particle-prefix",
        required=True,
        help="Particle prefix label (e.g. electron, muon)",
    )
    parser.add_argument(
        "--config",
        "--detector-config",
        dest="config",
        default=default_config,
        required=default_config is None,
        help="Detector configuration YAML file path",
    )
    parser.add_argument(
        "--max-pseudorapidity",
        type=float,
        default=None,
        help="Optional max pseudorapidity cutoff override",
    )
    args = parser.parse_args()

    ROOT.gROOT.SetBatch(True)

    logger.info(f"Starting {detector_name} histogram generation execution.")
    logger.info(f"Input file:       {args.input}")
    logger.info(f"Output file:      {args.output}")
    logger.info(f"Particle prefix:  {args.particle_prefix}")
    logger.info(f"Detector config:  {args.config}")

    try:
        with open(args.config, "r") as f:
            det_cfg = yaml.safe_load(f)
        logger.debug("Loaded detector configuration YAML successfully.")
    except Exception as e:
        logger.error(f"Failed to load detector configuration '{args.config}': {e}")
        sys.exit(1)

    reader = open_podio_root_reader(args.input)
    if not reader:
        logger.error(f"Could not initialize PODIO reader for: {args.input}")
        sys.exit(1)

    histogram_registry = analyze_detector_simulation_file(
        podio_reader=reader,
        particle_prefix=args.particle_prefix,
        det_cfg=det_cfg,
        max_pseudorapidity_override=args.max_pseudorapidity,
        processors=processors,
    )

    write_histograms_to_file(histogram_registry, args.output)
    logger.info(f"{detector_name} histogram extraction completed successfully.")
