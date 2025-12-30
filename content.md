# 📸 Snapshot Capture

检测到工作区发生变更。

### 📝 变更文件摘要:
```
.../pyneedle-pointer/src/needle/__init__.json      |  3 ++
 .../src/needle/pointer/__init__.json               |  4 +-
 .../pyneedle-pointer/src/needle/pointer/core.json  | 20 +++++-----
 .../pyneedle-pointer/src/needle/pointer/set.json   |  6 +--
 .../pyneedle-runtime/src/needle/__init__.json      |  3 ++
 .../src/needle/operators/__init__.json             |  3 ++
 .../src/needle/operators/dict_operator.json        |  3 +-
 .../src/needle/operators/fs_operator.json          |  5 ++-
 .../src/needle/operators/helpers/json_handler.json |  3 +-
 .../src/needle/operators/helpers/protocols.json    |  1 +
 .../src/needle/operators/i18n_factory.json         |  3 +-
 .../src/needle/operators/overlay_operator.json     |  3 +-
 .../pyneedle-runtime/src/needle/runtime.json       |  1 +
 .../pyneedle-spec/src/needle/__init__.json         |  3 ++
 .../pyneedle-spec/src/needle/spec/__init__.json    |  4 ++
 .../pyneedle-spec/src/needle/spec/protocols.json   | 20 +++++-----
 .../packages/pyneedle/src/needle/__init__.json     |  4 ++
 .../src/stitcher/app/__init__.json                 |  4 ++
 .../src/stitcher/app/core.json                     | 45 +++++++++++-----------
 .../src/stitcher/app/handlers/noop_handler.json    |  4 ++
 .../src/stitcher/app/protocols.json                |  6 +++
 .../src/stitcher/app/runners/__init__.json         |  3 ++
 .../src/stitcher/app/runners/check.json            | 29 ++++++++++++++
 .../src/stitcher/app/runners/generate.json         | 24 ++++++++++++
 .../src/stitcher/app/runners/init.json             | 15 ++++++++
 .../src/stitcher/app/runners/pump.json             | 27 +++++++++++++
 .../src/stitcher/app/runners/transform.json        | 19 +++++++++
 .../src/stitcher/app/services/__init__.json        |  3 ++
 .../src/stitcher/app/services/doc_manager.json     | 19 +++++++--
 .../src/stitcher/app/services/scanner.json         | 25 ++++++++++++
 ...
 70 files changed, 597 insertions(+), 205 deletions(-)
```