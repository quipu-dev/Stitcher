from stitcher.test_utils import create_test_app
from needle.pointer import L
from stitcher.test_utils import SpyBus, WorkspaceFactory


def test_check_detects_matrix_states(tmp_path, monkeypatch):
    """
    Verifies that 'check' correctly identifies all 5 states:
    Missing, Pending, Redundant, Conflict, Extra.
    """
    # 1. Arrange
    factory = WorkspaceFactory(tmp_path)
    project_root = (
        factory.with_config({"scan_paths": ["src"]})
        .with_source(
            "src/main.py",
            """
            def func_missing(): pass
            
            def func_pending():
                \"\"\"New Doc\"\"\"
                pass

            def func_redundant():
                \"\"\"Same Doc\"\"\"
                pass

            def func_conflict():
                \"\"\"Code Doc\"\"\"
                pass
            """,
        )
        .with_docs(
            "src/main.stitcher.yaml",
            {
                "__doc__": "Module doc",
                # Missing: func_missing not here
                # Pending: func_pending not here
                "func_redundant": "Same Doc",
                "func_conflict": "YAML Doc",
                "func_extra": "Old Doc",
            },
        )
        .build()
    )

    app = create_test_app(root_path=project_root)
    spy_bus = SpyBus()

    # 2. Act
    with spy_bus.patch(monkeypatch, "stitcher.common.bus"):
        success = app.run_check()

    # 3. Assert
    assert success is False

    # Check for all issue types
    spy_bus.assert_id_called(L.check.issue.missing, level="warning")
    spy_bus.assert_id_called(L.check.issue.redundant, level="warning")

    spy_bus.assert_id_called(L.check.issue.pending, level="error")
    spy_bus.assert_id_called(L.check.issue.conflict, level="error")
    spy_bus.assert_id_called(L.check.issue.extra, level="error")

    # Verify key association
    messages = spy_bus.get_messages()

    def verify_key(msg_id, expected_key):
        msgs = [m for m in messages if m["id"] == str(msg_id)]
        assert any(m["params"]["key"] == expected_key for m in msgs), (
            f"Expected key '{expected_key}' for message '{msg_id}' not found."
        )

    verify_key(L.check.issue.missing, "func_missing")
    verify_key(L.check.issue.pending, "func_pending")
    verify_key(L.check.issue.redundant, "func_redundant")
    verify_key(L.check.issue.conflict, "func_conflict")
    verify_key(L.check.issue.extra, "func_extra")


def test_check_passes_when_synced(tmp_path, monkeypatch):
    # 1. Arrange
    factory = WorkspaceFactory(tmp_path)
    project_root = (
        factory.with_config({"scan_paths": ["src"]})
        .with_source("src/main.py", "def func(): pass")
        .with_docs(
            "src/main.stitcher.yaml",
            {"__doc__": "Doc", "func": "Doc"},
        )
        .build()
    )

    app = create_test_app(root_path=project_root)
    spy_bus = SpyBus()

    # 2. Act
    with spy_bus.patch(monkeypatch, "stitcher.common.bus"):
        success = app.run_check()

    # 3. Assert
    assert success is True
    spy_bus.assert_id_called(L.check.run.success, level="success")


def test_check_command_detects_circular_dependency(spy_bus: SpyBus):
    # 1. Arrange
    with WorkspaceFactory(Path.cwd() / "test_project_circ") as wf:
        wf.with_pyproject("packages/pkg-a")
        wf.with_config(
            {
                "scan_paths": ["packages/pkg-a/src"],
            }
        )
        wf.with_source(
            "packages/pkg-a/src/pkg_a/mod_a.py",
            """
            from pkg_a.mod_b import B
            class A: pass
            """,
        )
        wf.with_source(
            "packages/pkg-a/src/pkg_a/mod_b.py",
            """
            from pkg_a.mod_c import C
            class B: pass
            """,
        )
        wf.with_source(
            "packages/pkg-a/src/pkg_a/mod_c.py",
            """
            from pkg_a.mod_a import A
            class C: pass
            """,
        )
        project_root = wf.build()
        app = create_test_app(project_root)

        # 2. Act
        success = app.run_check()

        # 3. Assert
        assert not success
        spy_bus.assert_id_called(L.check.run.fail, level="error")
        spy_bus.assert_id_called(
            L.check.architecture.circular_dependency, level="error"
        )

        # Check the message context
        messages = spy_bus.get_messages()
        arch_msg = next(
            (
                m
                for m in messages
                if m["id"] == str(L.check.architecture.circular_dependency)
            ),
            None,
        )
        assert arch_msg is not None
        assert "cycle" in arch_msg["params"]
        cycle_str = arch_msg["params"]["cycle"]
        assert "packages/pkg-a/src/pkg_a/mod_a.py" in cycle_str
        assert "packages/pkg-a/src/pkg_a/mod_b.py" in cycle_str
        assert "packages/pkg-a/src/pkg_a/mod_c.py" in cycle_str
