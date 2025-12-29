# 📸 Snapshot Capture

检测到工作区发生变更。

### 📝 变更文件摘要:
```
.../src/stitcher/app/core.json                     |  4 +-
 .../stitcher/app/services/signature_manager.json   | 15 +++---
 .../stitcher-cli/src/stitcher/cli/main.json        | 18 -------
 .../src/stitcher/common/adapters/yaml_adapter.json | 10 ++++
 .../src/stitcher/common/interfaces.json            | 10 ++++
 .../src/stitcher/spec/fingerprint.json             |  4 ++
 .../stitcher-spec/src/stitcher/spec/models.json    |  8 +--
 .../stitcher-spec/src/stitcher/spec/protocols.json | 39 ++++++++++++++
 .../src/stitcher/test_utils/helpers.json           |  5 ++
 .../stitcher-application/src/stitcher/app/core.py  | 42 +++++++++------
 .../src/stitcher/app/services/signature_manager.py | 15 +++---
 .../app/services/signature_manager.stitcher.yaml   |  5 +-
 .../tests/unit/test_signature_extraction.py        |  7 +--
 .../src/stitcher/common/adapters/yaml_adapter.py   |  4 +-
 .../src/stitcher/common/interfaces.py              |  2 +-
 .../src/stitcher/adapter/python/__init__.py        |  2 +-
 .../src/stitcher/adapter/python/fingerprint.py     | 26 ++++++---
 .../src/stitcher/adapter/python/generator.py       |  3 +-
 .../src/stitcher/adapter/python/inspector.py       |  2 +-
 .../src/stitcher/adapter/python/parser.py          |  3 +-
 .../src/stitcher/adapter/python/transformer.py     |  3 +-
 .../tests/unit/test_inspector.py                   | 12 +++--
 .../tests/unit/test_parser.py                      | 14 ++---
 .../tests/unit/test_stub_generator.py              | 59 ++++++++++++--------
 packages/stitcher-spec/src/stitcher/spec/models.py |  1 -
 .../src/stitcher/spec/models.stitcher.yaml         |  7 ---
 .../stitcher-spec/src/stitcher/spec/protocols.py   | 63 ++--------------------
 .../src/stitcher/spec/protocols.stitcher.yaml      | 37 +++++++++----
 .../src/stitcher/test_utils/helpers.py             |  3 --
 .../src/stitcher/test_utils/helpers.stitcher.yaml  |  5 +-
 30 files changed, 233 insertions(+), 195 deletions(-)
```