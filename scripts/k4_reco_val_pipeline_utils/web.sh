#!/bin/bash
source "$(dirname "$0")/utils.sh"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
FLOW_MANIFEST="$WORKAREA/validation_flows.tsv"
GENERATED_WEB_CONFIG="$WORKAREA/generated_web.yaml"
WEB_OUTPUT_DIR="$WORKAREA/web"
cd "$WORKAREA" || exit 1

if [[ ! -f "$FLOW_MANIFEST" ]]; then
    log_error "Validation flow manifest not found: $FLOW_MANIFEST"
    exit 1
fi

if [[ ! -f "$GENERATED_WEB_CONFIG" ]]; then
    log_error "Generated web config not found: $GENERATED_WEB_CONFIG (was setup.sh run?)"
    exit 1
fi

rel=$(realpath "$(dirname "$KEY4HEP_STACK")/../../")
log_info "Active Spack release tracking base context: $rel"

echo "key4hep-spack: $(cat "$rel/.key4hep-spack-commit")" > metadata.yaml
echo "spack: $(cat "$rel/.spack-commit")" >> metadata.yaml
echo "nightly: $rel" >> metadata.yaml

selected_count=0

while IFS=$'\t' read -r detector version _; do
    [[ -z "$detector" || -z "$version" ]] && continue
    ((selected_count += 1))
    mkdir -p "$WORKAREA/$PLOTAREA/$detector/$version"
    cp metadata.yaml "$WORKAREA/$PLOTAREA/$detector/$version"
done < <(awk -F '\t' '!seen[$1 FS $2]++ {print $1 "\t" $2 "\t" $3}' "$FLOW_MANIFEST")

log_info "Building validation website..."
mkdir -p "$WEB_OUTPUT_DIR"
build_status=0
python3 "${REPO_ROOT}/scripts/web/build_website.py" \
    --web-config "$GENERATED_WEB_CONFIG" \
    --templates-dir "${REPO_ROOT}/web/templates" \
    --static-dir "${REPO_ROOT}/web/static" \
    --plots-dir "$WORKAREA/$PLOTAREA" \
    --output-dir "$WEB_OUTPUT_DIR" || build_status=$?

subject="Key4hep validation website"
if [[ $build_status -ne 0 ]]; then
    subject+=" WARNING"
else
    subject+=" SUCCESS"
fi

body=$(cat <<EOF
Web stage summary for ${REPO_ROOT}

Selected detector versions: ${selected_count}
Build exit code: ${build_status}
EOF
)

if [[ $build_status -ne 0 ]]; then
    mark_pipeline_warning "Web build returned non-zero exit code (${build_status})."
    send_stage_mail "$REPO_ROOT" "$EMAIL_ADDRESSES" "$subject" "$body"
    log_warn "Website build reported a non-zero exit code (${build_status}); continuing with warning mail."
else
    log_success "Website built successfully."
fi
