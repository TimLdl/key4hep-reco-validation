#!/bin/bash
# Shared shell utilities for all pipeline stage scripts.
# Provides logging, stack initialization, flow selection and notification helpers.

export FORCE_COLOR=1
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_error()   { echo -e "${RED}[ERROR]${NC} $*" >&2; }
log_success() { echo -e "${GREEN}[OK]${NC} $*"; }
log_warn()    { echo -e "${YELLOW}[WARN]${NC} $*"; }
log_info()    { echo -e "${BLUE}[INFO]${NC} $*"; }

pipeline_repo_root() {
    local default_root
    default_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
    if [[ -n "${CI_PROJECT_DIR}" && -f "${CI_PROJECT_DIR}/scripts/k4_reco_val_pipeline_utils/utils.sh" ]]; then
        printf '%s\n' "$CI_PROJECT_DIR"
    else
        printf '%s\n' "$default_root"
    fi
}

normalize_slug() {
    local value="$1"
    local cleaned
    cleaned="$(printf '%s' "$value" | tr '[:upper:]' '[:lower:]' | sed -E 's/[^a-z0-9]+/_/g; s/^_+//; s/_+$//; s/_+/_/g')"
    if [[ -z "$cleaned" ]]; then
        printf 'general\n'
    else
        printf '%s\n' "$cleaned"
    fi
}

stage_shard_total() {
    if [[ "${FLOW_SHARD_TOTAL:-}" =~ ^[0-9]+$ && "${FLOW_SHARD_TOTAL:-}" -gt 1 ]]; then
        printf '%s\n' "$FLOW_SHARD_TOTAL"
        return 0
    fi
    if [[ "${CI_NODE_TOTAL:-1}" =~ ^[0-9]+$ && "${CI_NODE_TOTAL:-1}" -gt 1 ]]; then
        printf '%s\n' "$CI_NODE_TOTAL"
    else
        printf '1\n'
    fi
}

stage_shard_index() {
    if [[ "${FLOW_SHARD_TOTAL:-}" =~ ^[0-9]+$ && "${FLOW_SHARD_TOTAL:-}" -gt 1 && "${FLOW_SHARD_INDEX:-}" =~ ^[0-9]+$ && "${FLOW_SHARD_INDEX:-}" -ge 0 ]]; then
        printf '%s\n' "$FLOW_SHARD_INDEX"
        return 0
    fi
    if [[ "${CI_NODE_TOTAL:-1}" =~ ^[0-9]+$ && "${CI_NODE_TOTAL:-1}" -gt 1 && "${CI_NODE_INDEX:-1}" =~ ^[0-9]+$ && "${CI_NODE_INDEX:-1}" -ge 1 ]]; then
        printf '%s\n' "$((CI_NODE_INDEX - 1))"
    else
        printf '0\n'
    fi
}

select_flow_rows() {
    local manifest="$1"
    local total
    local index

    total="$(stage_shard_total)"
    index="$(stage_shard_index)"

    awk -F $'\t' -v shard_total="$total" -v shard_index="$index" '
        shard_total <= 1 || ((NR - 1) % shard_total) == shard_index { print }
    ' "$manifest"
}

send_stage_mail() {
    local repo_root="$1"
    local recipient="$2"
    local subject="$3"
    local body="$4"

    if [[ -z "$recipient" ]]; then
        log_info "Skipping notification mail for ${subject}: no recipient configured."
        return 0
    fi

    if [[ "$subject" != *"ERROR"* && "${SUPPRESS_SHARD_MAILS:-false}" == "true" ]]; then
        if [[ "${FLOW_SHARD_TOTAL:-1}" =~ ^[0-9]+$ && "${FLOW_SHARD_TOTAL:-1}" -gt 1 ]]; then
            log_info "Skipping shard-level notification mail for ${subject} (SUPPRESS_SHARD_MAILS=true)."
            return 0
        fi
        if [[ "${CI_NODE_TOTAL:-1}" =~ ^[0-9]+$ && "${CI_NODE_TOTAL:-1}" -gt 1 ]]; then
            log_info "Skipping shard-level notification mail for ${subject} (SUPPRESS_SHARD_MAILS=true)."
            return 0
        fi
    fi

    local context=""
    if [[ -n "${CI_PROJECT_PATH:-}" ]]; then
        context+="Project: ${CI_PROJECT_PATH}\n"
    fi
    if [[ -n "${CI_PIPELINE_ID:-}" || -n "${CI_PIPELINE_URL:-}" ]]; then
        context+="Pipeline: ${CI_PIPELINE_ID:-unknown}"
        if [[ -n "${CI_PIPELINE_URL:-}" ]]; then
            context+=" (${CI_PIPELINE_URL})"
        fi
        context+="\n"
    fi
    if [[ -n "${CI_JOB_NAME:-}" || -n "${CI_JOB_URL:-}" ]]; then
        context+="Job: ${CI_JOB_NAME:-unknown}"
        if [[ -n "${CI_JOB_ID:-}" ]]; then
            context+=" [${CI_JOB_ID}]"
        fi
        if [[ -n "${CI_JOB_URL:-}" ]]; then
            context+=" (${CI_JOB_URL})"
        fi
        context+="\n"
    fi
    if [[ -n "$context" ]]; then
        body="${body}\n\n---\nExecution Context\n${context}"
    fi

    python3 "${repo_root}/scripts/k4_reco_val_pipeline_utils/send_mail.py" \
        --to "$recipient" \
        --subject "$subject" \
        --body "$body" || {
            log_warn "Unable to send notification mail: ${subject}"
            mark_pipeline_warning "Notification failed: ${subject}"
        }
}

