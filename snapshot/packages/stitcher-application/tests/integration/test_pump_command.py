import yaml
from stitcher.test_utils import create_test_app
from needle.pointer import L
from stitcher.test_utils import SpyBus, WorkspaceFactory


def test_pump_adds_new_docs_to_yaml(tmp_path, monkeypatch):
    """Scenario 1: Normal Pumping"""
    # Arrange
    factory = WorkspaceFactory(tmp_path)
    project_root = (
        factory.with_config({"scan_paths": ["src"]})
        .with_source("src/main.py", 'def func():\n    """New doc."""\n    pass')
        .build()
    )

    app = create_test_app(root_path=project_root)
    spy_bus = SpyBus()

    # Act
    with spy_bus.patch(monkeypatch, "stitcher.common.bus"):
        result = app.run_pump()

    # Assert
    assert result.success is True
    spy_bus.assert_id_called(L.pump.file.success, level="success")
    spy_bus.assert_id_called(L.pump.run.complete, level="success")

    doc_path = project_root / "src/main.stitcher.yaml"
    assert doc_path.exists()
    with doc_path.open("r") as f:
        data = yaml.safe_load(f)
        assert data["func"] == "New doc."


def test_pump_fails_on_conflict(tmp_path, monkeypatch):
    """Scenario 2: Conflict Detection"""
    # Arrange
    factory = WorkspaceFactory(tmp_path)
    project_root = (
        factory.with_config({"scan_paths": ["src"]})
        .with_source("src/main.py", 'def func():\n    """Code doc."""\n    pass')
        .with_docs("src/main.stitcher.yaml", {"func": "YAML doc"})
        .build()
    )

    app = create_test_app(root_path=project_root)
    spy_bus = SpyBus()

    # Act
    with spy_bus.patch(monkeypatch, "stitcher.common.bus"):
        result = app.run_pump()

    # Assert
    assert result.success is False
    spy_bus.assert_id_called(L.pump.error.conflict, level="error")
    spy_bus.assert_id_called(L.pump.run.conflict, level="error")

    # Verify YAML was NOT changed
    doc_path = project_root / "src/main.stitcher.yaml"
    with doc_path.open("r") as f:
        data = yaml.safe_load(f)
        assert data["func"] == "YAML doc"


def test_pump_force_overwrites_conflict(tmp_path, monkeypatch):
    """Scenario 3: Force Overwrite"""
    # Arrange (same as conflict test)
    factory = WorkspaceFactory(tmp_path)
    project_root = (
        factory.with_config({"scan_paths": ["src"]})
        .with_source("src/main.py", 'def func():\n    """Code doc."""\n    pass')
        .with_docs("src/main.stitcher.yaml", {"func": "YAML doc"})
        .build()
    )

    app = create_test_app(root_path=project_root)
    spy_bus = SpyBus()

    # Act
    with spy_bus.patch(monkeypatch, "stitcher.common.bus"):
        result = app.run_pump(force=True)

    # Assert
    assert result.success is True
    spy_bus.assert_id_called(L.pump.file.success, level="success")

    # Verify YAML was changed
    doc_path = project_root / "src/main.stitcher.yaml"
    with doc_path.open("r") as f:
        data = yaml.safe_load(f)
        assert data["func"] == "Code doc."


def test_pump_with_strip_removes_source_doc(tmp_path, monkeypatch):
    """Scenario 4: Strip Integration"""
    # Arrange
    factory = WorkspaceFactory(tmp_path)
    source_path = "src/main.py"
    project_root = (
        factory.with_config({"scan_paths": ["src"]})
        .with_source(source_path, 'def func():\n    """New doc."""\n    pass')
        .build()
    )

    app = create_test_app(root_path=project_root)
    spy_bus = SpyBus()

    # Act
    with spy_bus.patch(monkeypatch, "stitcher.common.bus"):
        result = app.run_pump(strip=True)

    # Assert
    assert result.success is True
    spy_bus.assert_id_called(L.pump.file.success)
    spy_bus.assert_id_called(L.strip.file.success)
    spy_bus.assert_id_called(L.strip.run.complete)

    # Verify source was stripped
    final_code = (project_root / source_path).read_text()
    assert '"""' not in final_code


def test_pump_reconcile_ignores_source_conflict(tmp_path, monkeypatch):
    """Scenario 5: Reconcile (YAML-first) Mode"""
    # Arrange (same as conflict test)
    factory = WorkspaceFactory(tmp_path)
    project_root = (
        factory.with_config({"scan_paths": ["src"]})
        .with_source("src/main.py", 'def func():\n    """Code doc."""\n    pass')
        .with_docs("src/main.stitcher.yaml", {"func": "YAML doc"})
        .build()
    )

    app = create_test_app(root_path=project_root)
    spy_bus = SpyBus()

    # Act
    with spy_bus.patch(monkeypatch, "stitcher.common.bus"):
        result = app.run_pump(reconcile=True)

    # Assert
    assert result.success is True
    spy_bus.assert_id_called(L.pump.info.reconciled, level="info")

    # Verify no errors were raised
    error_msgs = [m for m in spy_bus.get_messages() if m["level"] == "error"]
    assert not error_msgs

    # Verify YAML was NOT changed
    doc_path = project_root / "src/main.stitcher.yaml"
    with doc_path.open("r") as f:
        data = yaml.safe_load(f)
        assert data["func"] == "YAML doc"
