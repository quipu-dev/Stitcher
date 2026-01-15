# 📸 Snapshot Capture

检测到工作区发生变更。

### 📝 变更文件摘要:
```
.../stitcher-application/src/stitcher/app/core.py  |  2 +-
 .../src/stitcher/app/runners/check/reporter.py     |  2 +-
 .../src/stitcher/app/runners/check/resolver.py     |  2 +-
 .../src/stitcher/app/runners/index.py              |  2 +-
 .../src/stitcher/app/runners/pump/executor.py      |  2 +-
 .../src/stitcher/app/runners/pump/runner.py        |  2 +-
 .../src/stitcher/app/runners/refactor.py           |  2 +-
 .../src/stitcher/app/runners/transform.py          |  2 +-
 .../src/stitcher/services/scanner.py               |  2 +-
 .../stitcher-bus/tests/unit/test_message_bus.py    | 14 ++++-----
 .../src/stitcher/cli/commands/basics.py            |  2 +-
 .../src/stitcher/cli/commands/check.py             |  2 +-
 .../stitcher-cli/src/stitcher/cli/commands/cov.py  |  2 +-
 .../src/stitcher/cli/commands/index.py             |  2 +-
 .../stitcher-cli/src/stitcher/cli/commands/pump.py |  2 +-
 .../src/stitcher/cli/commands/refactor.py          |  2 +-
 .../stitcher-cli/src/stitcher/cli/factories.py     |  2 +-
 packages/stitcher-cli/src/stitcher/cli/main.py     |  2 +-
 .../src/stitcher/common/transaction.py             |  2 +-
 .../src/stitcher/stubgen/runners.py                |  2 +-
 .../src/stitcher/test_utils/bus.py                 |  4 +--
 uv.lock                                            | 34 ++++++++++++++++++++--
 22 files changed, 60 insertions(+), 30 deletions(-)
```