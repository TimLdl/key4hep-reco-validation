#!/bin/bash
source "$(dirname "$0")/utils.sh"
source "$WORKAREA/version_array.txt"

UPDATED_VERSION_ARRAY=()

for VERSION in "${VERSION_ARRAY[@]}"; do
    [[ -z "$VERSION" ]] && continue

    GEOMETRY="${VERSION%%_*}"
    log_info "Processing Geometry: $GEOMETRY - Version: $VERSION"

    if ! pushd "$WORKAREA/$GEOMETRY/$VERSION" > /dev/null; then
        log_error "Could not enter directory: $WORKAREA/$GEOMETRY/$VERSION"
        continue
    fi

    job_script="${WORKAREA}/key4hep-reco-validation/scripts/detectors/${GEOMETRY}/${VERSION}/sim_digi.sh"

    exit_code=0

    IFS=',' read -r -a raw_particles <<< "${PARTICLES:-e-,mu-}"
    particles=()
    for p in "${raw_particles[@]}"; do
        p_clean="${p//[[:space:]]/}"
        [[ -n "$p_clean" ]] && particles+=("$p_clean")
    done

    for p in "${particles[@]}"; do
        output_name="${p//[-+]/}"

        log_info "Running script execution for ${p} particleGun..."

        ( source "$job_script" --nEvents ${NUMBER_OF_EVENTS} --particle "$p" --energy "10*GeV" --outputFile "${output_name}_particleGun" --seed 42 )
        cmd_status=$?

        log_info "Script finished with exit code: ${cmd_status}"

        if [ $cmd_status -ne 0 ]; then
            exit_code=1
            log_error "Execution failed for ${p} particle gun!"
        else
            if [[ "$MAKE_REFERENCE_SAMPLE" == "yes" ]]; then
                ref_dir="$WORKAREA/$REFERENCE_SAMPLE/$GEOMETRY/$VERSION"
                mkdir -p "$ref_dir"

                SIM_FILE="${GEOMETRY}_${output_name}_particleGun_sim.root"

                if [[ -f "${SIM_FILE}" ]]; then
                    cp "${SIM_FILE}" "${ref_dir}/ref_${VERSION}_${output_name}_particleGun_sim.root"
                    log_success "Simulation reference sample generated successfully for ${p} ($VERSION)"
                else
                    log_error "Simulation file ${SIM_FILE} not found in $(pwd)!"
                fi
            fi
        fi
    done

    log_info "All script executions completed with final exit code: ${exit_code}"

    if [[ $exit_code -ne 0 ]]; then
        log_error "Execution failed for $VERSION. Sending warning notification..."

        python "scripts/send_mail.py" \
            --to "$EMAIL_ADDRESSES" \
            --subject "WARNING for $VERSION: error during script execution!" \
            --body "An error occurred when executing the script for $VERSION: either a script crashed or the output file was not produced."
    else
        UPDATED_VERSION_ARRAY+=("$VERSION")
    fi

    popd > /dev/null || exit
done

VERSION_ARRAY=("${UPDATED_VERSION_ARRAY[@]}")
declare -p VERSION_ARRAY > "$WORKAREA/version_array.txt"
