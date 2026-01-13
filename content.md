# 📸 Snapshot Capture

检测到工作区发生变更。

### 📝 变更文件摘要:
```
.../src/stitcher/app/runners/pump/executor.py               |  4 +---
 .../tests/integration/test_check_interactive_flow.py        |  1 +
 .../tests/integration/test_check_state_machine.py           |  2 ++
 .../stitcher-lang-python/src/stitcher/lang/python/uri.py    |  2 +-
 .../src/stitcher/lang/sidecar/signature_manager.py          |  2 +-
 .../src/stitcher/lang/sidecar/transform.py                  |  5 +----
 .../stitcher-lang-sidecar/tests/test_signature_manager.py   |  6 ++++--
 .../tests/integration/test_debug_rename_failure.py          | 13 ++++---------
 .../tests/integration/test_monorepo_refactor_e2e.py         | 10 ++++------
 .../tests/integration/test_move_directory_e2e.py            |  8 +++-----
 .../tests/integration/test_move_directory_monorepo_e2e.py   | 12 +++++-------
 .../tests/integration/test_move_nested_directory_e2e.py     |  7 ++++---
 .../test_refactor_move_updates_suri_in_signatures.py        |  5 +----
 .../stitcher-refactor/tests/integration/test_rename_e2e.py  |  5 +++--
 .../tests/integration/test_rename_suri_update.py            | 13 ++++++-------
 .../tests/integration/test_rename_symbol_monorepo_e2e.py    |  6 ++----
 .../stitcher-test-utils/src/stitcher/test_utils/helpers.py  |  3 +--
 .../stitcher-workspace/src/stitcher/workspace/workspace.py  |  2 +-
 18 files changed, 45 insertions(+), 61 deletions(-)
```