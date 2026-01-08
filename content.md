# 📸 Snapshot Capture

### 💬 备注:
style: ruff and stitcher

检测到工作区发生变更。

### 📝 变更文件摘要:
```
.../src/stitcher/app/core.json                     |  9 ++++
 .../src/stitcher/app/runners/check.json            | 28 ++++++++--
 .../src/stitcher/app/runners/coverage.json         | 16 ++++--
 .../src/stitcher/app/runners/generate.json         |  4 ++
 .../src/stitcher/app/runners/init.json             |  8 ++-
 .../src/stitcher/app/runners/pump.json             |  8 ++-
 .../src/stitcher/app/runners/transform.json        | 12 +++--
 .../src/stitcher/app/services/doc_manager.json     |  6 +++
 .../stitcher-application/src/stitcher/app/core.py  | 60 +++++++++++-----------
 .../src/stitcher/app/runners/check.py              |  8 +--
 .../src/stitcher/app/runners/coverage.py           |  2 +-
 .../src/stitcher/app/runners/generate.py           |  2 +-
 .../src/stitcher/app/runners/init.py               |  2 +-
 .../src/stitcher/app/runners/pump.py               |  6 +--
 .../src/stitcher/app/runners/transform.py          |  2 +-
 .../src/stitcher/app/services/doc_manager.py       |  1 -
 .../app/services/doc_manager.stitcher.yaml         |  3 +-
 .../src/stitcher/adapter/python/__init__.py        |  2 +-
 18 files changed, 116 insertions(+), 63 deletions(-)
```