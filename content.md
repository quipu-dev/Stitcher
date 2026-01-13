# 📸 Snapshot Capture

检测到工作区发生变更。

### 📝 变更文件摘要:
```
.../src/stitcher/refactor/engine/planner.py        | 115 +++++----------------
 .../tests/integration/test_repro_sidecar_fqn.py    |   2 +
 .../integration/test_bug_init_relative_import.py   |   2 +
 .../test_bug_relative_import_refactor.py           |   2 +
 .../tests/integration/test_debug_rename_failure.py |   2 +
 .../test_fail_concurrent_move_and_rename.py        |   2 +
 .../integration/test_monorepo_refactor_e2e.py      |   2 +
 .../test_monorepo_refactor_with_tests_e2e.py       |   2 +
 .../tests/integration/test_move_directory_e2e.py   |   2 +
 .../test_move_directory_monorepo_e2e.py            |   2 +
 .../tests/integration/test_move_file_e2e.py        |   2 +
 .../integration/test_move_nested_directory_e2e.py  |   2 +
 .../tests/integration/test_rename_e2e.py           |   2 +
 .../test_rename_namespace_pkg_failure.py           |   2 +
 .../tests/integration/test_rename_suri_update.py   |   2 +
 .../integration/test_rename_symbol_definition.py   |   4 +
 .../integration/test_rename_symbol_monorepo_e2e.py |   2 +
 .../test_rename_transformer_advanced.py            |   2 +
 .../tests/unit/engine/test_planner_merging.py      |   6 ++
 19 files changed, 66 insertions(+), 91 deletions(-)
```