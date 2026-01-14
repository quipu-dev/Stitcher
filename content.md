I've analyzed the test failures. The consistent error `sqlite3.OperationalError: no such table: symbols` across numerous tests indicates a fundamental problem with the database initialization in the test environment.

The root cause is twofold:

1.  **Packaging Defect**: The `schema.sql` file, which contains the database table definitions, was not being included in the `stitcher-index` package. This means that even when the database initialization code ran, it was executing an empty schema, resulting in an empty database file.
2.  **Test Setup Brittleness**: The test helper `create_test_app` creates an instance of `StitcherApp` but does not explicitly initialize the database. While some command flows like `check` would trigger this initialization, many tests now rely on the index being available immediately. This creates a fragile dependency on command-specific initialization logic.

I will implement a two-part solution to address both issues comprehensively.

## [WIP] fix: Resolve database initialization failures in tests

### 错误分析
All test failures point to `sqlite3.OperationalError: no such table: symbols`. This is caused by test helpers and application commands attempting to access the semantic index before the database tables have been created. The schema creation was failing silently because the `schema.sql` file was not correctly included in the package resources, and the test setup did not guarantee database initialization upon application creation.

### 用户需求
Fix all `sqlite3.OperationalError` test failures by ensuring the database schema is correctly packaged and that the database is reliably initialized in the test environment.

### 评论
This fix is critical for stabilizing the test suite after the recent architectural changes that made the index a core dependency for many components like `DocumentManager`. By fixing the packaging and making the test setup more robust, we ensure that all subsequent tests can rely on a correctly initialized database.

### 目标
1.  Correct the packaging for `stitcher-index` to include `schema.sql`.
2.  Modify the `create_test_app` test helper to eagerly initialize the database, making the testing environment more predictable and robust.

### 基本原理
1.  By adding an `include` directive to `packages/stitcher-index/pyproject.toml`, we ensure that `importlib.resources` can always find and read the SQL schema, allowing `DatabaseManager.initialize()` to function correctly.
2.  By modifying `create_test_app` to call `app.db_manager.initialize()`, we make database setup an explicit part of the test application's creation, removing ambiguity about when the database becomes available and decoupling tests from the initialization side effects of specific commands like `check`.

### 标签
#intent/fix #flow/ready #priority/critical #comp/tests #comp/build #concept/state #scope/dx #ai/instruct #task/domain/testing #task/object/database #task/action/bug-fix #task/state/continue

---

### Script

#### Acts 1: Fix `stitcher-index` packaging
I'll update the `pyproject.toml` to ensure `schema.sql` is included in the package data.

~~~~~act
patch_file
packages/stitcher-index/pyproject.toml
~~~~~
~~~~~toml
[tool.hatch.build.targets.wheel]
packages = ["src/stitcher"]
~~~~~
~~~~~toml
[tool.hatch.build.targets.wheel]
packages = ["src/stitcher"]
include = ["/src/stitcher/index/schema.sql"]
~~~~~

#### Acts 2: Make test setup robust
Next, I'll modify the central test helper `create_test_app` to ensure the database is always initialized when a test-specific `StitcherApp` instance is created.

~~~~~act
patch_file
packages/stitcher-test-utils/src/stitcher/test_utils/helpers.py
~~~~~
~~~~~python.old
def create_test_app(
    root_path: Path, interaction_handler: Optional[InteractionHandler] = None
) -> StitcherApp:
    parser = GriffePythonParser()
    transformer = PythonTransformer()
    strategy = PythonFingerprintStrategy()
    return StitcherApp(
        root_path=root_path,
        parser=parser,
        transformer=transformer,
        fingerprint_strategy=strategy,
        interaction_handler=interaction_handler,
    )
~~~~~
~~~~~python.new
def create_test_app(
    root_path: Path, interaction_handler: Optional[InteractionHandler] = None
) -> StitcherApp:
    parser = GriffePythonParser()
    transformer = PythonTransformer()
    strategy = PythonFingerprintStrategy()
    app = StitcherApp(
        root_path=root_path,
        parser=parser,
        transformer=transformer,
        fingerprint_strategy=strategy,
        interaction_handler=interaction_handler,
    )
    # Eagerly initialize the database for test reliability.
    # It's idempotent (CREATE TABLE IF NOT EXISTS), so it's safe to call.
    app.db_manager.initialize()
    return app
~~~~~

### 下一步建议
The test failures should now be resolved. I will re-run the test suite to confirm. If successful, we can proceed with the final step of the architecture refactor: updating the `CheckRunner` and `SubjectAdapter` to consume data exclusively from the index, completing the performance optimization.
