# 📸 Snapshot Capture

### 💬 备注:
style: ruff and stitcher

检测到工作区发生变更。

### 📝 变更文件摘要:
```
packages/pyneedle-pointer/stitcher.lock            |  89 +++
 packages/pyneedle-runtime/stitcher.lock            | 133 ++++
 packages/pyneedle-spec/stitcher.lock               |  91 +++
 packages/stitcher-analysis/stitcher.lock           | 203 ++++++
 .../src/stitcher/app/core.stitcher.yaml            |   2 -
 .../src/stitcher/app/runners/check/resolver.py     |  50 +-
 .../src/stitcher/app/runners/check/subject.py      |  10 +-
 .../src/stitcher/app/runners/init.py               |   8 +-
 .../src/stitcher/app/runners/pump/executor.py      |  16 +-
 packages/stitcher-application/stitcher.lock        | 619 +++++++++++++++++
 packages/stitcher-cli/stitcher.lock                | 154 +++++
 packages/stitcher-common/stitcher.lock             | 292 ++++++++
 packages/stitcher-config/stitcher.lock             |  45 ++
 packages/stitcher-index/stitcher.lock              | 135 ++++
 .../src/stitcher/lang/python/uri.py                |  12 +-
 .../src/stitcher/lang/python/uri.stitcher.yaml     |  18 +-
 packages/stitcher-lang-python/stitcher.lock        | 735 +++++++++++++++++++++
 .../src/stitcher/lang/sidecar/adapter.py           |   4 +-
 .../src/stitcher/lang/sidecar/lock_manager.py      |  12 +-
 .../src/stitcher/refactor/engine/intent.py         |   2 -
 .../stitcher/refactor/engine/intent.stitcher.yaml  |   2 +
 .../src/stitcher/refactor/engine/planner.py        |  63 +-
 .../stitcher/refactor/operations/move_directory.py |   4 +-
 .../src/stitcher/refactor/operations/move_file.py  |   8 +-
 .../stitcher/refactor/operations/rename_symbol.py  |  16 +-
 packages/stitcher-refactor/stitcher.lock           | 264 ++++++++
 .../tests/integration/test_debug_rename_failure.py |   6 +-
 .../integration/test_monorepo_refactor_e2e.py      |  15 +-
 .../tests/integration/test_move_directory_e2e.py   |  13 +-
 .../test_move_directory_monorepo_e2e.py            |  42 +-
 ...
 50 files changed, 4057 insertions(+), 222 deletions(-)
```