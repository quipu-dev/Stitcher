# 📸 Snapshot Capture

### 💬 备注:
style: ruff and stitcher

检测到工作区发生变更。

### 📝 变更文件摘要:
```
.../stitcher-application/src/stitcher/app/core.json |  5 +++++
 .../src/stitcher/app/runners/check.json             | 11 +++++++++--
 .../src/stitcher/app/runners/init.json              | 10 ++++++++--
 .../src/stitcher/app/runners/pump.json              | 13 +++++++++----
 .../stitcher/app/services/signature_manager.json    | 21 ++++++++++++---------
 .../src/stitcher/app/runners/init.py                |  1 -
 .../src/stitcher/app/services/signature_manager.py  |  2 +-
 .../app/services/signature_manager.stitcher.yaml    |  8 --------
 .../tests/unit/test_signature_extraction.py         |  2 +-
 9 files changed, 45 insertions(+), 28 deletions(-)
```