# 📸 Snapshot Capture

检测到工作区发生变更。

### 📝 变更文件摘要:
```
.../tests/integration/test_check_command.py        |  6 ++++--
 .../tests/integration/test_check_conflict.py       |  2 +-
 .../tests/integration/test_check_file_tracking.py  | 14 ++++++++++----
 .../integration/test_check_ignores_imports.py      |  2 +-
 .../integration/test_check_ignores_reexports.py    |  2 +-
 .../integration/test_check_interactive_flow.py     | 22 ++++++++++++++++------
 .../tests/integration/test_check_policy.py         |  2 +-
 .../tests/integration/test_check_signatures.py     |  6 ++++--
 .../tests/integration/test_check_state_machine.py  |  2 +-
 .../tests/integration/test_end_to_end.py           |  6 ++++--
 .../tests/integration/test_init_command.py         |  2 +-
 .../integration/test_init_sidecar_idempotency.py   | 10 +++++++---
 .../tests/integration/test_lifecycle_commands.py   |  6 ++++--
 .../tests/integration/test_parser_robustness.py    |  2 +-
 .../tests/integration/test_pump_command.py         |  2 +-
 .../integration/test_pump_interactive_flow.py      | 18 +++++++++++++-----
 .../tests/integration/test_pump_test_files.py      |  2 +-
 .../tests/integration/test_stub_package.py         |  5 ++++-
 .../tests/integration/test_viewdiff_flow.py        |  2 +-
 .../tests/test_check_regression.py                 |  6 ++++--
 .../tests/integration/test_error_handling.py       |  6 ++++--
 .../tests/integration/test_fidelity_principles.py  |  6 ++++--
 .../tests/integration/test_loglevel_option.py      | 14 ++++++++++----
 .../integration/test_pump_strip_interaction.py     |  2 +-
 .../tests/integration/test_refactor_command.py     |  2 +-
 .../stitcher-common/tests/unit/test_message_bus.py |  3 +--
 26 files changed, 101 insertions(+), 51 deletions(-)
```