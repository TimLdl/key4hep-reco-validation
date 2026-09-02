#!/bin/bash
source "$(dirname "$0")/utils.sh"
REPO_ROOT="$(cat "$WORKAREA/repo_root.txt")"
FLOW_MANIFEST="$WORKAREA/validation_flows.tsv"
UPDATED_FLOW_MANIFEST="$WORKAREA/validation_flows.next.tsv"

if [[ ! -f "$FLOW_MANIFEST" ]]; then
    log_error "Validation flow manifest not found: $FLOW_MANIFEST"
    exit 1
fi

: > "$UPDATED_FLOW_MANIFEST"

while IFS=$'\t' read -r detector version slug validation config_path config_dir config_rel_dir particle output_tag energy seed sim_script hist_script; do
    [[ -z "$detector" ]] && continue

    log_info "Running simulation flow '${validation}' for ${detector} ${version}"

    if ! pushd "$WORKAREA/$detector/$version" > /dev/null; then
        log_error "Could not enter directory: $WORKAREA/$detector/$version"
        continue
    fi

    (
        # sim_digi.sh uses $VERSION to locate the FCC-config ctest script.
        # Export it from the manifest's version column before sourcing.
        export VERSION="$version"
        source "$sim_script" \
            --nEvents "${NUMBER_OF_EVENTS}" \
            --particle "$particle" \
            --energy "$energy" \
            --outputFile "${output_tag}_particleGun" \
            --seed "$seed"
    )
    cmd_status=$?

    log_info "Simulation finished with exit code: ${cmd_status}"

    if [[ $cmd_status -ne 0 ]]; then
        log_error "Simulation failed for validation flow '${validation}' (${detector} ${version})!"
        python3 "${REPO_ROOT}/scripts/k4_reco_val_pipeline_utils/send_mail.py" \
            --to "$EMAIL_ADDRESSES" \
            --subject "WARNING for ${detector} ${version} (${validation}): simulation failed" \
            --body "An error occurred when running simulation for validation flow '${validation}' in ${detector} ${version}. Check pipeline logs."
    else
        printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
            "$detector" "$version" "$slug" "$validation" "$config_path" "$config_dir" "$config_rel_dir" "$particle" "$output_tag" "$energy" "$seed" "$sim_script" "$hist_script" \
            >> "$UPDATED_FLOW_MANIFEST"
    fi

    popd > /dev/null || exit
done < "$FLOW_MANIFEST"

mv "$UPDATED_FLOW_MANIFEST" "$FLOW_MANIFEST"

if [[ ! -s "$FLOW_MANIFEST" ]]; then
    log_error "No validation flows succeeded in simulation."
    exit 1
fi
