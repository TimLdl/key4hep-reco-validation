import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[3]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from detectors.k4_reco_val_utils.hist_runner import run

if __name__ == "__main__":
    run(__file__)
