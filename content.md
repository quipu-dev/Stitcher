# 📸 Snapshot Capture

检测到工作区发生变更。

### 📝 变更文件摘要:
```
.../stitcher-application/src/stitcher/app/core.py  | 220 +++++++++++++--------
 .../src/stitcher/app/handlers/noop_handler.py      |   3 +-
 .../src/stitcher/app/protocols.py                  |   7 +-
 .../src/stitcher/app/services/doc_manager.py       |   6 +-
 .../integration/test_hydrate_interactive_flow.py   |   6 +-
 .../tests/test_check_regression.py                 |  53 +++--
 packages/stitcher-cli/src/stitcher/cli/handlers.py | 106 ++++++----
 packages/stitcher-cli/src/stitcher/cli/main.py     |  11 +-
 packages/stitcher-spec/src/stitcher/spec/models.py |   4 +-
 .../src/stitcher/test_utils/__init__.py            |   8 +-
 .../src/stitcher/test_utils/helpers.py             |   3 +-
 tests/integration/test_check_interactive_flow.py   |  44 +++--
 tests/integration/test_check_state_machine.py      |   2 -
 13 files changed, 301 insertions(+), 172 deletions(-)
```