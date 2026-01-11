# 📸 Snapshot Capture

### 💬 备注:
style: ruff and stitcher

检测到工作区发生变更。

### 📝 变更文件摘要:
```
.../pyneedle-pointer/src/needle/pointer/core.json  |  3 ++-
 .../pyneedle-pointer/src/needle/pointer/set.json   |  3 ++-
 .../src/needle/operators/dict_operator.json        |  3 ++-
 .../src/needle/operators/fs_operator.json          |  3 ++-
 .../src/needle/operators/i18n_factory.json         |  3 ++-
 .../src/needle/operators/overlay_operator.json     |  3 ++-
 .../pyneedle-spec/src/needle/spec/protocols.json   |  9 ++++---
 .../src/stitcher/app/core.json                     |  8 ++++---
 .../src/stitcher/app/handlers/noop_handler.json    |  3 ++-
 .../src/stitcher/app/protocols.json                |  6 +++--
 .../src/stitcher/app/runners/check/runner.json     | 11 +++++++--
 .../src/stitcher/app/runners/check/subject.json    | 28 ++++++++++++++++++++++
 .../src/stitcher/app/services/differ.json          |  3 ++-
 .../src/stitcher/app/services/doc_manager.json     |  3 ++-
 .../src/stitcher/app/services/merger.json          |  3 ++-
 .../stitcher/app/services/signature_manager.json   |  3 ++-
 .../stitcher-cli/src/stitcher/cli/handlers.json    |  3 ++-
 .../stitcher-cli/src/stitcher/cli/interactive.json |  6 +++--
 .../stitcher-cli/src/stitcher/cli/rendering.json   |  3 ++-
 .../src/stitcher/common/adapters/yaml_adapter.json |  3 ++-
 .../src/stitcher/common/interfaces.json            |  3 ++-
 .../src/stitcher/common/messaging/bus.json         |  3 ++-
 .../src/stitcher/common/messaging/protocols.json   |  3 ++-
 .../common/services/asset_path_resolver.json       |  3 ++-
 .../src/stitcher/config/loader.json                |  3 ++-
 .../stitcher-index/src/stitcher/index/indexer.json |  9 +++----
 .../src/stitcher/index/protocols.json              |  3 ++-
 .../stitcher/adapter/python/docstring/factory.json |  3 ++-
 .../stitcher/adapter/python/docstring/parsers.json |  6 +++--
 .../adapter/python/docstring/serializers.json      |  9 ++++---
 ...
 55 files changed, 228 insertions(+), 109 deletions(-)
```