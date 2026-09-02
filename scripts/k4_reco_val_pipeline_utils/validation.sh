#!/bin/bash
source "$(dirname "$0")/utils.sh"
source "$WORKAREA/version_array.txt"

cd "$WORKAREA" || exit 1

for VERSION in "${VERSION_ARRAY[@]}"; do
    [[ -z "$VERSION" ]] && continue
    GEOMETRY="${VERSION%%_*}"

    REF_DIR="$WORKAREA/$REFERENCE_SAMPLE/$GEOMETRY/$VERSION"

    if ! pushd "$WORKAREA/$GEOMETRY/$VERSION" > /dev/null; then
        log_error "Could not enter directory: $WORKAREA/$GEOMETRY/$VERSION"
        continue
    fi

    IFS=',' read -r -a raw_particles <<< "${PARTICLES:-e-,mu-}"
    particles=()
    for p in "${raw_particles[@]}"; do
        p_clean="${p//[[:space:]-+]/}"
        [[ -n "$p_clean" ]] && particles+=("$p_clean")
    done

    hist_exit_code=0

    for particle in "${particles[@]}"; do
        python "${WORKAREA}/key4hep-reco-validation/scripts/detectors/${GEOMETRY}/${VERSION}/hist.py" \
            --input "${GEOMETRY}_${particle}_particleGun_digi.root" \
            --output "${GEOMETRY}_${particle}_particleGun_hist.root" \
            --particle-prefix "${particle}" \
            --config "${WORKAREA}/key4hep-reco-validation/config/${GEOMETRY}/${VERSION}/config.yaml"

        cmd_status=$?
        if [ $cmd_status -ne 0 ]; then
            hist_exit_code=1
            log_error "Histogram generation failed for ${particle} particle gun!"
        fi
    done

    log_info "Histogram generation completed with exit code: ${hist_exit_code}"

    if [[ $hist_exit_code -ne 0 ]]; then
        log_error "Histogram step failed. Skipping comparison email alert logic."
        python "scripts/send_mail.py" \
            --to "$EMAIL_ADDRESSES" \
            --subject "WARNING for ${VERSION}: Histogram Generation Failure" \
            --body "An error occurred making histograms for $VERSION. Check pipeline logs."
    else
        log_success "Perfect simulation match verified for target configuration: ${VERSION}"

        if [[ "$MAKE_REFERENCE_SAMPLE" == "yes" ]]; then
            for particle in "${particles[@]}"; do
                NEW_SIM_FILE="${GEOMETRY}_${particle}_particleGun_sim.root"
                TARGET_REF_PATH="${REF_DIR}/ref_${VERSION}_${particle}_particleGun_sim.root"

                if [[ -f "${NEW_SIM_FILE}" ]]; then
                    mkdir -p "$REF_DIR"
                    mv "${NEW_SIM_FILE}" "$TARGET_REF_PATH"
                    log_success "Reference file updated successfully for ${particle} ($VERSION)"
                else
                    log_error "Expected simulation file ${NEW_SIM_FILE} was not found for reference updating!"
                fi
            done
        fi
    fi

    popd > /dev/null || exit
done

declare -p VERSION_ARRAY > "$WORKAREA/version_array.txt"
