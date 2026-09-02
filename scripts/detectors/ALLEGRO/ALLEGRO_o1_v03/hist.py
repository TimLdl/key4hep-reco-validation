import argparse
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[3]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from detectors.k4_reco_val_utils.engine import run_detector_pipeline
from detectors.k4_reco_val_utils.helpers import discover_validation_configs


def main():
    det_version_dir = Path(__file__).resolve().parent
    det_family_dir = det_version_dir.parent
    default_config_dir = (
        SCRIPTS_DIR.parent / "config" / det_family_dir.name / det_version_dir.name
    )

    parser = argparse.ArgumentParser(
        description=f"{det_version_dir.name} histogram extraction runner."
    )
    parser.add_argument("--input", required=True, help="Input PODIO ROOT file path")
    parser.add_argument(
        "--output", required=True, help="Output ROOT histogram file path"
    )
    parser.add_argument(
        "--config-dir",
        default=str(default_config_dir),
        help="Directory containing YAML validation configs",
    )
    parser.add_argument(
        "--max-pseudorapidity",
        type=float,
        default=None,
        help="Optional max pseudorapidity cutoff override",
    )
    args = parser.parse_args()

    configs = discover_validation_configs(args.config_dir)
    if not configs:
        print(f"No validation YAML configs found in {args.config_dir}")
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


if __name__ == "__main__":
    main()
