# 📸 Snapshot Capture

检测到工作区发生变更。

### 📝 变更文件摘要:
```
.../src/stitcher/app/protocols.json                | 32 ---------------
 .../src/stitcher/common/interfaces.json            | 21 ----------
 .../src/stitcher/index/protocols.json              | 12 ------
 .../stitcher-index/src/stitcher/index/types.json   | 45 ----------------------
 .../stitcher-spec/src/stitcher/spec/index.json     | 45 ++++++++++++++++++++++
 .../src/stitcher/spec/interaction.json             | 32 +++++++++++++++
 .../src/stitcher/spec/persistence.json             | 21 ++++++++++
 .../stitcher-spec/src/stitcher/spec/registry.json  | 12 ++++++
 .../stitcher-application/src/stitcher/app/core.py  |  4 +-
 .../src/stitcher/app/handlers/noop_handler.py      |  2 +-
 .../src/stitcher/app/protocols.py                  | 19 ---------
 .../src/stitcher/app/protocols.stitcher.yaml       | 17 --------
 .../src/stitcher/app/runners/check/analyzer.py     |  2 +-
 .../src/stitcher/app/runners/check/resolver.py     |  2 +-
 .../src/stitcher/app/runners/check/runner.py       |  2 +-
 .../src/stitcher/app/runners/check/subject.py      |  2 +-
 .../src/stitcher/app/runners/pump.py               |  2 +-
 .../src/stitcher/app/services/doc_manager.py       |  2 +-
 .../integration/test_check_interactive_flow.py     |  2 +-
 .../integration/test_pump_interactive_flow.py      |  2 +-
 .../tests/integration/test_viewdiff_flow.py        |  2 +-
 .../stitcher-cli/src/stitcher/cli/factories.py     |  2 +-
 packages/stitcher-cli/src/stitcher/cli/handlers.py |  2 +-
 .../stitcher-cli/src/stitcher/cli/interactive.py   |  2 +-
 .../src/stitcher/common/__init__.py                |  2 +-
 .../src/stitcher/common/adapters/yaml_adapter.py   |  2 +-
 .../src/stitcher/common/interfaces.py              | 10 -----
 .../src/stitcher/common/interfaces.stitcher.yaml   |  6 ---
 .../stitcher-index/src/stitcher/index/indexer.py   |  4 +-
 .../stitcher-index/src/stitcher/index/protocols.py |  9 -----
 ...
 44 files changed, 252 insertions(+), 252 deletions(-)
```