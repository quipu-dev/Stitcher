#!/bin/bash
set -e

# Define files to be patched
SIDECAR_TEST_FILES=(
    "packages/stitcher-lang-sidecar/tests/unit/test_sidecar_adapter.py"
    "packages/stitcher-lang-sidecar/tests/unit/test_transform.py"
)

# Common sed operations
IMPORT_SED='1 a from stitcher.lang.python.uri import PythonURIGenerator'
SA_SED="s/SidecarAdapter(root_path=tmp_path)/SidecarAdapter(root_path=tmp_path, uri_generator=PythonURIGenerator())/g"
ST_SED="s/SidecarTransformer()/SidecarTransformer(uri_generator=PythonURIGenerator())/g"

for file in "${SIDECAR_TEST_FILES[@]}"; do
    sed -i "$IMPORT_SED" "$file"
    sed -i "$SA_SED" "$file"
    sed -i "$ST_SED" "$file"
done