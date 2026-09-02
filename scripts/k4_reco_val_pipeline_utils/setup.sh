#!/bin/bash
source "$(dirname "$0")/utils.sh"

log_info "Performing target-specific cleanup of previous validation outputs..."

if [[ -z "${WORKAREA}" ]]; then
    log_error "WORKAREA environment variable is not set! Aborting script to prevent file loss."
    exit 1
fi

rm -rf "${WORKAREA}/key4hep-reco-validation"
rm -rf "${WORKAREA}/FCC-config"
rm -f "${WORKAREA}/version_array.txt" "${WORKAREA}/metadata.yaml"

if [[ -n "${PLOTAREA}" ]]; then
    rm -rf "${WORKAREA:?}/${PLOTAREA}"
fi

CLEAN_VERSIONS=$(echo "$VERSIONS" | tr -d '[]" ')
IFS=$',' read -r -a VERSION_INPUT_ARRAY <<< "$CLEAN_VERSIONS"

mkdir -p "$WORKAREA/$PLOTAREA"

log_info "Cloning central repositories..."
cd "$WORKAREA" || exit 1

git clone "$KEY4HEP_RECO_VALIDATION_REPO" -b "${KEY4HEP_RECO_VALIDATION_BRANCH:-main}"
git clone "$STEERING_FILE_REPO" -b "${STEERING_FILE_BRANCH:-main}"

VERSION_ARRAY=()

for VERSION in "${VERSION_INPUT_ARRAY[@]}"; do
    [[ -z "$VERSION" ]] && continue

    GEOMETRY="${VERSION%%_*}"
    [[ -z "$GEOMETRY" ]] && continue

    rm -rf "${WORKAREA}/${GEOMETRY:?}/${VERSION}"

    script="${WORKAREA}/key4hep-reco-validation/scripts/detectors/${GEOMETRY}/${VERSION}/sim_digi.sh"

    if [[ -f "$script" ]]; then
        mkdir -p "${WORKAREA}/${GEOMETRY}/${VERSION}"
        VERSION_ARRAY+=("$VERSION")
    else
        log_warn "No execution script found for version: $VERSION (Skipping)"
    fi
done

declare -p VERSION_ARRAY > "$WORKAREA/version_array.txt"
log_success "Setup verification complete. Active versions: ${VERSION_ARRAY[*]}"
