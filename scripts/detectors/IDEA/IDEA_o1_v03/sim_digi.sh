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

if [ -z "${KEY4HEP_STACK:-}" ]; then
    source /cvmfs/sw-nightlies.hsf.org/key4hep/setup.sh || exit 1
fi

set -e

CTEST_SCRIPT="${WORKAREA}/FCC-config/FCCee/FullSim/IDEA/${VERSION}/ctest_sim_digi_reco.sh"

if [[ ! -f "$CTEST_SCRIPT" ]]; then
    echo "Missing FCC-config simulation script: $CTEST_SCRIPT" >&2
    exit 1
fi
source "$CTEST_SCRIPT" "$@"
