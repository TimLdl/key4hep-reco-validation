#!/bin/bash
source "$(dirname "$0")/utils.sh"
REPO_ROOT="$(cat "$WORKAREA/repo_root.txt")"
FLOW_MANIFEST="$WORKAREA/validation_flows.tsv"

if [[ ! -f "$FLOW_MANIFEST" ]]; then
    log_error "Validation flow manifest not found: $FLOW_MANIFEST"
    exit 1
fi

COMPARISON_FAIL=0

while IFS=$'\t' read -r detector version slug validation config_path config_dir config_rel_dir particle output_tag energy seed sim_script hist_script; do
    [[ -z "$detector" ]] && continue

    if ! pushd "$WORKAREA/$detector/$version" > /dev/null; then
        log_error "Could not enter directory: $WORKAREA/$detector/$version"
        COMPARISON_FAIL=1
        continue
    fi

    hist_file="${detector}_${validation}_particleGun_hist.root"
    ref_dir="$WORKAREA/$REFERENCE_SAMPLE/$detector/$version"

    if [[ ! -f "$hist_file" ]]; then
        log_error "Histogram file not found for validation flow '${validation}': $hist_file"
        COMPARISON_FAIL=1
        popd > /dev/null || exit
        continue
    fi

    log_info "Plotting validation flow '${validation}' for ${detector} ${version} using $(basename "$config_path")"

    ref_args=()
    if [[ "$MAKE_REFERENCE_SAMPLE" != "yes" && -d "$ref_dir" ]]; then
        ref_args=(--ref-dir "$ref_dir")
    fi

    python3 "${REPO_ROOT}/scripts/detectors/k4_reco_val_utils/plotting.py" \
        --inputs "${validation}=${hist_file}" \
        --detector-config "$config_path" \
        --style-config "${REPO_ROOT}/config/plotting.yaml" \
        --output-dir "$WORKAREA/$PLOTAREA" \
        "${ref_args[@]}"

    cmd_status=$?
    if [[ $cmd_status -ne 0 ]]; then
        log_error "Plotting failed for validation flow '${validation}' (${detector} ${version})!"
        COMPARISON_FAIL=1
    else
        log_success "Plots generated for validation flow '${validation}' (${detector} ${version})."
    fi

    popd > /dev/null || exit
done < "$FLOW_MANIFEST"

if [[ $COMPARISON_FAIL -ne 0 ]]; then
    log_error "One or more plot runs failed — check logs above."
    exit 1
fi
