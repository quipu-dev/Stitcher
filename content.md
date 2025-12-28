# 📸 Snapshot Capture

检测到工作区发生变更。

### 📝 变更文件摘要:
```
.../src/stitcher/app/core.json                     |  6 +++
 .../src/stitcher/app/handlers/noop_handler.json    |  1 +
 .../src/stitcher/app/protocols.json                |  2 +
 .../src/stitcher/app/services/doc_manager.json     |  1 +
 .../stitcher/app/services/signature_manager.json   |  1 +
 .../app/services/stub_package_manager.json         |  1 +
 .../stitcher-cli/src/stitcher/cli/handlers.json    |  1 +
 .../stitcher-cli/src/stitcher/cli/main.json        |  2 +
 .../stitcher-cli/src/stitcher/cli/rendering.json   |  1 +
 .../src/stitcher/common/__init__.json              |  3 ++
 .../src/stitcher/common/messaging/bus.json         |  1 +
 .../src/stitcher/common/messaging/protocols.json   |  1 +
 .../src/stitcher/config/loader.json                |  6 +++
 .../src/stitcher/io/adapters/yaml_adapter.json     |  1 +
 .../stitcher-io/src/stitcher/io/interfaces.json    |  1 +
 .../src/stitcher/io/stub_generator.json            |  1 +
 .../src/stitcher/scanner/inspector.json            |  1 +
 .../src/stitcher/scanner/parser.json               |  1 +
 .../src/stitcher/scanner/transformer.json          |  3 ++
 .../stitcher-spec/src/stitcher/spec/models.json    | 54 ++++++++++++++++++++++
 .../src/stitcher/test_utils/bus.json               |  3 ++
 .../src/stitcher/test_utils/harness.json           |  1 +
 .../src/stitcher/test_utils/nexus.json             |  1 +
 .../src/stitcher/test_utils/workspace.json         |  1 +
 24 files changed, 95 insertions(+)
```