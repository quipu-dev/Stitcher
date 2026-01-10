# 📸 Snapshot Capture

### 💬 备注:
style: ruff and stitcher

检测到工作区发生变更。

### 📝 变更文件摘要:
```
.../src/stitcher/__init__.json                     |  3 ++
 .../stitcher-cli/src/stitcher/__init__.json        |  3 ++
 .../stitcher-common/src/stitcher/__init__.json     |  3 ++
 .../stitcher-refactor/src/stitcher/__init__.json   |  3 ++
 .../stitcher-spec/src/stitcher/__init__.json       |  3 ++
 .../stitcher-test-utils/src/stitcher/__init__.json |  3 ++
 .../stitcher-application/src/stitcher/__init__.py  |  1 -
 packages/stitcher-cli/src/stitcher/__init__.py     |  1 -
 packages/stitcher-common/src/stitcher/__init__.py  |  1 -
 packages/stitcher-config/src/stitcher/__init__.py  |  1 -
 packages/stitcher-index/src/stitcher/__init__.py   |  2 +-
 packages/stitcher-index/src/stitcher/index/db.py   | 13 ++++---
 .../stitcher-index/src/stitcher/index/store.py     | 12 +++---
 .../stitcher-index/src/stitcher/index/types.py     |  2 +-
 packages/stitcher-index/tests/conftest.py          |  6 ++-
 packages/stitcher-index/tests/unit/test_store.py   | 44 ++++++++++++----------
 .../src/stitcher/__init__.py                       |  1 -
 .../src/stitcher/__init__.py                       |  1 -
 .../stitcher-refactor/src/stitcher/__init__.py     |  1 -
 packages/stitcher-spec/src/stitcher/__init__.py    |  1 -
 packages/stitcher-stubgen/src/stitcher/__init__.py |  1 -
 .../stitcher-test-utils/src/stitcher/__init__.py   |  1 -
 22 files changed, 61 insertions(+), 46 deletions(-)
```