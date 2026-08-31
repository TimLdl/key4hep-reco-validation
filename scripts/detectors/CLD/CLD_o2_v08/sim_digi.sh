#!/bin/bash
# Simulation and digitization wrapper for CLD.
#
# Unlike ALLEGRO/IDEA, CLD's steering and reconstruction configuration
# (CLDConfig, https://github.com/key4hep/CLDConfig) ships with the Key4hep
# stack itself (exposed via the $CLDCONFIG environment variable), so no
# external steering-file repository needs to be cloned. The simulation is
# run with `ddsim` using CLDConfig's `cld_steer.py`, and digitization plus
# reconstruction is run with `k4run` using CLDConfig's
# `CLDReconstruction.py`, following the documented workflow at
# https://fcc-ee-detector-full-sim.docs.cern.ch/CLD/.
#
# Expected call signature (from simulation.sh):
#   source sim_digi.sh --nEvents N --particle P --energy E --outputFile TAG --seed S

set -e

# --- Default Values ---
PARTICLE="e-"
ENERGY="10*GeV"
INPUT_FILE=""
OUTPUT_FILE="o2_v08"
N_EVENTS=10
RANDOM_SEED=""
RUN_TRK_VALIDATION=false

# --- Help Function ---
print_usage() {
    echo "Usage: $0 [OPTIONS]"
    echo "  --particle    Particle type for ddsim gun (default: e-)"
    echo "  --energy      Energy for ddsim gun (default: 10*GeV)"
    echo "  --inputFile   Path to an input file (disables particle gun)"
    echo "  --outputFile  Base name for output files (default: output)"
    echo "  --nEvents     Number of events to simulate (default: 10)"
    echo "  --seed        Random seed for ddsim (optional)"
    echo "  --runTrkValidation  Run tracking validation (truth tracking)"
    exit 1
}

# --- Parse Keyword Arguments ---
while [[ $# -gt 0 ]]; do
    case $1 in
        --particle)
            PARTICLE="$2"; shift 2 ;;
        --energy)
            ENERGY="$2"; shift 2 ;;
        --inputFile)
            INPUT_FILE="$2"; shift 2 ;;
        --outputFile)
            OUTPUT_FILE="$2"; shift 2 ;;
        --nEvents)
            N_EVENTS="$2"; shift 2 ;;
        --seed)
            RANDOM_SEED="$2"; shift 2 ;;
        --runTrkValidation)
            RUN_TRK_VALIDATION=true; shift ;;
        -h|--help)
            print_usage ;;
        *)
            echo "Error: Unknown option $1"
            print_usage ;;
    esac
done

# --- Key4hep Setup ---
if [[ -z "${KEY4HEP_STACK:-}" ]]; then
    echo "Sourcing Key4hep environment..."
    source /cvmfs/sw-nightlies.hsf.org/key4hep/setup.sh
else
    echo "The Key4hep stack is already loaded."
fi

if [[ -z "${CLDCONFIG:-}" ]]; then
    echo "Error: \$CLDCONFIG is not set by the Key4hep stack; cannot find CLDConfig." >&2
    exit 1
fi
CLDCONFIG_DIR="${CLDCONFIG}/share/CLDConfig"

# --- Build ddsim command ---
DDSIM_CMD=(
ddsim
--outputFile "CLD_${OUTPUT_FILE}_sim.root"
--compactFile "${K4GEO}/FCCee/CLD/compact/CLD_o2_v08/CLD_o2_v08.xml"
--steeringFile "${CLDCONFIG_DIR}/cld_steer.py"
--numberOfEvents "${N_EVENTS}"
)

# Append seed flags if a seed is specified
if [[ -n "${RANDOM_SEED}" ]]; then
    DDSIM_CMD+=(
    --random.enableEventSeed
    --random.seed "${RANDOM_SEED}"
    )
fi

if [[ -n "${INPUT_FILE}" ]]; then
    echo "Using input file: ${INPUT_FILE} (Particle gun disabled)"
    DDSIM_CMD+=(--inputFiles "${INPUT_FILE}")
else
    echo "Using particle gun: ${N_EVENTS} event(s) of ${PARTICLE} at ${ENERGY}"
    DDSIM_CMD+=(
    --enableGun
    --gun.distribution uniform
    --gun.energy "${ENERGY}"
    --gun.particle "${PARTICLE}"
    --crossingAngleBoost 0.0
    )
fi

# Run the SIM step
echo "Running: ${DDSIM_CMD[*]}"
"${DDSIM_CMD[@]}"

# --- DIGI/RECO Step ---
# CLDReconstruction.py resolves its auxiliary files (e.g. Pandora settings)
# relative to its own location, so it must be run from the CLDConfig directory.
DIGI_CMD=(
k4run "${CLDCONFIG_DIR}/CLDReconstruction.py"
--inputFiles "$(pwd)/CLD_${OUTPUT_FILE}_sim.root"
--outputBasename "$(pwd)/CLD_${OUTPUT_FILE}_digi"
--GeoSvc.detectors "${K4GEO}/FCCee/CLD/compact/CLD_o2_v08/CLD_o2_v08.xml"
)

if [[ "${RUN_TRK_VALIDATION}" == true ]]; then
    DIGI_CMD+=(--trackingOnly --truthTracking)
fi

echo "Running: ${DIGI_CMD[*]}"
(cd "${CLDCONFIG_DIR}" && "${DIGI_CMD[@]}")

# --outputBasename appends "_REC.edm4hep.root"; rename to the pipeline-expected filename.
mv "CLD_${OUTPUT_FILE}_digi_REC.edm4hep.root" "CLD_${OUTPUT_FILE}_digi.root"

echo "Completed successfully"
