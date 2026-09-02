#!/bin/bash
source "$(dirname "$0")/utils.sh"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
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

while IFS=$'\t' read -r detector version slug validation config_path config_dir config_rel_dir particle output_tag energy seed sim_script hist_script; do
    [[ -z "$detector" ]] && continue
    ((selected_count += 1))

    flow_dir="$WORKAREA/$detector/$version"
    if ! mkdir -p "$flow_dir"; then
        msg="Could not create work directory '${flow_dir}'"
        log_error "$msg"
        failure_messages+=("$msg")
        continue
    fi

    if ! pushd "$flow_dir" > /dev/null; then
        msg="Could not enter work directory '${flow_dir}'"
        log_error "$msg"
        failure_messages+=("$msg")
        continue
    fi

    hist_file="${detector}_${validation}_particleGun_hist.root"
    ref_dir="$WORKAREA/$REFERENCE_SAMPLE/$detector/$version"

    if [[ ! -f "$hist_file" ]]; then
        msg="Missing histogram input for ${detector} ${version} / ${validation}: ${hist_file}"
        log_warn "$msg"
        warning_messages+=("$msg")
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

    cmd_status=$?
    if [[ $cmd_status -ne 0 ]]; then
        msg="Plotting failed for ${detector} ${version} / ${validation} (exit code ${cmd_status})"
        log_warn "$msg"
        warning_messages+=("$msg")
        ((warning_count += 1))
    else
        log_success "Plots generated for validation flow '${validation}' (${detector} ${version})."
        ((success_count += 1))
    fi

    popd > /dev/null || exit
done < <(select_flow_rows "$FLOW_MANIFEST")

if [[ $selected_count -eq 0 ]]; then
    msg="No validation flows were assigned to this plot shard."
    log_error "$msg"
    mark_pipeline_error "$msg"
    send_stage_mail "$REPO_ROOT" "$EMAIL_ADDRESSES" "Key4hep validation plotting ERROR: 0/0 flows completed" "Plot stage summary for ${REPO_ROOT}\n\nSelected flows: 0\nSucceeded: 0\nWarnings: 0\nErrors: 1\n\n${msg}\n"
    exit 1
fi

severity="SUCCESS"
if [[ ${#warning_messages[@]} -gt 0 || ${#failure_messages[@]} -gt 0 || $success_count -eq 0 ]]; then
    severity="WARNING"
fi

empty_exit_code=0
if [[ $success_count -eq 0 ]]; then
    empty_exit_code="$(empty_shard_exit_code)"
    if [[ "$empty_exit_code" -ne 0 ]]; then
        severity="ERROR"
    fi
fi

subject="Key4hep validation plotting ${severity}: ${success_count}/${selected_count} flows completed"

body=$(cat <<EOF
Plot stage summary for ${REPO_ROOT}

Shard: $(( $(stage_shard_index) + 1 ))/$(stage_shard_total)
Selected flows: ${selected_count}
Succeeded: ${success_count}
Warnings: ${warning_count}
Errors: ${#failure_messages[@]}

$(printf '%s\n' "${warning_messages[@]}" "${failure_messages[@]}")
EOF
)

if [[ "$severity" == "WARNING" ]]; then
    mark_pipeline_warning "$subject"
elif [[ "$severity" == "ERROR" ]]; then
    mark_pipeline_error "$subject"
fi

if [[ "$severity" != "SUCCESS" ]]; then
    send_stage_mail "$REPO_ROOT" "$EMAIL_ADDRESSES" "$subject" "$body"
fi

if [[ $success_count -eq 0 ]]; then
    if [[ "$empty_exit_code" -eq 0 ]]; then
        log_warn "Plot generation had no successful validation workflows in this shard; continuing due to SOFT_FAIL_ON_EMPTY_SHARD=true."
    else
        log_error "Plot generation had no successful validation workflows; aborting downstream stages."
    fi
    exit "$empty_exit_code"
fi
