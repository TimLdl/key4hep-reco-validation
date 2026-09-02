#!/bin/bash
export FORCE_COLOR=1
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_error() { echo -e "${RED}[ERROR]${NC} $*" >&2; }
log_success() { echo -e "${GREEN}[OK]${NC} $*"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $*"; }
log_info() { echo -e "${BLUE}[INFO]${NC} $*"; }

# Centralized, fail-soft stack initialization
if [[ -n "${KEY4HEP_STACK}" ]]; then
    log_warn "Key4hep stack already loaded in this shell. Skipping source."
else
    log_info "Sourcing current key4hep stack..."
    if [ -n "$TAG" ]; then
        source /cvmfs/sw-nightlies.hsf.org/key4hep/setup.sh -r "$TAG" || true
    else
        source /cvmfs/sw-nightlies.hsf.org/key4hep/setup.sh || true
    fi
    log_success "The key4hep stack initialization complete."
fi
