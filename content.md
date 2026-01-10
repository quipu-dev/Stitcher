# 📸 Snapshot Capture

### 💬 备注:
style: ruff and stitcher

检测到工作区发生变更。

### 📝 变更文件摘要:
```
.../stitcher-application/src/stitcher/app/core.json |  5 +++--
 .../src/stitcher/app/services/doc_manager.json      |  1 +
 .../stitcher/app/services/signature_manager.json    |  1 +
 .../src/stitcher/common/interfaces.json             |  4 ++++
 .../src/stitcher/common/services/__init__.json      |  3 +++
 .../common/services/asset_path_resolver.json        | 21 +++++++++++++++++++++
 .../stitcher-config/src/stitcher/__init__.json      |  3 +++
 .../src/stitcher/refactor/sidecar/manager.json      |  1 +
 .../stitcher-spec/src/stitcher/spec/protocols.json  |  4 ++--
 .../src/stitcher/app/core.stitcher.yaml             |  2 --
 .../app/services/signature_manager.stitcher.yaml    |  2 --
 .../src/stitcher/common/interfaces.py               |  2 --
 .../stitcher/common/services/asset_path_resolver.py | 15 ---------------
 .../services/asset_path_resolver.stitcher.yaml      | 14 ++++++++------
 packages/stitcher-config/src/stitcher/__init__.py   |  2 +-
 .../src/stitcher/__init__.py                        |  2 +-
 .../stitcher-spec/src/stitcher/spec/protocols.py    |  2 +-
 packages/stitcher-stubgen/src/stitcher/__init__.py  |  2 +-
 18 files changed, 51 insertions(+), 35 deletions(-)
```