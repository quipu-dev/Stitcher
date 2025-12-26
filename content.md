# 📸 Snapshot Capture

检测到工作区发生变更。

### 📝 变更文件摘要:
```
.gitignore                                         |  3 --
 .../src/stitcher/app/__init__.pyi                  |  4 ++
 .../stitcher-application/src/stitcher/app/core.pyi | 58 ++++++++++++++++++++
 .../src/stitcher/app/services/__init__.pyi         |  4 ++
 .../src/stitcher/app/services/doc_manager.pyi      | 63 ++++++++++++++++++++++
 .../stitcher/app/services/signature_manager.pyi    | 44 +++++++++++++++
 .../tests/test_doc_manager.pyi                     | 32 +++++++++++
 .../tests/test_doc_overlay.pyi                     | 12 +++++
 .../tests/test_signature_manager.pyi               | 20 +++++++
 .../stitcher-cli/src/stitcher/cli/__init__.pyi     |  1 +
 packages/stitcher-cli/src/stitcher/cli/main.pyi    | 36 +++++++++++++
 .../stitcher-cli/src/stitcher/cli/rendering.pyi    |  7 +++
 .../src/stitcher/common/__init__.pyi               |  4 ++
 .../src/stitcher/common/messaging/bus.pyi          | 24 +++++++++
 .../src/stitcher/common/messaging/protocols.pyi    | 17 ++++++
 .../stitcher-common/tests/test_message_bus.pyi     | 19 +++++++
 .../src/stitcher/config/__init__.pyi               |  4 ++
 .../stitcher-config/src/stitcher/config/loader.pyi | 22 ++++++++
 packages/stitcher-config/tests/test_loader.pyi     | 16 ++++++
 packages/stitcher-io/src/stitcher/io/__init__.pyi  |  6 +++
 .../src/stitcher/io/adapters/__init__.pyi          |  0
 .../src/stitcher/io/adapters/yaml_adapter.pyi      | 11 ++++
 .../stitcher-io/src/stitcher/io/interfaces.pyi     | 33 ++++++++++++
 .../stitcher-io/src/stitcher/io/stub_generator.pyi | 28 ++++++++++
 packages/stitcher-io/tests/test_document_io.pyi    | 12 +++++
 packages/stitcher-io/tests/test_stub_generator.pyi | 12 +++++
 packages/stitcher-needle/src/stitcher/__init__.pyi |  1 +
 .../src/stitcher/needle/__init__.pyi               |  7 +++
 .../src/stitcher/needle/handlers.pyi               | 10 ++++
 .../src/stitcher/needle/interfaces.pyi             | 13 +++++
 ...
 51 files changed, 1004 insertions(+), 3 deletions(-)
```