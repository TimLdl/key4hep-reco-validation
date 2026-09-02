import argparse
import sys
from pathlib import Path
import yaml

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from k4_reco_val_pipeline_utils.logger import setup_logger
from web.web_builder import WebBuilder

logger = setup_logger("build_website")


def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Build Key4hep reconstruction validation HTML website."
    )
    parser.add_argument(
        "--web-config",
        default="config/web.yaml",
        help="Path to website layout configuration YAML",
    )
    parser.add_argument(
        "--templates-dir",
        default="web/templates",
        help="Directory containing Jinja2 template files",
    )
    parser.add_argument(
        "--static-dir",
        default="web/static",
        help="Directory containing static web assets",
    )
    parser.add_argument(
        "--plots-dir",
        default="plots",
        help="Directory containing generated output plots",
    )
    parser.add_argument(
        "--output-dir",
        default="www",
        help="Target output directory for rendered site",
    )
    return parser.parse_args()


def main():
    args = parse_arguments()

    logger.info("Initializing website builder CLI execution.")
    logger.info(f"Web Config:   {args.web_config}")
    logger.info(f"Templates:    {args.templates_dir}")
    logger.info(f"Static Assets:{args.static_dir}")
    logger.info(f"Plots Source: {args.plots_dir}")
    logger.info(f"Target Output:{args.output_dir}")

    try:
        with open(args.web_config, "r", encoding="utf-8") as f:
            web_cfg = yaml.safe_load(f)
        logger.debug("Successfully loaded web YAML configuration.")
    except Exception as e:
        logger.error(f"Failed to load web configuration '{args.web_config}': {e}")
        sys.exit(1)

    builder = WebBuilder(
        web_config=web_cfg,
        templates_dir=Path(args.templates_dir),
        static_dir=Path(args.static_dir),
        plots_dir=Path(args.plots_dir),
        output_dir=Path(args.output_dir),
    )

    builder.build()
    logger.info("Execution complete.")


if __name__ == "__main__":
    main()
