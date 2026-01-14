# 📸 Snapshot Capture

检测到工作区发生变更。

### 📝 变更文件摘要:
```
.../src/stitcher/analysis/graph/algo/__init__.py   |  2 +-
 .../src/stitcher/analysis/graph/algo/cycles.py     | 29 ++++++----------------
 .../analysis/graph/algo/cycles.stitcher.yaml       |  2 ++
 .../src/stitcher/analysis/graph/algorithms.py      |  3 +--
 .../analysis/graph/algorithms.stitcher.yaml        | 13 ++++++++--
 .../rules/architecture/circular_dependency.py      | 14 +++++++----
 packages/stitcher-analysis/stitcher.lock           | 12 +++++++++
 .../src/stitcher/app/runners/check/reporter.py     |  8 +++---
 packages/stitcher-application/stitcher.lock        | 20 ++++++++++++---
 9 files changed, 64 insertions(+), 39 deletions(-)
```