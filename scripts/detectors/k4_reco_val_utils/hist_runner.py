"""Shared histogram extraction entrypoint for all detector variants.

Each per-detector hist.py simply calls run() from this module. The script
auto-resolves the default config directory from the calling file's location.
"""
import argparse
import sys
from pathlib import Path

from detectors.k4_reco_val_utils.engine import run_detector_pipeline
from detectors.k4_reco_val_utils.helpers import discover_validation_configs


def run(calling_file: str):
    """Run the histogram extraction pipeline for a detector variant.

    Args:
        calling_file: ``__file__`` from the calling hist.py; used to resolve
            the detector name and default config directory automatically.
    """
    det_version_dir = Path(calling_file).resolve().parent
    det_family_dir = det_version_dir.parent
    scripts_dir = det_version_dir.parents[2]
    default_config_source = (
        scripts_dir.parent / "config" / det_family_dir.name / det_version_dir.name
    )

    parser = argparse.ArgumentParser(
        description=f"{det_version_dir.name} histogram extraction runner."
    )
    parser.add_argument("--input", required=True, help="Input PODIO ROOT file path")
    parser.add_argument("--output", required=True, help="Output ROOT histogram file path")
    parser.add_argument(
        "--config-source",
        "--config-dir",
        dest="config_source",
        default=str(default_config_source),
        help="Validation config file or directory containing validation configs",
    )
    parser.add_argument(
        "--max-pseudorapidity",
        type=float,
        default=None,
        help="Optional max pseudorapidity cutoff override",
    )
    args = parser.parse_args()

    configs = discover_validation_configs(args.config_source)
    if not configs:
        print(f"No validation YAML configs found in {args.config_source}", file=sys.stderr)
        sys.exit(1)

    output_path = Path(args.output)
    if output_path.exists():
        output_path.unlink()

    for cfg_path in configs:
        run_detector_pipeline(
            input_file=args.input,
            output_file=args.output,
            config_path=cfg_path,
            detector_name=det_version_dir.name,
            max_pseudorapidity=args.max_pseudorapidity,
            mode="UPDATE",
        )
