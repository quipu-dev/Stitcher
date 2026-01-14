Understood. Using `sed` is a more direct approach for this kind of widespread, systematic replacement. Now that I have access to the test files, I can address all remaining `pyright` errors.

This plan will execute a single shell script containing a series of `sed` commands to replace every incorrect import of `RefactorContext` with the new, correct path.

## [WIP] fix: Resolve all remaining pyright errors using sed

### 错误分析

The `pyright` errors are all consistent and stem from the previous architectural refactoring. The `RefactorContext` class was moved from `stitcher.refactor.engine.context` to the new `stitcher.refactor.types` module to break a dependency cycle. The previous plan updated the internal library code, but as the error report shows, the import paths in the application runner and the entire test suite were not updated.

### 用户需求

The user requires a fix for all reported `pyright` errors and has specifically requested that the fix be implemented using `sed` commands instead of `patch_file`.

### 评论

This is the final cleanup step for the dependency cycle refactoring. Using `sed` is highly efficient for this task, as it involves applying the exact same text substitution across a large number of files. This confirms the architectural change was correct, and now we are simply propagating that change to all consumer modules.

### 目标

Execute a single, comprehensive shell script that uses `sed` to replace all outdated import paths for `RefactorContext` across the application, library, and test files.

### 基本原理

I will generate a single `run_command` block. This block will contain a multi-line shell script. Each line of the script will be a `sed -i` command targeting one of the files reported by `pyright`. The `sed` command will perform an in-place search and replace, changing `from stitcher.refactor.engine.context import RefactorContext` to `from stitcher.refactor.types import RefactorContext`. This directly resolves all remaining import errors.

### 标签

#intent/fix #flow/ready #priority/high #comp/build #comp/tests #scope/dx #ai/instruct #task/domain/testing #task/object/dependency-graph #task/action/bug-fix #task/state/continue

---

### Script

#### Acts 1: Update all `RefactorContext` import paths

This script will now execute `sed` on all affected files, including the newly provided test files, to correct the import paths.

~~~~~act
run_command
~~~~~
~~~~~bash
sed -i 's#from stitcher.refactor.engine.context import RefactorContext#from stitcher.refactor.types import RefactorContext#g' packages/stitcher-application/src/stitcher/app/runners/refactor.py
sed -i 's#from stitcher.refactor.engine.context import RefactorContext#from stitcher.refactor.types import RefactorContext#g' packages/stitcher-refactor/src/stitcher/refactor/operations/rename_namespace.py
sed -i 's#from stitcher.refactor.engine.context import RefactorContext#from stitcher.refactor.types import RefactorContext#g' packages/stitcher-refactor/src/stitcher/refactor/tests/integration/test_repro_sidecar_fqn.py
sed -i 's#from stitcher.refactor.engine.context import RefactorContext#from stitcher.refactor.types import RefactorContext#g' packages/stitcher-refactor/tests/integration/test_bug_init_relative_import.py
sed -i 's#from stitcher.refactor.engine.context import RefactorContext#from stitcher.refactor.types import RefactorContext#g' packages/stitcher-refactor/tests/integration/test_bug_relative_import_refactor.py
sed -i 's#from stitcher.refactor.engine.context import RefactorContext#from stitcher.refactor.types import RefactorContext#g' packages/stitcher-refactor/tests/integration/test_debug_rename_failure.py
sed -i 's#from stitcher.refactor.engine.context import RefactorContext#from stitcher.refactor.types import RefactorContext#g' packages/stitcher-refactor/tests/integration/test_fail_concurrent_move_and_rename.py
sed -i 's#from stitcher.refactor.engine.context import RefactorContext#from stitcher.refactor.types import RefactorContext#g' packages/stitcher-refactor/tests/integration/test_monorepo_refactor_e2e.py
sed -i 's#from stitcher.refactor.engine.context import RefactorContext#from stitcher.refactor.types import RefactorContext#g' packages/stitcher-refactor/tests/integration/test_monorepo_refactor_with_tests_e2e.py
sed -i 's#from stitcher.refactor.engine.context import RefactorContext#from stitcher.refactor.types import RefactorContext#g' packages/stitcher-refactor/tests/integration/test_move_directory_e2e.py
sed -i 's#from stitcher.refactor.engine.context import RefactorContext#from stitcher.refactor.types import RefactorContext#g' packages/stitcher-refactor/tests/integration/test_move_directory_monorepo_e2e.py
sed -i 's#from stitcher.refactor.engine.context import RefactorContext#from stitcher.refactor.types import RefactorContext#g' packages/stitcher-refactor/tests/integration/test_move_file_cross_package_e2e.py
sed -i 's#from stitcher.refactor.engine.context import RefactorContext#from stitcher.refactor.types import RefactorContext#g' packages/stitcher-refactor/tests/integration/test_move_file_e2e.py
sed -i 's#from stitcher.refactor.engine.context import RefactorContext#from stitcher.refactor.types import RefactorContext#g' packages/stitcher-refactor/tests/integration/test_move_nested_directory_e2e.py
sed -i 's#from stitcher.refactor.engine.context import RefactorContext#from stitcher.refactor.types import RefactorContext#g' packages/stitcher-refactor/tests/integration/test_rename_e2e.py
sed -i 's#from stitcher.refactor.engine.context import RefactorContext#from stitcher.refactor.types import RefactorContext#g' packages/stitcher-refactor/tests/integration/test_rename_namespace_pkg_failure.py
sed -i 's#from stitcher.refactor.engine.context import RefactorContext#from stitcher.refactor.types import RefactorContext#g' packages/stitcher-refactor/tests/integration/test_rename_suri_update.py
sed -i 's#from stitcher.refactor.engine.context import RefactorContext#from stitcher.refactor.types import RefactorContext#g' packages/stitcher-refactor/tests/integration/test_rename_symbol_definition.py
sed -i 's#from stitcher.refactor.engine.context import RefactorContext#from stitcher.refactor.types import RefactorContext#g' packages/stitcher-refactor/tests/integration/test_rename_symbol_monorepo_e2e.py
sed -i 's#from stitcher.refactor.engine.context import RefactorContext#from stitcher.refactor.types import RefactorContext#g' packages/stitcher-refactor/tests/integration/test_rename_transformer_advanced.py
sed -i 's#from stitcher.refactor.engine.context import RefactorContext#from stitcher.refactor.types import RefactorContext#g' packages/stitcher-refactor/tests/unit/engine/test_planner.py
sed -i 's#from stitcher.refactor.engine.context import RefactorContext#from stitcher.refactor.types import RefactorContext#g' packages/stitcher-refactor/tests/unit/engine/test_planner_merging.py
sed -i 's#from stitcher.refactor.engine.context import RefactorContext#from stitcher.refactor.types import RefactorContext#g' packages/stitcher-refactor/tests/unit/operations/test_rename_symbol_operation.py
sed -i 's#from stitcher.refactor.engine.context import RefactorContext#from stitcher.refactor.types import RefactorContext#g' packages/stitcher-refactor/tests/unit/test_rename_operation.py
~~~~~

### 下一步建议

All known `pyright` errors have now been addressed. The next crucial step is to run the full test suite to ensure that these changes have not introduced any runtime regressions.

I recommend running `pytest`. If that passes, we can consider this refactoring complete and create a `[COMMIT]` plan to finalize the changes.
