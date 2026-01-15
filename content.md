# 📸 Snapshot Capture

检测到工作区发生变更。

### 📝 变更文件摘要:
```
.../src/stitcher/app/runners/check/resolver.py     | 18 +++++++------
 .../src/stitcher/app/runners/check/runner.py       |  2 ++
 .../src/stitcher/app/runners/pump/executor.py      |  1 -
 .../src/stitcher/app/services/lock_session.py      | 25 ++++++++++-------
 .../integration/test_init_sidecar_idempotency.py   | 31 +++++++++++++++-------
 .../tests/unit/runners/pump/test_pump_executor.py  |  1 +
 .../stitcher-index/src/stitcher/index/indexer.py   |  4 ++-
 7 files changed, 54 insertions(+), 28 deletions(-)
```