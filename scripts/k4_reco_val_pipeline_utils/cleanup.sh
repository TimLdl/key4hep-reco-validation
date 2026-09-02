#!/bin/bash
source "$(dirname "$0")/utils.sh"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

log_info "Initiating runtime pipeline execution cleanup tasks..."
cd "$WORKAREA"

if ! pipeline_has_warnings && ! pipeline_has_errors; then
    body=$(cat <<EOF
Pipeline summary for ${REPO_ROOT}

Result: SUCCESS
All stages completed successfully up to and including cleanup.
EOF
)
    send_stage_mail "$REPO_ROOT" "$EMAIL_ADDRESSES" "Key4hep validation pipeline SUCCESS: completed through cleanup" "$body"
    log_success "Sent final pipeline success notification."
else
    log_info "Skipping final success notification because warning/error markers were recorded."
fi

rm -rf FCC-config .pipeline-state
rm -f metadata.yaml validation_flows.tsv repo_root.txt generated_web.yaml
log_success "Workspace scratch data removed."
