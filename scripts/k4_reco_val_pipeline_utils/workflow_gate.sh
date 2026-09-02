#!/bin/bash
source "$(dirname "${BASH_SOURCE[0]:-$0}")/utils.sh" || exit 1

REPO_ROOT="$(pipeline_repo_root)"
PLOT_ROOT="$WORKAREA/$PLOTAREA"
FLOW_MANIFEST="$WORKAREA/validation_flows.tsv"

if [[ ! -d "$PLOT_ROOT" ]]; then
    message="Plot directory not found: $PLOT_ROOT"
    log_error "$message"
    mark_pipeline_error "$message"
    send_stage_mail "$REPO_ROOT" "$EMAIL_ADDRESSES" "Key4hep validation workflow gate ERROR: no plots directory" "$message"
    exit 1
fi

if [[ ! -f "$FLOW_MANIFEST" ]]; then
    message="Flow manifest not found: $FLOW_MANIFEST"
    log_error "$message"
    mark_pipeline_error "$message"
    send_stage_mail "$REPO_ROOT" "$EMAIL_ADDRESSES" "Key4hep validation workflow gate ERROR: missing manifest" "$message"
    exit 1
fi

plot_count=$(find "$PLOT_ROOT" -type f -name '*.png' 2>/dev/null | wc -l | tr -d ' ')

total_flows=0
flows_with_digi=0
flows_with_hist=0
flows_with_plots=0
declare -a detail_lines=()

while IFS=$'\t' read -r detector version _slug validation _config_path _config_dir _config_rel_dir _particle output_tag _energy _seed _n_events _run_track_validation _sim_script _hist_script; do
    [[ -z "$detector" ]] && continue
    ((total_flows += 1))

    flow_label="${detector} ${version} / ${validation}"
    flow_dir="$WORKAREA/$detector/$version"
    digi_file="${flow_dir}/${detector}_${output_tag}_particleGun_digi.root"
    hist_file="${flow_dir}/${detector}_${validation}_particleGun_hist.root"
    plot_dir="${PLOT_ROOT}/${detector}/${version}/$(normalize_slug "$validation")"
    legacy_plot_dir="${PLOT_ROOT}/$(normalize_slug "$detector")/$(normalize_slug "$version")/$(normalize_slug "$validation")"

    digi_status="missing"
    hist_status="missing"
    plot_status="0"
    flow_ok="true"
    issue_list=()

    if [[ -f "$digi_file" ]]; then
        digi_status="present"
        ((flows_with_digi += 1))
    else
        flow_ok="false"
        issue_list+=("missing digi ROOT: ${digi_file}")
    fi

    if [[ -f "$hist_file" ]]; then
        hist_status="present"
        ((flows_with_hist += 1))
    else
        flow_ok="false"
        issue_list+=("missing histogram ROOT: ${hist_file}")
    fi

    if [[ -d "$plot_dir" ]]; then
        flow_plot_count=$(find "$plot_dir" -type f -name '*.png' 2>/dev/null | wc -l | tr -d ' ')
        plot_status="$flow_plot_count"
        if [[ "$flow_plot_count" -gt 0 ]]; then
            ((flows_with_plots += 1))
        else
            flow_ok="false"
            issue_list+=("plot directory exists but contains no PNG files: ${plot_dir}")
        fi
    elif [[ -d "$legacy_plot_dir" ]]; then
        flow_plot_count=$(find "$legacy_plot_dir" -type f -name '*.png' 2>/dev/null | wc -l | tr -d ' ')
        plot_status="$flow_plot_count"
        if [[ "$flow_plot_count" -gt 0 ]]; then
            ((flows_with_plots += 1))
            log_warn "Using legacy slugged plot directory for ${flow_label}: ${legacy_plot_dir}; re-run plot stage to create ${plot_dir}"
            issue_list+=("using legacy slugged plot directory: ${legacy_plot_dir}; re-run plot stage to create ${plot_dir}")
        else
            flow_ok="false"
            issue_list+=("legacy plot directory exists but contains no PNG files: ${legacy_plot_dir}")
        fi
    else
        flow_ok="false"
        issue_list+=("missing plot directory: ${plot_dir}")
    fi

    if [[ "$flow_ok" != "true" ]]; then
        detail_lines+=("- ${flow_label} | digi=${digi_status}, hist=${hist_status}, plots=${plot_status}")
        for issue in "${issue_list[@]}"; do
            detail_lines+=("    • ${issue}")
        done
    fi
done < "$FLOW_MANIFEST"

if [[ "$total_flows" -eq 0 ]]; then
    message="Workflow manifest is empty: $FLOW_MANIFEST"
    log_error "$message"
    mark_pipeline_error "$message"
    send_stage_mail "$REPO_ROOT" "$EMAIL_ADDRESSES" "Key4hep validation workflow gate ERROR: empty manifest" "$message"
    exit 1
fi

if [[ "$flows_with_plots" -eq "$total_flows" ]]; then
    log_success "Workflow gate passed: all ${total_flows} workflows produced plots (${plot_count} PNG files)."
    exit 0
fi

detail_text="$(printf '%s\n' "${detail_lines[@]}")"
if [[ -z "$detail_text" ]]; then
    detail_text="(no per-flow diagnostic details captured)"
fi

body=$(cat <<EOF
Workflow gate summary for ${REPO_ROOT}

Total configured workflows: ${total_flows}
Workflows with digi output: ${flows_with_digi}/${total_flows}
Workflows with histogram output: ${flows_with_hist}/${total_flows}
Workflows with plots: ${flows_with_plots}/${total_flows}
Total discovered plot PNG files: ${plot_count}

Per-workflow issues:
${detail_text}
EOF
)

if [[ "$flows_with_plots" -gt 0 ]]; then
    mark_pipeline_warning "Partial workflow failures (${flows_with_plots}/${total_flows})"
    send_stage_mail "$REPO_ROOT" "$EMAIL_ADDRESSES" "Key4hep validation workflow gate WARNING: partial workflow failures (${flows_with_plots}/${total_flows})" "$body"
    log_warn "Workflow gate warning: ${flows_with_plots}/${total_flows} workflows produced plots."
    exit 0
fi

mark_pipeline_error "No workflows produced plots."
send_stage_mail "$REPO_ROOT" "$EMAIL_ADDRESSES" "Key4hep validation workflow gate ERROR: no successful workflows" "$body"
log_error "Workflow gate failed: no workflow produced plots."
exit 1
