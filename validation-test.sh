#!/usr/bin/env bash
# Local standalone validation test — runs histogram extraction and plotting
# for all discovered validation flows without running simulation.
#
# Prerequisites:
#   - Key4hep stack sourced (or CVMFS available)
#   - Pre-existing digi ROOT files under DATA_DIR/<DETECTOR>/<VARIANT>/
#     named <DETECTOR>_<output_tag>_particleGun_digi.root
#
# Usage:
#   ./validation-test.sh [--data-dir DIR] [--output-dir DIR] [--versions FILTER]
set -e

REPO_ROOT="$(cd "$(dirname "$0")" && pwd)"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[0;33m'; BLUE='\033[0;34m'; NC='\033[0m'
log_error()   { echo -e "${RED}[ERROR]${NC} $*" >&2; }
log_success() { echo -e "${GREEN}[OK]${NC} $*"; }
log_warn()    { echo -e "${YELLOW}[WARN]${NC} $*"; }
log_info()    { echo -e "${BLUE}[INFO]${NC} $*"; }

# --- Defaults ---
DATA_DIR="${DATA_DIR:-$REPO_ROOT/data}"
OUTPUT_DIR="${OUTPUT_DIR:-$REPO_ROOT/test-output}"
HIST_ROOT="${OUTPUT_DIR}/hist"
PLOT_ROOT="${OUTPUT_DIR}/plots"
REF_DIR="${REF_DIR:-$REPO_ROOT/references}"
VERSIONS="${VERSIONS:-}"

while [[ $# -gt 0 ]]; do
    case $1 in
        --data-dir)    DATA_DIR="$2";    shift 2 ;;
        --output-dir)  OUTPUT_DIR="$2";  shift 2 ;;
        --ref-dir)     REF_DIR="$2";     shift 2 ;;
        --versions)    VERSIONS="$2";    shift 2 ;;
        --help|-h)
            echo "Usage: $0 [--data-dir DIR] [--output-dir DIR] [--ref-dir DIR] [--versions FILTER]"
            echo ""
            echo "  --data-dir    Directory containing pre-existing digi ROOT files (default: ./data)"
            echo "  --output-dir  Root directory for outputs (hist under ./hist, plots under ./plots)"
            echo "  --ref-dir     Directory containing reference histograms for comparison (default: ./references)"
            echo "  --versions    Comma-separated variant filter, e.g. ALLEGRO_o1_v03 (default: all)"
            exit 0 ;;
        *) log_warn "Unknown option: $1"; shift ;;
    esac
done

# --- Key4hep stack ---
if [[ -z "${KEY4HEP_STACK}" ]]; then
    log_info "Sourcing Key4hep stack via CVMFS..."
    source /cvmfs/sw-nightlies.hsf.org/key4hep/setup.sh
fi

mkdir -p "$HIST_ROOT" "$PLOT_ROOT"

# --- Discover validation flows ---
log_info "Discovering validation flows..."
MANIFEST="$(mktemp /tmp/validation_flows_XXXXXX.tsv)"
trap 'rm -f "$MANIFEST"' EXIT

python3 "$REPO_ROOT/scripts/k4_reco_val_pipeline_utils/config_discovery.py" \
    --repo-root "$REPO_ROOT" \
    --versions "${VERSIONS}" \
    --format tsv \
    --output "$MANIFEST"

flow_count=$(wc -l < "$MANIFEST")
log_info "Found ${flow_count} validation flow(s)."

FAIL=0

while IFS=$'\t' read -r detector version slug validation config_path config_dir config_rel_dir particle output_tag energy seed sim_script hist_script; do
    [[ -z "$detector" ]] && continue

    digi_file="$DATA_DIR/$detector/$version/${detector}_${output_tag}_particleGun_digi.root"
    hist_file="$HIST_ROOT/$detector/$version/${detector}_${validation}_particleGun_hist.root"
    plot_dir="$PLOT_ROOT/$slug"
    variant_ref_dir="$REF_DIR/$detector/$version"

    mkdir -p "$(dirname "$hist_file")"

    if [[ ! -f "$digi_file" ]]; then
        log_warn "Skipping '${validation}' (${detector} ${version}): digi file not found at $digi_file"
        continue
    fi

    log_info "==> Extracting histograms: ${detector} ${version} / ${validation}"
    python3 "$hist_script" \
        --input "$digi_file" \
        --output "$hist_file" \
        --config-source "$config_path" || { log_error "Histogram extraction failed for ${validation}!"; FAIL=1; continue; }

    log_info "==> Rendering plots: ${detector} ${version} / ${validation}"
    ref_args=()
    if [[ -d "$variant_ref_dir" ]]; then
        ref_args=(--ref-dir "$variant_ref_dir")
    fi

    python3 "$REPO_ROOT/scripts/detectors/k4_reco_val_utils/plotting.py" \
        --inputs "${validation}=${hist_file}" \
        --detector-config "$config_path" \
        --style-config "$REPO_ROOT/config/plotting.yaml" \
        --output-dir "$PLOT_ROOT" \
        "${ref_args[@]}" || { log_error "Plot rendering failed for ${validation}!"; FAIL=1; continue; }

    log_success "Completed: ${detector} ${version} / ${validation} -> $plot_dir"
done < "$MANIFEST"

if [[ $FAIL -ne 0 ]]; then
    log_error "One or more validation flows failed."
    exit 1
fi

log_success "All validation flows completed. Output: $OUTPUT_DIR"
