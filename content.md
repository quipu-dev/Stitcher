# 📸 Snapshot Capture

### 💬 备注:
style: ruff and stitcher

检测到工作区发生变更。

### 📝 变更文件摘要:
```
.../src/stitcher/app/core.json                     |  4 ++
 .../src/stitcher/app/runners/index.json            | 11 +++--
 .../src/stitcher/app/runners/refactor.json         |  9 +++-
 .../stitcher-index/src/stitcher/index/indexer.json | 34 +++++++++++++++
 .../stitcher-index/src/stitcher/index/linker.json  | 16 +++++++
 .../stitcher-index/src/stitcher/index/store.json   | 10 +++++
 .../src/stitcher/adapter/python/index_adapter.json | 10 ++++-
 .../python/analysis/cst/rename_transformers.json   |  4 ++
 .../src/stitcher/refactor/engine/context.json      |  2 +
 .../src/stitcher/refactor/engine/graph.json        | 11 ++++-
 .../tests/integration/test_repro_sidecar_fqn.json  |  1 +
 .../src/stitcher/test_utils/__init__.json          |  1 +
 .../src/stitcher/test_utils/helpers.json           | 10 +++++
 .../stitcher-workspace/src/stitcher/__init__.json  |  3 ++
 .../src/stitcher/workspace/__init__.json           |  5 +++
 .../src/stitcher/workspace/workspace.json          | 51 ++++++++++++++++++++++
 .../src/stitcher/app/runners/index.py              |  2 +-
 .../src/stitcher/app/runners/refactor.py           |  3 +-
 .../tests/integration/test_refactor_internals.py   |  8 +---
 .../stitcher-index/src/stitcher/index/indexer.py   |  4 +-
 .../stitcher-index/src/stitcher/index/linker.py    |  6 +--
 .../src/stitcher/index/linker.stitcher.yaml        |  3 ++
 .../stitcher-index/src/stitcher/index/store.py     | 29 ++++--------
 .../src/stitcher/index/store.stitcher.yaml         |  6 +++
 .../tests/integration/test_indexer_aliases.py      |  3 +-
 packages/stitcher-index/tests/unit/test_indexer.py |  4 +-
 .../src/stitcher/adapter/python/index_adapter.py   |  3 +-
 .../adapter/python/index_adapter.stitcher.yaml     |  2 +
 .../python/analysis/cst/rename_transformers.py     |  6 +--
 .../src/stitcher/refactor/__init__.py              |  2 +-
 ...
 44 files changed, 236 insertions(+), 77 deletions(-)
```