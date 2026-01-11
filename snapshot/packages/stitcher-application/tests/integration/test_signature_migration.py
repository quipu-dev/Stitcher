import json
import pytest
from pathlib import Path
from stitcher.test_utils import WorkspaceFactory, create_test_app, SpyBus

def test_pump_should_not_corrupt_suri_keys(tmp_path, monkeypatch):
    """
    捕获错误：PumpRunner 目前手动序列化 JSON，可能会将 SURI 键写回短键。
    """
    # 1. Arrange: Init a project with SURIs
    factory = WorkspaceFactory(tmp_path)
    rel_path = "src/app.py"
    project_root = (
        factory.with_config({"scan_paths": ["src"]})
        .with_source(rel_path, "def existing_func(): pass")
        .build()
    )
    
    app = create_test_app(project_root)
    app.run_init()
    
    # 验证初始是 SURI
    sig_path = project_root / ".stitcher/signatures/src/app.json"
    with sig_path.open("r") as f:
        assert any(k.startswith("py://") for k in json.load(f).keys())

    # 2. Act: 添加新函数并运行 pump
    (project_root / rel_path).write_text("def existing_func(): pass\ndef new_func(): \"\"\"Doc\"\"\"")
    
    with SpyBus().patch(monkeypatch, "stitcher.common.bus"):
        # 注意：这里我们期望 pump 能保持 SURI
        app.run_pump()
        
    # 3. Assert: 检查物理文件
    with sig_path.open("r") as f:
        raw_data = json.load(f)
        keys = list(raw_data.keys())
        
        # 失败点：如果 PumpRunner 没改，这里会是 ["existing_func", "new_func"]
        # 我们期望这里依然全是 SURI
        assert all(k.startswith("py://") for k in keys), f"Pump corrupted SURI keys! Found: {keys}"

def test_check_relink_should_upgrade_legacy_signatures(tmp_path, monkeypatch):
    """
    捕获缺失功能：Check --force-relink 应该将旧版短键 JSON 升级为 SURI。
    """
    # 1. Arrange: 手动创建一个旧版的短键签名文件
    factory = WorkspaceFactory(tmp_path)
    rel_path = "src/app.py"
    project_root = (
        factory.with_config({"scan_paths": ["src"]})
        .with_source(rel_path, "def func(a: int): pass")
        .build()
    )
    
    sig_dir = project_root / ".stitcher/signatures/src"
    sig_dir.mkdir(parents=True)
    legacy_data = {
        "func": {
            "baseline_code_structure_hash": "old_hash",
            "baseline_yaml_content_hash": "old_yaml_hash"
        }
    }
    (sig_dir / "app.json").write_text(json.dumps(legacy_data))

    # 2. Act: 运行 check --force-relink (模拟签名漂移后的修复)
    # 修改源码触发漂移
    (project_root / rel_path).write_text("def func(a: str): pass")
    
    app = create_test_app(project_root)
    with SpyBus().patch(monkeypatch, "stitcher.common.bus"):
        # 执行强制重链接，我们期望它不仅更新哈希，还升级 Key 格式
        app.run_check(force_relink=True)

    # 3. Assert: 检查物理文件是否已迁移为 SURI
    sig_path = sig_dir / "app.json"
    with sig_path.open("r") as f:
        raw_data = json.load(f)
        keys = list(raw_data.keys())
        
        # 失败点：如果 Check 只是盲目更新，Key 依然会是 "func"
        # 我们期望它升级为 "py://src/app.py#func"
        assert any(k.startswith("py://") for k in keys), f"Check failed to upgrade legacy keys! Found: {keys}"