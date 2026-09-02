#!/usr/bin/env bash
set -e

DETECTORS=(
"ALLEGRO_o1_v03"
# "IDEA_o1_v03"
)

REF_BASE_DIR="references"

for DET in "${DETECTORS[@]}"; do
    DET_FAMILY="${DET%%_*}"
    CONFIG_DIR="config/${DET_FAMILY}/${DET}"

    INPUT_FILE="data/${DET_FAMILY}/${DET}/${DET_FAMILY}_particleGun_digi.root"
    OUTPUT_FILE="output/${DET_FAMILY}/${DET}/${DET_FAMILY}_particleGun_hist.root"
    REF_DIR="${REF_BASE_DIR}/${DET_FAMILY}/${DET}"

    echo "================================================================================"
    echo " Processing Detector: ${DET}"
    echo "================================================================================"

    echo "==> Running histogram extraction for ${DET}..."
    python3 "scripts/detectors/${DET_FAMILY}/${DET}/hist.py" \
        --input "${INPUT_FILE}" \
        --output "${OUTPUT_FILE}"

    echo "==> Rendering plots with reference comparison for ${DET}..."
    for CONFIG_PATH in "${CONFIG_DIR}"/*.yaml; do
        [ -f "${CONFIG_PATH}" ] || continue

        python3 scripts/detectors/k4_reco_val_utils/plotting.py \
            --inputs "data=${OUTPUT_FILE}" \
            --style-config config/plotting.yaml \
            --detector-config "${CONFIG_PATH}" \
            --ref-dir "${REF_DIR}" \
            --output-dir "plots/${DET_FAMILY}/${DET}"
    done
done

echo "==> Local validation run completed successfully."
