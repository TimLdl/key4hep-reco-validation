#!/bin/bash
source "$(dirname "$0")/utils.sh"

log_info "Initiating runtime pipeline execution cleanup tasks..."
cd "$WORKAREA"
rm -rf key4hep-reco-validation FCC-config
rm -f metadata.yaml version_array.txt
log_success "Workspace scratch data removed completely."
