你的直觉非常敏锐。通过对代码的静态分析，我发现了一个严重的架构不一致性：`InitRunner` 已经通过 `SignatureManager` 适配了 SURI，但 **`PumpRunner` 却在手动序列化 JSON**，这导致它会绕过 SURI 逻辑，重新写回旧的短键格式，从而破坏数据的统一性。

同时，`CheckRunner` 目前虽然能“兼容”加载（通过跳过无法解析的键），但它并没有任何逻辑将旧格式“就地升级”为新格式。

根据 **ADAP v1.0** 协议和你的指令，我将**仅创建测试文件**来捕获这些确定性缺失的边缘情况。

## [WIP] test(application): 捕获 Pump 与 Check 在 SURI 迁移中的不一致性

### 用户需求
创建集成测试，用于暴露以下两个问题：
1.  `pump` 命令是否会错误地将签名文件写回旧的短键格式。
2.  `check` 命令是否能够识别旧格式并在执行重链接（relink）操作时将其升级为 SURI 格式。

### 评论
我们必须确保系统的进化是“全方位的”。如果只有 `init` 遵循新协议，而核心的 `pump` 流程仍在破坏协议，那么 SURI 体系就会崩溃。这些测试将作为我们“RED”阶段的基石。

### 目标
1.  创建 `packages/stitcher-application/tests/integration/test_signature_migration.py`。
2.  **测试 A (`test_pump_maintains_suri_format`)**: 验证在 `init` 产生 SURI 后，运行 `pump` 是否会保持 SURI 格式。
3.  **测试 B (`test_check_upgrades_legacy_format_on_relink`)**: 验证面对旧版短键 JSON，`check --force-relink` 是否能将其正确迁移为 SURI。

### 基本原理
-   **捕获 Pump 腐蚀**: 我们通过检查 `pump` 后的物理文件内容，确认是否存在 `py://` 前缀。
-   **捕获 Check 迁移缺失**: 我们手动构造一个旧版 JSON，运行 `check`，观察它是否能通过重链接过程“洗白”数据格式。

### 标签
#intent/tooling #flow/ready #priority/critical #comp/tests #concept/state #scope/dx #ai/instruct #task/domain/storage #task/object/suri-migration #task/action/capture-failure #task/state/begin

---

### Script

#### Acts 1: 创建不一致性捕获测试

我们将编写两个精确的集成测试，它们在当前的实现下**必然会失败**。

~~~~~act
write_file
packages/stitcher-application/tests/integration/test_signature_migration.py
~~~~~
~~~~~python
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
~~~~~

### 下一步建议

现在请运行这些测试：
`pytest packages/stitcher-application/tests/integration/test_signature_migration.py`

我预计这两个测试都会**失败 (RED)**。
- 第一个测试会失败，因为 `PumpRunner` 确实在手动写 JSON 且没用 SURI。
- 第二个测试会失败，因为 `SignatureManager.load_composite_hashes` 在加载时会跳过（解析失败）旧键，导致 `check` 认为 Baseline 为空，从而无法进行有效的 Relink/升级。

一旦确认失败，我将根据 **ADAP v1.0** 协议提交修复方案，彻底统一这些链路。
