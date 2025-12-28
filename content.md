# 📸 Snapshot Capture

检测到工作区发生变更。

### 📝 变更文件摘要:
```
.../pyneedle-nexus/src/needle/nexus/loaders.json   |  15 --
 .../pyneedle-nexus/src/needle/nexus/nexus.json     |  43 ----
 .../src/needle/pointer/__init__.json               |   7 -
 .../pyneedle-pointer/src/needle/pointer/core.json  |  51 ----
 .../pyneedle-pointer/src/needle/pointer/set.json   |  19 --
 .../pyneedle-spec/src/needle/spec/protocols.json   | 100 --------
 .../src/stitcher/app/core.json                     | 108 --------
 .../src/stitcher/app/handlers/noop_handler.json    |  15 --
 .../src/stitcher/app/protocols.json                |  16 --
 .../src/stitcher/app/services/doc_manager.json     |  63 -----
 .../stitcher/app/services/signature_manager.json   |  27 --
 .../app/services/stub_package_manager.json         |  15 --
 .../stitcher-cli/src/stitcher/cli/handlers.json    |  11 -
 .../stitcher-cli/src/stitcher/cli/main.json        |  36 ---
 .../stitcher-cli/src/stitcher/cli/rendering.json   |  11 -
 .../src/stitcher/common/__init__.json              |  17 --
 .../src/stitcher/common/formatting.json            |  10 -
 .../src/stitcher/common/messaging/bus.json         |  39 ---
 .../src/stitcher/common/messaging/protocols.json   |  11 -
 .../src/stitcher/config/loader.json                |  44 ----
 .../src/stitcher/io/adapters/yaml_adapter.json     |  15 --
 .../stitcher-io/src/stitcher/io/interfaces.json    |  15 --
 .../src/stitcher/io/stub_generator.json            |  35 ---
 .../src/stitcher/scanner/inspector.json            |  19 --
 .../src/stitcher/scanner/parser.json               |  63 -----
 .../src/stitcher/scanner/transformer.json          |  81 ------
 .../stitcher-spec/src/stitcher/spec/models.json    | 284 ---------------------
 .../src/stitcher/test_utils/bus.json               |  49 ----
 .../src/stitcher/test_utils/harness.json           |  47 ----
 .../src/stitcher/test_utils/helpers.json           |   6 -
 ...
 32 files changed, 1326 deletions(-)
```