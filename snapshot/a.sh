#!/bin/bash
set -e

# Define files to be patched
APP_TEST_FILES=(
    "packages/stitcher-application/tests/unit/test_doc_manager.py"
    "packages/stitcher-application/tests/unit/test_doc_manager_strategies.py"
    "packages/stitcher-application/tests/unit/test_doc_overlay.py"
    "packages/stitcher-application/tests/unit/test_docstring_hybrid.py"
    "packages/stitcher-application/tests/unit/test_execution_planner.py"
)

# Common sed operations
IMPORT_SED='1 a from stitcher.lang.python.uri import PythonURIGenerator'
DM_SED="s/DocumentManager(root_path=tmp_path)/DocumentManager(root_path=tmp_path, uri_generator=PythonURIGenerator())/g"
DM_SED2="s/DocumentManager(tmp_path)/DocumentManager(tmp_path, uri_generator=PythonURIGenerator())/g"
SA_SED="s/SidecarAdapter(root_path=tmp_path)/SidecarAdapter(root_path=tmp_path, uri_generator=PythonURIGenerator())/g"
EXEC_DM_SED="s/doc_manager=DocumentManager(root_path=tmp_path)/doc_manager=DocumentManager(root_path=tmp_path, uri_generator=PythonURIGenerator())/g"

for file in "${APP_TEST_FILES[@]}"; do
    sed -i "$IMPORT_SED" "$file"
    sed -i "$DM_SED" "$file"
    sed -i "$DM_SED2" "$file"
    sed -i "$SA_SED" "$file"
    sed -i "$EXEC_DM_SED" "$file"
done

# Special case for the fixture in test_doc_manager_strategies.py
sed -i "s/return DocumentManager(root)/return DocumentManager(root, uri_generator=PythonURIGenerator())/g" "packages/stitcher-application/tests/unit/test_doc_manager_strategies.py"