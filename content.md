# 📸 Snapshot Capture

检测到工作区发生变更。

### 📝 变更文件摘要:
```
.../pyneedle-nexus/src/needle/nexus/base.json      | 23 ++++++++++++++++
 .../pyneedle-nexus/src/needle/nexus/loaders.json   |  7 +++--
 .../pyneedle-nexus/src/needle/nexus/nexus.json     | 10 ++++---
 .../pyneedle-spec/src/needle/spec/protocols.json   |  9 +++++--
 .../src/stitcher/app/core.json                     | 31 ++++++++++++++++------
 .../src/stitcher/app/protocols.json                |  9 +++++++
 .../stitcher-cli/src/stitcher/cli/main.json        | 16 +++++------
 .../src/stitcher/spec/fingerprint.json             |  3 +++
 .../stitcher-spec/src/stitcher/spec/models.json    |  9 +++++++
 packages/pyneedle-nexus/src/needle/nexus/base.py   | 24 +----------------
 .../src/needle/nexus/base.stitcher.yaml            | 17 ++++++++++++
 packages/pyneedle-nexus/src/needle/nexus/nexus.py  | 25 +++++++----------
 .../src/needle/nexus/nexus.stitcher.yaml           | 14 +++++-----
 13 files changed, 128 insertions(+), 69 deletions(-)
```