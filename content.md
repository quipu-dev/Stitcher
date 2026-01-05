Of course. It looks like the tests are failing due to a simple setup issue. Here is the plan to fix it.

This is a classic issue when using a builder pattern like `WorkspaceFactory`. The methods like `.with_source()` only declare what files *should* be created; they don't actually write anything to disk until you call the `.build()` method. The tests are attempting to move a file that hasn't been created yet, leading to the `FileNotFoundError`.

I'll add the necessary `.build()` calls to fix the test setup.

## [WIP] fix(tests): Call WorkspaceFactory.build() in refactor command tests

### 错误分析

The tests `test_refactor_apply_e2e` and `test_refactor_apply_dry_run` are failing with a `FileNotFoundError`. This occurs because the `WorkspaceFactory` is configured with various source files (like `pyproject.toml`), but the `.build()` method, which actually writes these files to the temporary directory, is never called. Consequently, the subsequent line attempting to `.rename()` the `pyproject.toml` file fails because it doesn't exist on the filesystem yet.

### 用户需求

The user needs to fix the two failing integration tests in `packages/stitcher-cli/tests/integration/test_refactor_command.py`.

### 评论

This is a straightforward fix that addresses a common oversight when using the builder pattern. Correcting the test setup will ensure the `refactor` command's integration tests are reliable and can properly validate the command's functionality.

### 目标

1.  Locate the two failing tests in `test_refactor_command.py`.
2.  Modify each test to call `.build()` on the `WorkspaceFactory` instance after it has been configured and before any of its created files are accessed.
3.  Ensure the tests pass after the correction.

### 基本原理

The `WorkspaceFactory` API is designed to be declarative. You chain methods to describe the desired state of the test workspace, and then call `.build()` as the final imperative step to realize that state on the filesystem. The fix is to simply add this missing `.build()` call at the correct point in the test setup.

### 标签

#intent/fix #flow/ready #priority/high #comp/tests #comp/cli #scope/dx #ai/instruct #task/domain/testing #task/object/test-setup #task/action/bug-fix #task/state/begin

---

### Script

#### Acts 1: Correct the test setup

I will apply two patches to `test_refactor_command.py` to add the required `.build()` calls, ensuring the test workspace is created before its files are used.

~~~~~act
patch_file
packages/stitcher-cli/tests/integration/test_refactor_command.py
~~~~~
~~~~~python.old
    (
        factory
        .with_project_name("mypkg")
        .with_source("src/mypkg/core.py", "class Old: pass")
        .with_source("src/mypkg/app.py", "from mypkg.core import Old")
        .with_source("pyproject.toml", "[project]\nname='mypkg'") # For discovery
    )
    # Migration script
~~~~~
~~~~~python.new
    (
        factory
        .with_project_name("mypkg")
        .with_source("src/mypkg/core.py", "class Old: pass")
        .with_source("src/mypkg/app.py", "from mypkg.core import Old")
        .with_source("pyproject.toml", "[project]\nname='mypkg'") # For discovery
    ).build()
    # Migration script
    migration_script_content = """
~~~~~

~~~~~act
patch_file
packages/stitcher-cli/tests/integration/test_refactor_command.py
~~~~~
~~~~~python.old
    (
        factory
        .with_project_name("mypkg")
        .with_source("src/mypkg/core.py", "class Old: pass")
        .with_source("pyproject.toml", "[project]\nname='mypkg'")
    )
    migration_script_content = """
~~~~~
~~~~~python.new
    (
        factory
        .with_project_name("mypkg")
        .with_source("src/mypkg/core.py", "class Old: pass")
        .with_source("pyproject.toml", "[project]\nname='mypkg'")
    ).build()
    migration_script_content = """
~~~~~

### 下一步建议

After applying this fix, please re-run the test suite to confirm that the failures are resolved.
