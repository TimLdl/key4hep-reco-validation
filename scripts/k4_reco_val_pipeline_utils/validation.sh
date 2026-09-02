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

    ref_dir="$WORKAREA/$REFERENCE_SAMPLE/$detector/$version"
    input_file="${detector}_${output_tag}_particleGun_digi.root"
    output_file="${detector}_${validation}_particleGun_hist.root"

    if ! pushd "$WORKAREA/$detector/$version" > /dev/null; then
        log_error "Could not enter directory: $WORKAREA/$detector/$version"
        continue
    fi

    log_info "Generating histograms for validation flow '${validation}' (${detector} ${version})..."
    python3 "$hist_script" \
        --input "$input_file" \
        --output "$output_file" \
        --config-source "$config_path"

    cmd_status=$?
    if [[ $cmd_status -ne 0 ]]; then
        log_error "Histogram generation failed for validation flow '${validation}'!"
        python3 "${REPO_ROOT}/scripts/k4_reco_val_pipeline_utils/send_mail.py" \
            --to "$EMAIL_ADDRESSES" \
            --subject "WARNING for ${detector} ${version} (${validation}): histogram generation failed" \
            --body "An error occurred when generating histograms for validation flow '${validation}' in ${detector} ${version}. Check pipeline logs."
    else
        if [[ "$MAKE_REFERENCE_SAMPLE" == "yes" ]]; then
            mkdir -p "$ref_dir"
            cp "$output_file" "$ref_dir/$output_file"
            log_success "Reference histogram saved for validation flow '${validation}' (${detector} ${version})"
        fi

        printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
            "$detector" "$version" "$slug" "$validation" "$config_path" "$config_dir" "$config_rel_dir" "$particle" "$output_tag" "$energy" "$seed" "$sim_script" "$hist_script" \
            >> "$UPDATED_FLOW_MANIFEST"
    fi

    popd > /dev/null || exit
done < "$FLOW_MANIFEST"

mv "$UPDATED_FLOW_MANIFEST" "$FLOW_MANIFEST"

if [[ ! -s "$FLOW_MANIFEST" ]]; then
    log_error "No validation flows succeeded in histogram generation."
    exit 1
fi
