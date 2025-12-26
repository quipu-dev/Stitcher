# 📸 Snapshot Capture

### 💬 备注:
ruff

检测到工作区发生变更。

### 📝 变更文件摘要:
```
.../stitcher-application/src/stitcher/app/core.py  | 20 ++---
 .../src/stitcher/app/services/signature_manager.py | 14 +--
 .../tests/test_signature_manager.py                | 41 ++++-----
 packages/stitcher-cli/src/stitcher/cli/main.py     |  2 +
 .../src/stitcher/common/messaging/bus.py           |  4 +-
 .../src/stitcher/scanner/parser.py                 |  8 +-
 .../src/stitcher/scanner/transformer.py            | 99 ++++++++++++----------
 .../stitcher-scanner/tests/test_parser_imports.py  | 23 +++--
 .../stitcher-scanner/tests/test_transformer.py     | 20 ++---
 packages/stitcher-spec/src/stitcher/spec/models.py |  8 +-
 tests/integration/test_check_signatures.py         | 38 +++++----
 tests/integration/test_lifecycle_commands.py       |  6 +-
 12 files changed, 149 insertions(+), 134 deletions(-)
```