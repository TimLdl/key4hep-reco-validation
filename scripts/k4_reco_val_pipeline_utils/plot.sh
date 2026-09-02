#!/bin/bash
source "$(dirname "$0")/utils.sh"
source "$WORKAREA/version_array.txt"

COMPARISON_FAIL=0

for VERSION in "${VERSION_ARRAY[@]}"; do
    [ -z "$VERSION" ] && continue
    GEOMETRY="${VERSION%%_*}"
    cd "$WORKAREA/$GEOMETRY/$VERSION" || continue
    log_info "Plotting Histograms: $GEOMETRY ($VERSION)"

    TARGET_PLOT_DIR="$WORKAREA/$PLOTAREA/$GEOMETRY/$VERSION"

    if [ -d "$TARGET_PLOT_DIR" ]; then
        log_warn "Plot area directory already exists. Purging obsolete data..."
        rm -rf "$TARGET_PLOT_DIR"
    fi
    mkdir -p "$TARGET_PLOT_DIR"

    # Dynamically build plot input array from active particles
    IFS=',' read -r -a raw_particles <<< "${PARTICLES:-e-,mu-}"
    PLOT_INPUTS=()

    for p in "${raw_particles[@]}"; do
        p_clean="${p//[[:space:]-+]/}"
        [[ -z "$p_clean" ]] && continue

        # Map short particle codes to plot legend keys
        case "$p_clean" in
            e|electron) label="electron"; short="e" ;;
            mu|muon) label="muon"; short="mu" ;;
            pi|pion) label="pion"; short="pi" ;;
            gamma|photon) label="gamma"; short="gamma" ;;
            *) label="$p_clean"; short="$p_clean" ;;
        esac

        hist_file="${GEOMETRY}_${short}_particleGun_hist.root"

        if [[ -f "$hist_file" ]]; then
            PLOT_INPUTS+=("${label}=${hist_file}")
        else
            log_warn "Expected histogram file missing for ${label}: ${hist_file}"
        fi
    done

    if [[ ${#PLOT_INPUTS[@]} -eq 0 ]]; then
        log_error "No valid ROOT histogram files found to plot for $GEOMETRY ($VERSION)!"
        COMPARISON_FAIL=1
        continue
    fi

    log_info "Executing data plotting runner engine with inputs: ${PLOT_INPUTS[*]}"
    python "$WORKAREA/key4hep-reco-validation/scripts/detectors/k4_reco_val_utils/plotting.py" \
        --inputs "${PLOT_INPUTS[@]}" \
        --detector-config "$WORKAREA/key4hep-reco-validation/config/$GEOMETRY/$VERSION/config.yaml" \
        --style-config "$WORKAREA/key4hep-reco-validation/config/plotting.yaml" \
        --output-dir "$TARGET_PLOT_DIR"

    cmd_status=$?
    if [[ $cmd_status -ne 0 ]]; then
        log_error "Plotting rendering engine failed for $VERSION!"
        COMPARISON_FAIL=1
    else
        log_success "Plot execution completed successfully."
    fi
done
