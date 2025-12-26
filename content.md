# 📸 Snapshot Capture

检测到工作区发生变更。

### 📝 变更文件摘要:
```
.../src/stitcher/app/core.stitcher.yaml            | 19 +++++++++++++++++
 .../app/services/doc_manager.stitcher.yaml         | 24 ++++++++++++++++++++++
 .../app/services/signature_manager.stitcher.yaml   | 17 +++++++++++++++
 .../tests/test_doc_manager.stitcher.yaml           | 11 ++++++++++
 .../tests/test_doc_overlay.stitcher.yaml           |  4 ++++
 .../tests/test_signature_manager.stitcher.yaml     |  8 ++++++++
 .../src/stitcher/cli/main.stitcher.yaml            | 10 +++++++++
 .../src/stitcher/cli/rendering.stitcher.yaml       |  2 ++
 .../stitcher/common/messaging/bus.stitcher.yaml    |  2 ++
 .../common/messaging/protocols.stitcher.yaml       |  9 ++++++++
 .../src/stitcher/config/loader.stitcher.yaml       |  6 ++++++
 .../tests/test_loader.stitcher.yaml                |  5 +++++
 .../io/adapters/yaml_adapter.stitcher.yaml         |  2 ++
 .../src/stitcher/io/interfaces.stitcher.yaml       | 20 ++++++++++++++++++
 .../src/stitcher/io/stub_generator.stitcher.yaml   |  2 ++
 packages/stitcher-io/tests/test_document_io.py     |  9 +++-----
 .../tests/test_document_io.stitcher.yaml           |  3 +++
 .../stitcher-io/tests/test_generator_dunder_all.py |  8 ++++----
 .../src/stitcher/needle/handlers.stitcher.yaml     |  2 ++
 .../src/stitcher/needle/interfaces.stitcher.yaml   |  6 ++++++
 .../src/stitcher/needle/loader.stitcher.yaml       |  3 +++
 .../src/stitcher/needle/pointer.stitcher.yaml      | 18 ++++++++++++++++
 .../src/stitcher/needle/runtime.stitcher.yaml      | 12 +++++++++++
 .../src/stitcher/scanner/inspector.stitcher.yaml   | 18 ++++++++++++++++
 .../src/stitcher/scanner/parser.py                 | 20 ++++++++++++++----
 .../src/stitcher/scanner/parser.stitcher.yaml      |  9 ++++++++
 .../src/stitcher/scanner/transformer.stitcher.yaml | 10 +++++++++
 .../tests/test_inspector.stitcher.yaml             |  5 +++++
 .../tests/test_parser_advanced.stitcher.yaml       |  8 ++++++++
 .../tests/test_parser_dunder_all.py                |  8 ++++----
 ...
 38 files changed, 323 insertions(+), 20 deletions(-)
```