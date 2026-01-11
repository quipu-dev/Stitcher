# 📸 Snapshot Capture

### 💬 备注:
style: ruff and stitcher

检测到工作区发生变更。

### 📝 变更文件摘要:
```
.../src/needle/pointer/__init__.json               |  4 +-
 .../pyneedle-pointer/src/needle/pointer/core.json  | 24 ++----
 .../pyneedle-pointer/src/needle/pointer/set.json   | 12 ++-
 .../src/needle/operators/dict_operator.json        |  9 +-
 .../src/needle/operators/fs_operator.json          |  9 +-
 .../src/needle/operators/helpers/json_handler.json |  5 +-
 .../src/needle/operators/helpers/protocols.json    |  5 +-
 .../src/needle/operators/i18n_factory.json         |  9 +-
 .../src/needle/operators/overlay_operator.json     |  9 +-
 .../pyneedle-runtime/src/needle/runtime.json       |  4 +-
 .../pyneedle-spec/src/needle/spec/protocols.json   | 52 +++++-------
 .../src/stitcher/app/core.json                     | 97 +++-------------------
 .../src/stitcher/app/handlers/noop_handler.json    |  6 +-
 .../src/stitcher/app/protocols.json                | 31 +++----
 .../src/stitcher/app/runners/check.json            | 14 +---
 .../src/stitcher/app/runners/coverage.json         | 14 +---
 .../src/stitcher/app/runners/index.json            |  7 +-
 .../src/stitcher/app/runners/init.json             | 10 +--
 .../src/stitcher/app/runners/pump.json             | 15 +---
 .../src/stitcher/app/runners/refactor.json         |  5 +-
 .../src/stitcher/app/runners/transform.json        | 10 +--
 .../src/stitcher/app/services/differ.json          |  6 +-
 .../src/stitcher/app/services/doc_manager.json     | 56 +++++--------
 .../src/stitcher/app/services/merger.json          |  6 +-
 .../src/stitcher/app/services/scanner.json         |  5 +-
 .../stitcher/app/services/signature_manager.json   | 34 ++------
 .../src/stitcher/app/types.json                    | 15 +++-
 .../src/stitcher/cli/commands/basics.json          | 12 +--
 .../src/stitcher/cli/commands/check.json           |  3 +-
 .../src/stitcher/cli/commands/pump.json            |  3 +-
 ...
 103 files changed, 723 insertions(+), 1094 deletions(-)
```