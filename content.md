# 📸 Snapshot Capture

### 💬 备注:
style: ruff and stitcher

检测到工作区发生变更。

### 📝 变更文件摘要:
```
.../stitcher-index/src/stitcher/index/store.json     |  4 ++--
 .../src/stitcher/lang/python/analysis/models.json    |  2 ++
 .../src/stitcher/refactor/operations/base.json       | 20 ++++++++++++++++++--
 .../stitcher-spec/src/stitcher/spec/storage.json     |  4 ++--
 .../src/stitcher/analysis/semantic/graph.py          |  3 ++-
 .../src/stitcher/lang/sidecar/adapter.py             |  8 ++++----
 .../src/stitcher/lang/sidecar/parser.py              | 10 +++++-----
 .../tests/unit/test_sidecar_adapter.py               |  3 +--
 .../src/stitcher/refactor/engine/planner.py          |  8 ++++----
 .../src/stitcher/refactor/operations/base.py         | 15 +--------------
 .../stitcher/refactor/operations/base.stitcher.yaml  |  9 +++++++++
 .../tests/integration/test_rename_e2e.py             |  5 +----
 .../unit/operations/test_sidecar_update_mixin.py     |  4 ++--
 13 files changed, 53 insertions(+), 42 deletions(-)
```