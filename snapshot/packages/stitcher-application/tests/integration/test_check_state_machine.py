from stitcher.test_utils import create_test_app
from needle.pointer import L
from stitcher.test_utils import SpyBus, WorkspaceFactory, get_stored_hashes


def _assert_no_errors_or_warnings(spy_bus: SpyBus):
    errors = [m for m in spy_bus.get_messages() if m["level"] == "error"]
    warnings = [m for m in spy_bus.get_messages() if m["level"] == "warning"]
    assert not errors, f"Unexpected errors: {errors}"
    assert not warnings, f"Unexpected warnings: {warnings}"


def test_state_synchronized(tmp_path, monkeypatch):
    """
    State 1: Synchronized - Code and docs match stored hashes.
    Expected: Silent pass.
    """
    factory = WorkspaceFactory(tmp_path)
    project_root = (
        factory.with_config({"scan_paths": ["src"]})
        .with_source(
            "src/module.py", 'def func(a: int):\n    """Docstring."""\n    pass'
        )
        .build()
    )
    app = create_test_app(root_path=project_root)

    with SpyBus().patch(monkeypatch, "stitcher.common.bus"):
        app.run_init()

    # Remove docstring to achieve 'Synchronized' state without redundant warnings
    (project_root / "src/module.py").write_text("def func(a: int):\n    pass")

    spy_bus = SpyBus()
    with spy_bus.patch(monkeypatch, "stitcher.common.bus"):
        success = app.run_check()

    assert success is True
    _assert_no_errors_or_warnings(spy_bus)
    spy_bus.assert_id_called(L.check.run.success, level="success")


def test_state_doc_improvement_auto_reconciled(tmp_path, monkeypatch):
    """
    State 2: Documentation Improvement.
    Expected: INFO message, auto-reconcile doc hash, pass.
    """
    factory = WorkspaceFactory(tmp_path)
    project_root = (
        factory.with_config({"scan_paths": ["src"]})
        .with_source("src/module.py", 'def func(a: int):\n    """Old Doc."""\n    pass')
        .build()
    )
    app = create_test_app(root_path=project_root)
    with SpyBus().patch(monkeypatch, "stitcher.common.bus"):
        app.run_init()

    (project_root / "src/module.py").write_text("def func(a: int):\n    pass")

    # Modify YAML
    doc_file = project_root / "src/module.stitcher.yaml"
    new_doc_content = "New Doc."
    doc_file.write_text(
        f'__doc__: "Module Doc"\nfunc: "{new_doc_content}"\n', encoding="utf-8"
    )

    initial_hashes = get_stored_hashes(project_root, "src/module.py")

    spy_bus = SpyBus()
    with spy_bus.patch(monkeypatch, "stitcher.common.bus"):
        success = app.run_check()

    assert success is True
    # Assert Semantic ID for doc update
    spy_bus.assert_id_called(L.check.state.doc_updated, level="info")
    spy_bus.assert_id_called(L.check.run.success, level="success")

    final_hashes = get_stored_hashes(project_root, "src/module.py")
    assert (
        final_hashes["func"]["baseline_code_structure_hash"]
        == initial_hashes["func"]["baseline_code_structure_hash"]
    )

    expected_hash = app.doc_manager.compute_yaml_content_hash(new_doc_content)
    assert final_hashes["func"]["baseline_yaml_content_hash"] == expected_hash


def test_state_signature_drift_error(tmp_path, monkeypatch):
    """
    State 3: Signature Drift.
    Expected: ERROR message, check fails.
    """
    factory = WorkspaceFactory(tmp_path)
    project_root = (
        factory.with_config({"scan_paths": ["src"]})
        .with_source("src/module.py", 'def func(a: int):\n    """Doc."""\n    pass')
        .build()
    )
    app = create_test_app(root_path=project_root)
    with SpyBus().patch(monkeypatch, "stitcher.common.bus"):
        app.run_init()

    (project_root / "src/module.py").write_text("def func(a: str):\n    pass")

    spy_bus = SpyBus()
    with spy_bus.patch(monkeypatch, "stitcher.common.bus"):
        success = app.run_check()

    assert success is False
    spy_bus.assert_id_called(L.check.state.signature_drift, level="error")
    spy_bus.assert_id_called(L.check.run.fail, level="error")


