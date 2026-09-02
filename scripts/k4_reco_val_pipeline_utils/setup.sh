#!/bin/bash
source "$(dirname "$0")/utils.sh"

log_info "Performing target-specific cleanup of previous validation outputs..."

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DEFAULT_REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

if [[ -z "${WORKAREA}" ]]; then
    log_error "WORKAREA environment variable is not set! Aborting script to prevent file loss."
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

rm -rf "${WORKAREA}/FCC-config"
rm -f "${WORKAREA}/validation_flows.tsv" "${WORKAREA}/repo_root.txt"       "${WORKAREA}/generated_web.yaml" "${WORKAREA}/metadata.yaml"

if [[ -n "${PLOTAREA}" ]]; then
    rm -rf "${WORKAREA:?}/${PLOTAREA}"
fi

mkdir -p "$WORKAREA" "$WORKAREA/$PLOTAREA"

log_info "Discovering validation flows from repository configs..."
python3 "${REPO_ROOT}/scripts/k4_reco_val_pipeline_utils/config_discovery.py"     --repo-root "$REPO_ROOT"     --versions "${VERSIONS:-}"     --format tsv     --output "$FLOW_MANIFEST"     --base-web-config "${REPO_ROOT}/config/web.yaml"     --generate-web-config "$GENERATED_WEB_CONFIG"

if [[ ! -s "$FLOW_MANIFEST" ]]; then
    log_error "No validation flows were discovered. Check config and script layout."
    exit 1
fi

log_info "Cloning steering file repository..."
cd "$WORKAREA" || exit 1
git clone "$STEERING_FILE_REPO" -b "${STEERING_FILE_BRANCH:-main}"

while IFS=$'	' read -r detector version _; do
    [[ -z "$detector" || -z "$version" ]] && continue
    mkdir -p "${WORKAREA}/${detector}/${version}"
done < <(awk -F '	' '!seen[$1 FS $2]++ {print $1 "	" $2 "	" $3}' "$FLOW_MANIFEST")

echo "$REPO_ROOT" > "$WORKAREA/repo_root.txt"
flow_count=$(wc -l < "$FLOW_MANIFEST")
variant_count=$(awk -F '	' '!seen[$1 FS $2]++ {count++} END {print count+0}' "$FLOW_MANIFEST")
log_success "Setup complete. Discovered ${flow_count} validation flow(s) across ${variant_count} detector variant(s)."
