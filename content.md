# 📸 Snapshot Capture

检测到工作区发生变更。

### 📝 变更文件摘要:
```
packages/stitcher-bus/src/stitcher/bus/bus.py      | 65 +++++++++++++++++++++
 .../src/stitcher/bus/bus.stitcher.yaml             | 18 ++++++
 .../stitcher-bus/src/stitcher/bus/protocols.py     |  5 ++
 .../src/stitcher/bus/protocols.stitcher.yaml       |  9 +++
 packages/stitcher-bus/stitcher.lock                | 66 ++++++++++++++++++++++
 .../stitcher-cli/src/stitcher/cli/rendering.py     |  2 +-
 .../src/stitcher/common/__init__.py                |  2 +-
 .../src/stitcher/common/messaging/bus.py           | 65 ---------------------
 .../stitcher/common/messaging/bus.stitcher.yaml    | 18 ------
 .../src/stitcher/common/messaging/protocols.py     |  5 --
 .../common/messaging/protocols.stitcher.yaml       |  9 ---
 packages/stitcher-common/stitcher.lock             | 61 --------------------
 .../src/stitcher/test_utils/bus.py                 |  2 +-
 13 files changed, 166 insertions(+), 161 deletions(-)
```