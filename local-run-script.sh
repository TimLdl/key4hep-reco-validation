#!/bin/bash
set -e

# Color Output Configuration
# Force color if FORCE_COLOR is set, otherwise check if stdout is a terminal
if [[ -t 1 || -n "${FORCE_COLOR}" ]]; then
    RED='\033[0;31m'
    GREEN='\033[0;32m'
    YELLOW='\033[0;33m'
    BLUE='\033[0;34m'
    NC='\033[0m'
else
    RED=''
    GREEN=''
    YELLOW=''
    BLUE=''
    NC=''
fi

# Logging Helper Functions
log_error() { echo -e "${RED}[ERROR]${NC} $*" >&2; }
log_success() { echo -e "${GREEN}[OK]${NC} $*"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $*"; }
log_info() { echo -e "${BLUE}[INFO]${NC} $*"; }

# The repository root is the directory containing this script
REPO_ROOT="$(cd "$(dirname "$0")" && pwd)"

# Default Options
RUN_ONLY=false

# Keyword Argument Parsing
while [[ $# -gt 0 ]]; do
    case $1 in
        --runTask)
            RUN_TASK="$2"; shift 2 ;;
        --only)
            RUN_ONLY=true; shift ;;
        --help|-h)
            echo "Usage: $0 [--runTask TASK] [--only]"
            echo ""
            echo "  --runTask TASK  Run up to and including TASK (default: plot)"
            echo "                  Available tasks: setup, simulation, validation, plot, web"
            echo "  --only          Run only the specified task, not the full chain up to it"
            echo ""
            echo "Environment variable overrides:"
            echo "  WORKAREA                  Workspace directory (default: ~/local-k4-validation)"
            echo "  VERSIONS                  Comma-separated variant filter (default: all)"
            echo "  MAKE_REFERENCE_SAMPLE     Set to 'yes' to save histograms as references"
            echo "  STEERING_FILE_REPO        FCC-config repository URL"
            echo "  STEERING_FILE_BRANCH      FCC-config branch (default: main)"
            echo "  TAG                       Key4hep nightly tag (default: latest)"
            exit 0 ;;
        *)
            log_warn "Unknown option: $1"; shift ;;
    esac
done

# Default Values & Configuration Hierarchy
DEFAULT_ORDER="setup,simulation,validation,plot,web"
TASK_ORDER="${TASK_ORDER:-$DEFAULT_ORDER}"
RUN_TASK="${RUN_TASK:-plot}"

# Pipeline Variables (Uses env/command-line value if provided, otherwise defaults)
export STEERING_FILE_REPO="${STEERING_FILE_REPO:-https://github.com/HEP-FCC/FCC-config.git}"
export STEERING_FILE_BRANCH="${STEERING_FILE_BRANCH:-main}"
export WORKAREA="${WORKAREA:-$HOME/local-k4-validation}"
export PLOTAREA="${PLOTAREA:-plots}"
export REFERENCE_SAMPLE="${REFERENCE_SAMPLE:-references}"
export VERSIONS="${VERSIONS:-}"
export MAKE_REFERENCE_SAMPLE="${MAKE_REFERENCE_SAMPLE:-yes}"
export TAG="${TAG:-}"

# --- Resolve Execution Order Chain ---
IFS=',' read -r -a ALL_TASKS <<< "$TASK_ORDER"

TARGET_INDEX=-1
for i in "${!ALL_TASKS[@]}"; do
    if [[ "${ALL_TASKS[$i]}" == "$RUN_TASK" ]]; then
        TARGET_INDEX=$i
        break
    fi
done

if [[ $TARGET_INDEX -eq -1 ]]; then
    log_error "Target task '$RUN_TASK' is not part of the defined TASK_ORDER."
    log_warn "Allowed tasks in order: ${ALL_TASKS[*]}"
    exit 1
fi

# Build execution list (chain up to target vs single task)
TASKS_TO_RUN=()
if [[ "$RUN_ONLY" == true ]]; then
    TASKS_TO_RUN+=("${ALL_TASKS[$TARGET_INDEX]}")
else
    for ((i=0; i<=TARGET_INDEX; i++)); do
        TASKS_TO_RUN+=("${ALL_TASKS[$i]}")
    done
fi

# --- UI / Configuration Printout ---
log_info "=================================================="
log_info "        LOCAL GITLAB PIPELINE EXECUTION           "
log_info "=================================================="
log_info "Execution Chain: $(echo "${TASKS_TO_RUN[@]}" | sed 's/ / -> /g')"
log_info "--------------------------------------------------"
echo "  - WORKAREA:               $WORKAREA"
echo "  - VERSIONS FILTER:        ${VERSIONS:-[Auto-discover all]}"
echo "  - MAKE_REFERENCE_SAMPLE:  $MAKE_REFERENCE_SAMPLE"
echo "  - REPO ROOT:              $REPO_ROOT"
echo "  - TAG:                    ${TAG:-[Default/Latest]}"
echo "  - RUN ONLY SINGLE TASK:   $RUN_ONLY"
log_info "=================================================="

# --- Environment Setup ---
if [[ -z "${KEY4HEP_STACK}" ]]; then
    log_info "Sourcing Key4hep stack via cvmfs..."
    source /cvmfs/sw-nightlies.hsf.org/key4hep/setup.sh
    log_success "Key4hep stack successfully loaded."
else
    log_info "Key4hep stack was already active in this environment."
fi

# Clean or create the workspace directory safely.
# Only clear the contents if 'setup' is explicitly part of the tasks we are running.
if [[ " ${TASKS_TO_RUN[*]} " =~ " setup " ]]; then
    if [ -d "$WORKAREA" ]; then
        log_warn "Directory $WORKAREA already exists. Clearing contents for fresh setup..."
        rm -rf "$WORKAREA"/*
        log_success "Workspace cleanup completed."
    else
        mkdir -p "$WORKAREA"
        log_success "Created fresh workspace directory."
    fi
else
    mkdir -p "$WORKAREA"
    log_info "Using existing workspace directory (skipped cleanup to preserve task data)."
fi

cd "$REPO_ROOT"

# --- Centralized Job Runner Function ---
run_gitlab_job() {
    local job_name="$1"
    log_info "--------------------------------------------------"
    log_info "STARTING TASK: $job_name"
    log_info "--------------------------------------------------"

    local start_time=$(date +%s)

    gitlab-ci-local --force-shell-executor \
        --variable WORKAREA="$WORKAREA" \
        --variable PLOTAREA="$PLOTAREA" \
        --variable REFERENCE_SAMPLE="$REFERENCE_SAMPLE" \
        --variable VERSIONS="$VERSIONS" \
        --variable MAKE_REFERENCE_SAMPLE="$MAKE_REFERENCE_SAMPLE" \
        --variable STEERING_FILE_REPO="$STEERING_FILE_REPO" \
        --variable STEERING_FILE_BRANCH="$STEERING_FILE_BRANCH" \
        --variable TAG="$TAG" \
        "$job_name"

    local end_time=$(date +%s)
    log_success "COMPLETED TASK: $job_name (Duration: $((end_time - start_time))s)"
}

# --- Execute Pipeline Chain ---
for TASK in "${TASKS_TO_RUN[@]}"; do
    run_gitlab_job "$TASK"
done

log_info "=================================================="
log_success "All tasks in the execution chain finished successfully!"
log_info "=================================================="
