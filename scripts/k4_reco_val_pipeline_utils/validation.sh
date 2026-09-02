#!/bin/bash
source "$(dirname "$0")/utils.sh" || exit 1
FLOW_MANIFEST="$WORKAREA/validation_flows.tsv"

if [[ ! -f "$FLOW_MANIFEST" ]]; then
    log_error "Validation flow manifest not found: $FLOW_MANIFEST"
    exit 1
fi

selected_count=0
success_count=0
warning_count=0
declare -a warning_messages=()
declare -a failure_messages=()

while IFS=$'\t' read -r detector version _slug validation config_path _config_dir _config_rel_dir _particle output_tag _energy _seed _sim_script hist_script; do
    [[ -z "$detector" ]] && continue
    ((selected_count += 1))

    flow_dir="$WORKAREA/$detector/$version"
    input_file="${detector}_${output_tag}_particleGun_digi.root"
    output_file="${detector}_${validation}_particleGun_hist.root"
    ref_dir="$WORKAREA/$REFERENCE_SAMPLE/$detector/$version"

    if ! mkdir -p "$flow_dir"; then
        message="Could not create work directory '${flow_dir}'"
        log_error "$message"
        failure_messages+=("$message")
        continue
    fi

    if ! pushd "$flow_dir" > /dev/null; then
        message="Could not enter work directory '${flow_dir}'"
        log_error "$message"
        failure_messages+=("$message")
        continue
    fi

    if [[ ! -f "$input_file" ]]; then
        message="Missing digi input for ${detector} ${version} / ${validation}: ${input_file}"
        log_warn "$message"
        warning_messages+=("$message")
        ((warning_count += 1))
        popd > /dev/null || exit 1
        continue
    fi

    log_info "Generating histograms for validation flow '${validation}' (${detector} ${version})..."
    python3 "$hist_script" \
        --input "$input_file" \
        --output "$output_file" \
        --config-source "$config_path"

    command_status=$?
    if [[ $command_status -ne 0 ]]; then
        message="Histogram generation failed for ${detector} ${version} / ${validation} (exit code ${command_status})"
        log_warn "$message"
        warning_messages+=("$message")
        ((warning_count += 1))
    else
        log_success "Histogram generation completed for ${detector} ${version} / ${validation}"
        if [[ "$MAKE_REFERENCE_SAMPLE" == "yes" ]]; then
            if ! mkdir -p "$ref_dir" || ! cp "$output_file" "$ref_dir/$output_file"; then
                message="Could not save reference histogram for ${detector} ${version} / ${validation}"
                log_warn "$message"
                warning_messages+=("$message")
                ((warning_count += 1))
                popd > /dev/null || exit 1
                continue
            fi
            log_success "Reference histogram saved for validation flow '${validation}' (${detector} ${version})"
        fi
        ((success_count += 1))
    fi

    popd > /dev/null || exit
done < <(select_flow_rows "$FLOW_MANIFEST")

finalize_flow_stage \
    "histogram extraction" \
    "Validation" \
    "Histogram extraction" \
    "$selected_count" \
    "$success_count" \
    "$warning_count" \
    warning_messages \
    failure_messages
exit $?
