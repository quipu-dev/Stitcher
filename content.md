# 📸 Snapshot Capture

### 💬 备注:
style: ruff and stitcher

检测到工作区发生变更。

### 📝 变更文件摘要:
```
.../src/stitcher/cli/commands/check.json           |  4 +--
 .../src/stitcher/cli/commands/pump.json            |  4 +--
 .../src/stitcher/cli/commands/refactor.json        |  4 +--
 .../src/stitcher/refactor/engine/context.json      |  4 ++-
 .../src/stitcher/refactor/engine/graph.json        |  5 ++--
 .../src/stitcher/refactor/sidecar/manager.json     | 19 ++++++++++++++
 .../src/stitcher/refactor/workspace.json           | 30 ++++++++++++++++++++++
 .../src/stitcher/test_utils/workspace.json         |  5 ++++
 .../src/stitcher/refactor/sidecar/manager.py       |  4 +--
 .../refactor/sidecar/manager.stitcher.yaml         |  4 +++
 .../src/stitcher/refactor/workspace.py             | 12 ++++-----
 .../src/stitcher/refactor/workspace.stitcher.yaml  |  8 ++++++
 .../test_monorepo_refactor_with_tests_e2e.py       |  4 +--
 .../integration/test_rename_symbol_monorepo_e2e.py |  4 +--
 .../tests/unit/refactor/test_workspace.py          | 14 ++++++----
 .../tests/unit/sidecar/test_manager.py             |  2 +-
 .../src/stitcher/test_utils/workspace.py           |  1 -
 .../stitcher/test_utils/workspace.stitcher.yaml    |  2 ++
 18 files changed, 98 insertions(+), 32 deletions(-)
```