# 📸 Snapshot Capture

检测到工作区发生变更。

### 📝 变更文件摘要:
```
.../src/stitcher/common/transaction.json           | 138 +++++++++++++++++
 .../src/stitcher/refactor/engine/transaction.json  | 138 -----------------
 .../src/stitcher/common/transaction.py             | 169 +++++++++++++++++++++
 .../src/stitcher/common/transaction.stitcher.yaml  |   3 +
 .../src/stitcher/refactor/engine/__init__.py       |   2 +-
 .../src/stitcher/refactor/engine/planner.py        |   2 +-
 .../src/stitcher/refactor/engine/renamer.py        |   2 +-
 .../src/stitcher/refactor/engine/transaction.py    | 169 ---------------------
 .../refactor/engine/transaction.stitcher.yaml      |   3 -
 .../refactor/operations/rename_namespace.py        |   2 +-
 .../integration/test_bug_init_relative_import.py   |   2 +-
 .../test_bug_relative_import_refactor.py           |   2 +-
 .../tests/integration/test_debug_rename_failure.py |   4 +-
 .../test_fail_concurrent_move_and_rename.py        |   2 +-
 .../integration/test_monorepo_refactor_e2e.py      |   2 +-
 .../test_monorepo_refactor_with_tests_e2e.py       |   2 +-
 .../tests/integration/test_move_directory_e2e.py   |   2 +-
 .../test_move_directory_monorepo_e2e.py            |   2 +-
 .../tests/integration/test_move_file_e2e.py        |   2 +-
 .../integration/test_move_nested_directory_e2e.py  |   2 +-
 .../tests/integration/test_rename_e2e.py           |   2 +-
 .../test_rename_namespace_pkg_failure.py           |   2 +-
 .../integration/test_rename_symbol_definition.py   |   2 +-
 .../integration/test_rename_symbol_monorepo_e2e.py |   2 +-
 .../test_rename_transformer_advanced.py            |   2 +-
 .../tests/integration/test_transaction_fs.py       |   2 +-
 .../tests/unit/test_rename_operation.py            |   2 +-
 .../tests/unit/test_transaction.py                 |   2 +-
 28 files changed, 333 insertions(+), 333 deletions(-)
```