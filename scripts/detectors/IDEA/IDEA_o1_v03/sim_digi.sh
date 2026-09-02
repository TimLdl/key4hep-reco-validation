#!/bin/bash
# Simulation and digitization wrapper for IDEA.
#
# Forwards all arguments to the FCC-config CTest simulation script.
# The script path is constructed from the $VERSION environment variable
# (exported by simulation.sh from the validation flow manifest) and the
# $WORKAREA/FCC-config/ clone created by setup.sh.
#
# Expected call signature (from simulation.sh):
#   source sim_digi.sh --nEvents N --particle P --energy E --outputFile TAG --seed S

# --- Setup Environment ---
if [ -z "${KEY4HEP_STACK:-}" ]; then
    source /cvmfs/sw-nightlies.hsf.org/key4hep/setup.sh
fi

# Enable strict error tracking for production/pipeline safety
set -e

# Locate the FCC-config ctest script for this variant.
# VERSION is set by simulation.sh from the manifest's 'version' column.
CTEST_SCRIPT="${WORKAREA}/FCC-config/FCCee/FullSim/IDEA/${VERSION}/ctest_sim_digi_reco.sh"

# --- Forward Arguments ---
source "$CTEST_SCRIPT" "$@"
