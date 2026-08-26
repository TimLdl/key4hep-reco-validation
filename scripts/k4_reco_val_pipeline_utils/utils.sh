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
        --body "$body" || log_warn "Unable to send notification mail: ${subject}"
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

# Direct Python log files to $WORKAREA/logs/ when WORKAREA is set.
if [[ -n "${WORKAREA}" ]]; then
    export K4_LOG_DIR="${WORKAREA}/logs"
    mkdir -p "${K4_LOG_DIR}"
fi

# Centralized, fail-soft stack initialization
if [[ -n "${KEY4HEP_STACK}" ]]; then
    log_warn "Key4hep stack already loaded in this shell. Skipping source."
else
    log_info "Sourcing current key4hep stack..."
    if [ -n "$TAG" ]; then
        source /cvmfs/sw-nightlies.hsf.org/key4hep/setup.sh -r "$TAG" || true
    else
        source /cvmfs/sw-nightlies.hsf.org/key4hep/setup.sh || true
    fi
    log_success "Key4hep stack initialization complete."
fi
