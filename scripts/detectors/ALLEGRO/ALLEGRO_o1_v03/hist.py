import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[3]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from detectors.k4_reco_val_utils.engine import run_detector_pipeline


def main():
    run_detector_pipeline(
        detector_name="ALLEGRO",
        default_config="config/ALLEGRO/ALLEGRO_o1_v03/config.yaml",
    )


if __name__ == "__main__":
    main()
