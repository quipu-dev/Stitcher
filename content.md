# 📸 Snapshot Capture

### 💬 备注:
style: ruff and stitcher

检测到工作区发生变更。

### 📝 变更文件摘要:
```
.../src/stitcher/refactor/engine/graph.json        |  9 ++++++--
 .../refactor/operations/move_directory.json        |  4 ++++
 .../refactor/operations/rename_namespace.json      | 13 +++++++++++
 .../transforms/rename_namespace_transformer.json   | 27 ++++++++++++++++++++++
 .../src/stitcher/refactor/engine/graph.py          |  6 ++---
 .../stitcher/refactor/engine/graph.stitcher.yaml   | 16 -------------
 .../refactor/operations/rename_namespace.py        |  9 ++------
 .../transforms/rename_namespace_transformer.py     |  2 +-
 8 files changed, 56 insertions(+), 30 deletions(-)
```