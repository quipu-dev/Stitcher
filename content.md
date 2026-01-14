# 📸 Snapshot Capture

### 💬 备注:
style: ruff and stitcher

检测到工作区发生变更。

### 📝 变更文件摘要:
```
packages/pyneedle-pointer/stitcher.lock            |  40 +--
 packages/pyneedle-runtime/stitcher.lock            |  40 +--
 packages/pyneedle-spec/stitcher.lock               |  52 ++--
 packages/stitcher-analysis/stitcher.lock           |  66 ++---
 .../stitcher-application/src/stitcher/app/core.py  |  12 +-
 packages/stitcher-application/stitcher.lock        |  36 +--
 .../tests/integration/test_check_cache.py          |   2 +-
 .../tests/integration/test_check_state_machine.py  |   4 +-
 packages/stitcher-cli/stitcher.lock                |  85 ++----
 packages/stitcher-common/stitcher.lock             |  61 ++--
 packages/stitcher-index/stitcher.lock              |  27 +-
 .../stitcher/lang/python/docstring/serializers.py  |   4 +-
 .../python/docstring/serializers.stitcher.yaml     |  27 +-
 packages/stitcher-lang-python/stitcher.lock        | 167 ++++++-----
 .../src/stitcher/lang/sidecar/adapter.py           |   2 +-
 .../src/stitcher/lang/sidecar/indexer.py           |  31 +-
 .../src/stitcher/lang/sidecar/uri.py               |   2 +-
 packages/stitcher-refactor/stitcher.lock           |  70 ++---
 .../stitcher-spec/src/stitcher/spec/protocols.py   |   5 -
 .../src/stitcher/spec/protocols.stitcher.yaml      |   1 +
 packages/stitcher-spec/stitcher.lock               | 329 +++++++--------------
 packages/stitcher-test-utils/stitcher.lock         | 103 +++----
 packages/stitcher-workspace/stitcher.lock          |   6 +-
 23 files changed, 445 insertions(+), 727 deletions(-)
```