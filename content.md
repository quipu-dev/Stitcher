# 📸 Snapshot Capture

检测到工作区发生变更。

### 📝 变更文件摘要:
```
.../src/stitcher/refactor/engine/intent.py         |  1 +
 .../src/stitcher/refactor/engine/planner.py        | 48 +++++++++++++++-------
 .../src/stitcher/refactor/engine/renamer.py        |  2 +-
 .../src/stitcher/refactor/engine/transaction.py    | 23 ++++++-----
 .../src/stitcher/refactor/operations/base.py       |  3 +-
 .../stitcher/refactor/operations/move_directory.py | 46 ++++++++++++++-------
 .../src/stitcher/refactor/operations/move_file.py  |  2 +-
 .../stitcher/refactor/operations/rename_symbol.py  |  2 +-
 .../operations/transforms/rename_transformer.py    |  2 +-
 .../integration/test_bug_init_relative_import.py   | 17 ++++----
 .../test_bug_relative_import_refactor.py           | 25 +++++------
 .../test_fail_concurrent_move_and_rename.py        | 38 +++++++++--------
 .../tests/integration/test_rename_e2e.py           |  2 +-
 .../integration/test_rename_symbol_definition.py   |  2 +-
 .../tests/unit/engine/test_transaction_rebase.py   | 33 ++++++++-------
 .../tests/unit/test_rename_operation.py            |  2 +-
 16 files changed, 146 insertions(+), 102 deletions(-)
```