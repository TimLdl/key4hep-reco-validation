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

while IFS=$'\t' read -r detector version _slug validation _config_path _config_dir _config_rel_dir particle output_tag energy seed sim_script _hist_script; do
    [[ -z "$detector" ]] && continue
    ((selected_count += 1))

    log_info "Running simulation flow '${validation}' for ${detector} ${version}"

    flow_dir="$WORKAREA/$detector/$version"
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

    (
        export VERSION="$version"
        source "$sim_script" \
            --nEvents "${NUMBER_OF_EVENTS}" \
            --particle "$particle" \
            --energy "$energy" \
            --outputFile "${output_tag}_particleGun" \
            --seed "$seed"
    )
    command_status=$?

    if [[ $command_status -ne 0 ]]; then
        message="Simulation failed for ${detector} ${version} / ${validation} (exit code ${command_status})"
        log_warn "$message"
        warning_messages+=("$message")
        ((warning_count += 1))
    else
        log_success "Simulation completed for ${detector} ${version} / ${validation}"
        ((success_count += 1))
    fi

    popd > /dev/null || exit 1
done < <(select_flow_rows "$FLOW_MANIFEST")

finalize_flow_stage \
    "simulation" \
    "Simulation" \
    "Simulation" \
    "$selected_count" \
    "$success_count" \
    "$warning_count" \
    warning_messages \
    failure_messages
exit $?
