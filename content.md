
#### Acts 3: 提交修复

最后，我们将所有修改过的文件添加到暂存区并提交。

~~~~~act
git_add
packages/stitcher-common/src/stitcher/common/assets/needle/en/hydrate/main.json
packages/stitcher-common/src/stitcher/common/assets/needle/zh/hydrate/main.json
packages/stitcher-application/src/stitcher/app/core.py
packages/stitcher-application/tests/integration/test_hydrate_interactive_flow.py
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
fix(testing): correct hydrate interactive abort test

The integration test for the interactive `hydrate --abort` flow was failing due to two issues:
1. The test was incorrectly trying to assert the content of a rendered "message" string from the `SpyBus`, but the `SpyBus` is designed to only capture semantic message IDs and parameters, not the final UI string.
2. The application code in `StitcherApp.run_hydrate` was using a hardcoded string `bus.error("Hydration aborted...")` instead of a semantic pointer, making it untestable by the `SpyBus` and inconsistent with the rest of the application.

This commit addresses both issues:
- Adds a new semantic message `L.hydrate.run.aborted` to the locale files.
- Updates `StitcherApp.run_hydrate` to use this new semantic pointer when the user aborts.
- Updates `test_hydrate_interactive_abort_stops_process` to use `spy_bus.assert_id_called(L.hydrate.run.aborted)` for a correct, robust assertion.
~~~~~

