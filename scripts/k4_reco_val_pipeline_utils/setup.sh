#!/bin/bash
source "$(dirname "$0")/utils.sh" || exit 1

log_info "Performing target-specific cleanup of previous validation outputs..."

DEFAULT_REPO_ROOT="$(pipeline_repo_root)"

if [[ -z "${WORKAREA}" ]]; then
    log_error "WORKAREA environment variable is not set! Aborting script to prevent file loss."
    exit 1
fi
if [[ -z "${PLOTAREA:-}" || -z "${REFERENCE_SAMPLE:-}" || -z "${STEERING_FILE_REPO:-}" ]]; then
    log_error "PLOTAREA, REFERENCE_SAMPLE, and STEERING_FILE_REPO must be configured."
    exit 1
fi

REPO_ROOT="${CI_PROJECT_DIR:-$DEFAULT_REPO_ROOT}"
if [[ ! -f "${REPO_ROOT}/scripts/k4_reco_val_pipeline_utils/config_discovery.py" ]]; then
    log_warn "Repository root '${REPO_ROOT}' is missing the pipeline utilities; falling back to '${DEFAULT_REPO_ROOT}'."
    REPO_ROOT="$DEFAULT_REPO_ROOT"
fi
FLOW_MANIFEST="$WORKAREA/validation_flows.tsv"
GENERATED_WEB_CONFIG="$WORKAREA/generated_web.yaml"

log_info "Repository root: $REPO_ROOT"

if ! mkdir -p "$WORKAREA"; then
    log_error "Could not create work area '${WORKAREA}'."
    exit 1
fi

rm -rf "${WORKAREA}/FCC-config"
rm -f "${WORKAREA}/validation_flows.tsv" "${WORKAREA}/repo_root.txt" "${WORKAREA}/generated_web.yaml" "${WORKAREA}/metadata.yaml"
rm -rf "${WORKAREA}/.pipeline-state"

if [[ -n "${PLOTAREA}" ]]; then
    rm -rf "${WORKAREA:?}/${PLOTAREA}"
fi

if ! mkdir -p "$WORKAREA/$PLOTAREA"; then
    log_error "Could not create plot directory '${WORKAREA}/${PLOTAREA}'."
    exit 1
fi

log_info "Discovering validation flows from repository configs..."
if ! python3 "${REPO_ROOT}/scripts/k4_reco_val_pipeline_utils/config_discovery.py" \
    --repo-root "$REPO_ROOT" \
    --versions "${VERSIONS:-}" \
    --format tsv \
    --output "$FLOW_MANIFEST" \
    --base-web-config "${REPO_ROOT}/config/web.yaml" \
    --generate-web-config "$GENERATED_WEB_CONFIG"; then
    log_error "Validation flow discovery failed."
    exit 1
fi

if [[ ! -s "$FLOW_MANIFEST" ]]; then
    log_error "No validation flows were discovered. Check config and script layout."
    exit 1
fi

log_info "Cloning steering file repository..."
if ! cd "$WORKAREA"; then
    log_error "Could not enter work area '${WORKAREA}'."
    exit 1
fi
if ! git clone "$STEERING_FILE_REPO" -b "${STEERING_FILE_BRANCH:-main}" FCC-config; then
    log_error "Could not clone steering repository '${STEERING_FILE_REPO}'."
    exit 1
fi

while IFS=$'	' read -r detector version _; do
    [[ -z "$detector" || -z "$version" ]] && continue
    if ! mkdir -p "${WORKAREA}/${detector}/${version}"; then
        log_error "Could not create flow directory for '${detector} ${version}'."
        exit 1
    fi
done < <(awk -F '	' '!seen[$1 FS $2]++ {print $1 "	" $2 "	" $3}' "$FLOW_MANIFEST")

if ! printf '%s\n' "$REPO_ROOT" > "$WORKAREA/repo_root.txt"; then
    log_error "Could not write repository metadata."
    exit 1
fi
flow_count=$(wc -l < "$FLOW_MANIFEST")
variant_count=$(awk -F '	' '!seen[$1 FS $2]++ {count++} END {print count+0}' "$FLOW_MANIFEST")
log_success "Setup complete. Discovered ${flow_count} validation flow(s) across ${variant_count} detector variant(s)."
