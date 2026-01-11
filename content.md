# 📸 Snapshot Capture

检测到工作区发生变更。

### 📝 变更文件摘要:
```
.../pyneedle-nexus/src/needle/nexus/base.json      | 28 -------
 .../pyneedle-nexus/src/needle/nexus/loaders.json   | 19 -----
 .../pyneedle-nexus/src/needle/nexus/nexus.json     | 44 ----------
 .../pyneedle-nexus/src/needle/nexus/operators.json | 15 ----
 .../src/needle/pointer/__init__.json               |  4 +-
 .../pyneedle-pointer/src/needle/pointer/core.json  | 24 ++----
 .../pyneedle-pointer/src/needle/pointer/set.json   | 12 +--
 .../src/needle/loaders/fs_loader.json              | 50 -----------
 .../src/needle/loaders/json_handler.json           | 27 ------
 .../src/needle/loaders/protocols.json              | 19 -----
 .../src/needle/operators/dict_operator.json        |  9 +-
 .../src/needle/operators/fs_operator.json          |  9 +-
 .../src/needle/operators/i18n_factory.json         |  9 +-
 .../src/needle/operators/overlay_operator.json     |  9 +-
 .../pyneedle-runtime/src/needle/runtime.json       |  4 +-
 .../pyneedle-spec/src/needle/spec/protocols.json   | 52 ++++--------
 .../packages/pyneedle/src/needle/__init__.json     |  4 -
 .../src/stitcher/app/core.json                     | 97 ++--------------------
 .../src/stitcher/app/handlers/noop_handler.json    |  6 +-
 .../src/stitcher/app/protocols.json                | 29 ++-----
 .../src/stitcher/app/runners/check.json            |  9 --
 .../src/stitcher/app/runners/coverage.json         |  9 --
 .../src/stitcher/app/runners/generate.json         | 38 ---------
 .../src/stitcher/app/runners/index.json            |  2 -
 .../src/stitcher/app/runners/init.json             |  5 --
 .../src/stitcher/app/runners/pump.json             | 13 +--
 .../src/stitcher/app/runners/transform.json        |  5 --
 .../src/stitcher/app/services/differ.json          |  6 +-
 .../src/stitcher/app/services/doc_manager.json     | 56 ++++---------
 .../src/stitcher/app/services/merger.json          |  6 +-
 ...
 102 files changed, 344 insertions(+), 1783 deletions(-)
```