save_reference_file() {
    local source_file="$1"
    local ref_dir="$2"

    [[ -f "$source_file" ]] || return 1

    mkdir -p "$ref_dir" && cp -f "$source_file" "${ref_dir}/$(basename "$source_file")" || return 1
    log_success "Reference saved: ${ref_dir}/$(basename "$source_file")"
}

pipeline_warning_file() {
    local job_key
    job_key="$(normalize_slug "${CI_JOB_NAME:-local_job}")"
    printf '%s\n' "${WORKAREA}/.pipeline-state/warnings/${job_key}.log"
}

pipeline_error_file() {
    local job_key
    job_key="$(normalize_slug "${CI_JOB_NAME:-local_job}")"
    printf '%s\n' "${WORKAREA}/.pipeline-state/errors/${job_key}.log"
}

mark_pipeline_warning() {
    local message="$1"
    local path
    path="$(pipeline_warning_file)"
    mkdir -p "$(dirname "$path")"
    printf '%s\n' "$message" >> "$path"
}

mark_pipeline_error() {
    local message="$1"
    local path
    path="$(pipeline_error_file)"
    mkdir -p "$(dirname "$path")"
    printf '%s\n' "$message" >> "$path"
}

pipeline_has_warnings() {
    find "${WORKAREA}/.pipeline-state/warnings" -type f -size +0c -print -quit 2>/dev/null | grep -q .
}

pipeline_has_errors() {
    find "${WORKAREA}/.pipeline-state/errors" -type f -size +0c -print -quit 2>/dev/null | grep -q .
}

empty_shard_exit_code() {
    if [[ "${SOFT_FAIL_ON_EMPTY_SHARD:-false}" == "true" ]]; then
        printf '0\n'
    else
        printf '1\n'
    fi
}

finalize_flow_stage() {
    local stage_name="$1"
    local stage_title="$2"
    local no_success_description="$3"
    local selected_count="$4"
    local success_count="$5"
    local warning_count="$6"
    local warning_messages_name="$7"
    local failure_messages_name="$8"
    local -n warning_messages_ref="$warning_messages_name"
    local -n failure_messages_ref="$failure_messages_name"
    local failure_count="${#failure_messages_ref[@]}"
    local message
    local repo_root
    repo_root="$(pipeline_repo_root)"

    if [[ "$selected_count" -eq 0 ]]; then
        message="No validation flows were assigned to this ${stage_name} shard."
        log_error "$message"
        mark_pipeline_error "$message"
        send_stage_mail \
            "$repo_root" \
            "$EMAIL_ADDRESSES" \
            "Key4hep validation ${stage_name} ERROR: 0/0 flows completed" \
            "${stage_title} stage summary\n\nSelected flows: 0\nSucceeded: 0\nWarnings: 0\nErrors: 1\n\n${message}\n"
        return 1
    fi

    local severity="SUCCESS"
    local empty_exit_code=0
    if [[ "$failure_count" -gt 0 || ${#warning_messages_ref[@]} -gt 0 || "$success_count" -eq 0 ]]; then
        severity="WARNING"
    fi
    if [[ "$success_count" -eq 0 ]]; then
        empty_exit_code="$(empty_shard_exit_code)"
        if [[ "$empty_exit_code" -ne 0 ]]; then
            severity="ERROR"
        fi
    fi

    local subject="Key4hep validation ${stage_name} ${severity}: ${success_count}/${selected_count} flows completed"
    local detail_text
    detail_text="$(printf '%s\n' "${warning_messages_ref[@]}" "${failure_messages_ref[@]}")"
    local body
    body=$(cat <<EOF
${stage_title} stage summary for ${repo_root}

Shard: $(( $(stage_shard_index) + 1 ))/$(stage_shard_total)
Selected flows: ${selected_count}
Succeeded: ${success_count}
Warnings: ${warning_count}
Errors: ${failure_count}

${detail_text}
EOF
)

    if [[ "$severity" == "WARNING" ]]; then
        mark_pipeline_warning "$subject"
    elif [[ "$severity" == "ERROR" ]]; then
        mark_pipeline_error "$subject"
    fi
    if [[ "$severity" != "SUCCESS" ]]; then
        send_stage_mail "$repo_root" "$EMAIL_ADDRESSES" "$subject" "$body"
    fi

    if [[ "$success_count" -eq 0 ]]; then
        if [[ "$empty_exit_code" -eq 0 ]]; then
            log_warn "${no_success_description} had no successful workflows in this shard; continuing due to SOFT_FAIL_ON_EMPTY_SHARD=true."
        else
            log_error "${no_success_description} had no successful workflows; aborting downstream stages."
        fi
        return "$empty_exit_code"
    fi
    return 0
}

# Direct Python log files to $WORKAREA/logs/ when WORKAREA is set.
if [[ -n "${WORKAREA}" ]]; then
    export K4_LOG_DIR="${WORKAREA}/logs"
    mkdir -p "${K4_LOG_DIR}"
fi

# Initialize the Key4hep stack once for each stage shell.
if [[ -n "${KEY4HEP_STACK}" ]]; then
    log_warn "Key4hep stack already loaded in this shell. Skipping source."
else
    log_info "Sourcing current key4hep stack..."
    if [[ ! -f /cvmfs/sw-nightlies.hsf.org/key4hep/setup.sh ]]; then
        log_error "Key4hep setup script is not available on this runner."
        return 1
    fi
    if [ -n "${TAG:-}" ]; then
        source /cvmfs/sw-nightlies.hsf.org/key4hep/setup.sh -r "$TAG" ||
            return 1
    else
        source /cvmfs/sw-nightlies.hsf.org/key4hep/setup.sh ||
            return 1
    fi
    log_success "Key4hep stack initialization complete."
fi
