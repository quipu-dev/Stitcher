# 📸 Snapshot Capture

### 💬 备注:
style: ruff and stitcher

检测到工作区发生变更。

### 📝 变更文件摘要:
```
.../src/stitcher/app/core.json                     |  5 ++++
 .../src/stitcher/app/runners/coverage.json         | 22 +++++++++++++++++
 .../src/stitcher/app/types.json                    |  6 +++++
 .../src/stitcher/cli/commands/cov.json             |  6 +++++
 .../tests/integration/test_repro_sidecar_fqn.json  |  7 ++++++
 .../stitcher-spec/src/stitcher/spec/models.json    |  5 ++++
 .../stitcher-application/src/stitcher/app/core.py  |  4 +---
 .../src/stitcher/app/runners/coverage.py           | 12 +++++-----
 .../stitcher-cli/src/stitcher/cli/commands/cov.py  |  2 +-
 .../tests/integration/test_coverage_command.py     | 21 ++++++++--------
 .../tests/integration/test_repro_sidecar_fqn.py    | 28 ++++------------------
 .../test_repro_sidecar_fqn.stitcher.yaml           | 10 ++++++++
 packages/stitcher-spec/src/stitcher/spec/models.py |  7 ++----
 .../src/stitcher/spec/models.stitcher.yaml         |  2 ++
 14 files changed, 89 insertions(+), 48 deletions(-)
```