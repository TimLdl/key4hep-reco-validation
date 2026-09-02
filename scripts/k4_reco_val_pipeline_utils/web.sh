#!/bin/bash
source "$(dirname "$0")/utils.sh"

source "$WORKAREA/version_array.txt"
cd "$WORKAREA" || exit 1

rel=$(realpath "$(dirname "$KEY4HEP_STACK")/../../")
log_info "Active Spack release tracking base context: $rel"

echo "key4hep-spack: $(cat $rel/.key4hep-spack-commit)" > metadata.yaml
echo "spack: $(cat $rel/.spack-commit)" >> metadata.yaml
echo "nightly: $rel" >> metadata.yaml

for VERSION in "${VERSION_ARRAY[@]}"; do
    [ -z "$VERSION" ] && continue
    GEOMETRY="${VERSION%%_*}"
    cp metadata.yaml "$WORKAREA/$PLOTAREA/$GEOMETRY/$VERSION"
done

log_info "Compiling statistical summary display interfaces..."

RECO_VAL_DIR="$WORKAREA/key4hep-reco-validation"

python3 "$RECO_VAL_DIR/scripts/web/build_website.py" \
    --web-config "$RECO_VAL_DIR/config/web.yaml" \
    --templates-dir "$RECO_VAL_DIR/web/templates" \
    --static-dir "$RECO_VAL_DIR/web/static" \
    --plots-dir "$WORKAREA/$PLOTAREA" \
    --output-dir "$WORKAREA/$PLOTAREA"

log_success "Web asset compilation process completed cleanly."
