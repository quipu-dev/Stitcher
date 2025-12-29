from stitcher.test_utils import create_test_app
from needle.pointer import L
from stitcher.test_utils import SpyBus, WorkspaceFactory


def test_pump_does_not_corrupt_code_signature_baseline(tmp_path, monkeypatch):
    """
    Regression Test: Ensures `pump` does not incorrectly update the code
    signature baseline, which would hide a "signature drift" error from `check`.

    Workflow:
    1. `init`: Create a baseline with `func(a: int)`.
    2. Modify code: Change signature to `func(a: str)` and add a docstring.
    3. `pump`: This should only hydrate the docstring. On the buggy code, it
       also incorrectly updates the code signature to match `func(a: str)`.
    4. `check`: This should now report a signature drift. The test fails if
       `check` passes, because it means `pump` corrupted the state.
    """
    # 1. Arrange: Initialize a workspace to create a baseline.
    factory = WorkspaceFactory(tmp_path)
    project_root = (
        factory.with_config({"scan_paths": ["src"]})
        .with_source("src/main.py", "def func(a: int): ...")
        .build()
    )

    # Use the LibCST parser for init, simulating the old state
    # NOTE: When running against the *fixed* codebase, this will use Griffe,
    # but the test logic remains valid as it's about state changes.
    app = create_test_app(root_path=project_root)
    with SpyBus().patch(monkeypatch, "stitcher.app.core.bus"):
        app.run_init()

    # 2. Act: Modify the code to introduce a signature drift AND a new docstring
    (project_root / "src/main.py").write_text(
        'def func(a: str):\n    """New doc."""', encoding="utf-8"
    )

    # 3. Act: Run pump. This is the command with the potential side effect.
    # On buggy code, this will overwrite the code signature baseline.
    # On fixed code, it will only update the doc hashes.
    with SpyBus().patch(monkeypatch, "stitcher.app.core.bus"):
        pump_result = app.run_pump()
        assert pump_result.success is True, "Pump command itself should succeed."

    # 4. Assert: Run check and verify that it STILL detects the original drift.
    spy_bus_check = SpyBus()
    with spy_bus_check.patch(monkeypatch, "stitcher.app.core.bus"):
        check_success = app.run_check()

    # On buggy code, `pump` resets the baseline, so `check` will pass (check_success=True).
    # This will make the assertion fail, proving the test catches the bug. (RED)
    # On fixed code, `pump` does NOT reset the baseline, so `check` will fail (check_success=False).
    # This will make the assertion pass. (GREEN)
    assert (
        check_success is False
    ), "Check passed, meaning `pump` corrupted the signature baseline."

    # Additionally, verify that the correct error was reported.
    spy_bus_check.assert_id_called(L.check.state.signature_drift, level="error")