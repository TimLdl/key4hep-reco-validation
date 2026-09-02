#!/bin/bash
source "$(dirname "${BASH_SOURCE[0]:-$0}")/utils.sh" || exit 1
REPO_ROOT="$(pipeline_repo_root)"
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

while IFS=$'\t' read -r detector version _slug validation config_path _config_dir _config_rel_dir _particle _output_tag _energy _seed _n_events _run_track_validation _sim_script _hist_script; do
    [[ -z "$detector" ]] && continue
    ((selected_count += 1))

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

    hist_file="${detector}_${validation}_particleGun_hist.root"
    ref_dir="$WORKAREA/$REFERENCE_SAMPLE/$detector/$version"

    if [[ ! -f "$hist_file" ]]; then
        message="Missing histogram input for ${detector} ${version} / ${validation}: ${hist_file}"
        log_warn "$message"
        warning_messages+=("$message")
        ((warning_count += 1))
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

    command_status=$?
    if [[ $command_status -ne 0 ]]; then
        message="Plotting failed for ${detector} ${version} / ${validation} (exit code ${command_status})"
        log_warn "$message"
        warning_messages+=("$message")
        ((warning_count += 1))
    else
        log_success "Plots generated for validation flow '${validation}' (${detector} ${version})."
        ((success_count += 1))
    fi

    popd > /dev/null || exit
done < <(select_flow_rows "$FLOW_MANIFEST")

finalize_flow_stage \
    "plotting" \
    "Plot" \
    "Plot generation" \
    "$selected_count" \
    "$success_count" \
    "$warning_count" \
    warning_messages \
    failure_messages
exit $?
