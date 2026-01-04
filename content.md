# 📸 Snapshot Capture

### 💬 备注:
style: ruff and stitcher

检测到工作区发生变更。

### 📝 变更文件摘要:
```
.../src/stitcher/refactor/engine/graph.json        | 16 +++++-
 .../stitcher/refactor/operations/move_file.json    | 18 +++++++
 .../src/stitcher/refactor/engine/graph.py          | 52 +++++++-----------
 .../stitcher/refactor/engine/graph.stitcher.yaml   | 16 ++++++
 .../src/stitcher/refactor/operations/move_file.py  | 19 +++----
 .../refactor/operations/move_file.stitcher.yaml    |  3 ++
 .../tests/integration/test_move_file_e2e.py        | 62 +++++++++++-----------
 .../tests/unit/engine/test_graph_visitor.py        | 20 +++----
 8 files changed, 118 insertions(+), 88 deletions(-)
```