def test_state_signature_drift_force_relink(tmp_path, monkeypatch):
    """
    State 3 (Resolved): Signature Drift with force_relink.
    Expected: SUCCESS message, update signature hash, pass.
    """
    factory = WorkspaceFactory(tmp_path)
    project_root = (
        factory.with_config({"scan_paths": ["src"]})
        .with_source("src/module.py", 'def func(a: int):\n    """Doc."""\n    pass')
        .build()
    )
    app = create_test_app(root_path=project_root)
    with SpyBus().patch(monkeypatch, "stitcher.common.bus"):
        app.run_init()

    (project_root / "src/module.py").write_text("def func(a: str):\n    pass")

    initial_hashes = get_stored_hashes(project_root, "src/module.py")

    spy_bus = SpyBus()
    with spy_bus.patch(monkeypatch, "stitcher.common.bus"):
        success = app.run_check(force_relink=True)

    assert success is True
    spy_bus.assert_id_called(L.check.state.relinked, level="success")
    spy_bus.assert_id_called(L.check.run.success, level="success")

    final_hashes = get_stored_hashes(project_root, "src/module.py")

    assert (
        final_hashes["func"]["baseline_code_structure_hash"]
        != initial_hashes["func"]["baseline_code_structure_hash"]
    )
    assert (
        final_hashes["func"]["baseline_yaml_content_hash"]
        == initial_hashes["func"]["baseline_yaml_content_hash"]
    )


def test_state_co_evolution_error(tmp_path, monkeypatch):
    """
    State 4: Co-evolution.
    Expected: ERROR message, check fails.
    """
    factory = WorkspaceFactory(tmp_path)
    project_root = (
        factory.with_config({"scan_paths": ["src"]})
        .with_source("src/module.py", 'def func(a: int):\n    """Old Doc."""\n    pass')
        .build()
    )
    app = create_test_app(root_path=project_root)
    with SpyBus().patch(monkeypatch, "stitcher.common.bus"):
        app.run_init()

    (project_root / "src/module.py").write_text("def func(a: str):\n    pass")

    doc_file = project_root / "src/module.stitcher.yaml"
    doc_file.write_text(
        '__doc__: "Module Doc"\nfunc: "New YAML Doc."\n', encoding="utf-8"
    )

    spy_bus = SpyBus()
    with spy_bus.patch(monkeypatch, "stitcher.common.bus"):
        success = app.run_check()

    assert success is False
    spy_bus.assert_id_called(L.check.state.co_evolution, level="error")
    spy_bus.assert_id_called(L.check.run.fail, level="error")


def test_state_co_evolution_reconcile(tmp_path, monkeypatch):
    """
    State 4 (Resolved): Co-evolution with reconcile.
    Expected: SUCCESS message, update both hashes, pass.
    """
    factory = WorkspaceFactory(tmp_path)
    project_root = (
        factory.with_config({"scan_paths": ["src"]})
        .with_source("src/module.py", 'def func(a: int):\n    """Old Doc."""\n    pass')
        .build()
    )
    app = create_test_app(root_path=project_root)
    with SpyBus().patch(monkeypatch, "stitcher.common.bus"):
        app.run_init()

    (project_root / "src/module.py").write_text("def func(a: str):\n    pass")

    doc_file = project_root / "src/module.stitcher.yaml"
    new_doc_content = "New YAML Doc."
    doc_file.write_text(
        f'__doc__: "Module Doc"\nfunc: "{new_doc_content}"\n', encoding="utf-8"
    )

    initial_hashes = get_stored_hashes(project_root, "src/module.py")

    spy_bus = SpyBus()
    with spy_bus.patch(monkeypatch, "stitcher.common.bus"):
        success = app.run_check(reconcile=True)

    assert success is True
    spy_bus.assert_id_called(L.check.state.reconciled, level="success")
    spy_bus.assert_id_called(L.check.run.success, level="success")

    final_hashes = get_stored_hashes(project_root, "src/module.py")
    assert (
        final_hashes["func"]["baseline_code_structure_hash"]
        != initial_hashes["func"]["baseline_code_structure_hash"]
    )
    assert (
        final_hashes["func"]["baseline_yaml_content_hash"]
        != initial_hashes["func"]["baseline_yaml_content_hash"]
    )

    expected_doc_hash = app.doc_manager.compute_yaml_content_hash(new_doc_content)
    assert final_hashes["func"]["baseline_yaml_content_hash"] == expected_doc_hash
