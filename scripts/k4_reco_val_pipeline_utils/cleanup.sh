#!/bin/bash
source "$(dirname "$0")/utils.sh"

log_info "Initiating runtime pipeline execution cleanup tasks..."
cd "$WORKAREA"
rm -rf FCC-config
rm -f metadata.yaml validation_flows.tsv repo_root.txt generated_web.yaml
log_success "Workspace scratch data removed."
