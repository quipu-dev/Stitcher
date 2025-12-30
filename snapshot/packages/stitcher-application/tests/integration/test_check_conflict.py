from stitcher.test_utils import create_test_app
from needle.pointer import L
from stitcher.test_utils import SpyBus, WorkspaceFactory


def test_check_detects_content_conflict(tmp_path, monkeypatch):
    """
    Verifies that 'check' command fails if docstring content differs
    between the source code and the YAML file.
    """
    # 1. Arrange: Setup a workspace with conflicting docstrings
    factory = WorkspaceFactory(tmp_path)
    project_root = (
        factory.with_config({"scan_paths": ["src"]})
        .with_source("src/main.py", 'def func():\n    """Source Code Doc"""\n    pass')
        .with_docs("src/main.stitcher.yaml", {"func": "YAML Doc"})
        .build()
    )

    app = create_test_app(root_path=project_root)
    spy_bus = SpyBus()

    # 2. Act
    with spy_bus.patch(monkeypatch, "stitcher.common.bus"):
        success = app.run_check()

    # 3. Assert
    assert success is False, "Check should fail when content conflicts."

    # Assert that the specific conflict message was sent as an error
    spy_bus.assert_id_called(L.check.issue.conflict, level="error")
    spy_bus.assert_id_called(L.check.run.fail, level="error")

    # Verify the parameters of the conflict message
    conflict_msg = next(
        (m for m in spy_bus.get_messages() if m["id"] == str(L.check.issue.conflict)),
        None,
    )
    assert conflict_msg is not None
    assert conflict_msg["params"]["key"] == "func"
