简要回答
之前的测试失败揭示了两个潜在问题：一是测试用例中的多行字符串缩进可能导致 Scanner 解析失败，导致没有保存初始指纹；二是 `run_from_config` (Generate) 在更新指纹时可能存在隐患。

我将采取以下措施：
1.  **增强测试稳健性**: 修改集成测试，使用更安全的字符串格式，并显式断言 `run_init` 和 `run_from_config` 是否成功扫描并处理了文件（通过检查 Bus 消息）。
2.  **重构 `SignatureManager`**: 增加一些防御性逻辑，确保目录存在。
3.  **重新应用 `models.py`**: 确保指纹计算逻辑被正确注入。

## [WIP] fix: 修复指纹机制的集成测试与实现细节

### 用户需求
确保签名指纹机制在各种边界条件下都能稳定工作，并且测试用例能够真实反映代码变更。

### 评论
测试失败是极好的反馈。它不仅暴露了测试代码的脆弱性（对缩进的假设），也暗示了我们需要在核心流程中增加更多的验证步骤（例如确保 Scan 真的产生了 ModuleDef）。

### 目标
1.  重新 patch `models.py` 以确保 `compute_fingerprint` 存在。
2.  优化 `SignatureManager` 的写入逻辑。
3.  重写 `tests/integration/test_check_signatures.py`，加入对中间步骤成功的断言。

### 标签
#intent/fix #flow/ready #priority/high
#comp/tests #comp/application
#task/domain/quality #task/object/signature-verification #task/action/debug

---

### Script

#### Acts 1: 重新确认 `models.py` 的指纹计算逻辑

为了防止之前的 patch 因为上下文匹配问题没打上，我将再次应用它，并确保上下文足够独特。

~~~~~act
patch_file
packages/stitcher-spec/src/stitcher/spec/models.py
~~~~~
~~~~~python.old
    is_async: bool = False
    is_static: bool = False  # @staticmethod
    is_class: bool = False  # @classmethod
~~~~~
~~~~~python.new
    is_async: bool = False
    is_static: bool = False  # @staticmethod
    is_class: bool = False  # @classmethod

    def compute_fingerprint(self) -> str:
        """
        Computes a stable hash of the function signature (excluding docstring).
        """
        parts = [
            f"name:{self.name}",
            f"async:{self.is_async}",
            f"static:{self.is_static}",
            f"class:{self.is_class}",
            f"ret:{self.return_annotation or ''}",
        ]
        
        for arg in self.args:
            arg_sig = f"{arg.name}:{arg.kind}:{arg.annotation or ''}:{arg.default or ''}"
            parts.append(arg_sig)
            
        sig_str = "|".join(parts)
        return hashlib.sha256(sig_str.encode("utf-8")).hexdigest()
~~~~~

#### Acts 2: 增强 `SignatureManager` 的健壮性

确保在写入前父目录绝对存在。

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/services/signature_manager.py
~~~~~
~~~~~python.old
    def save_signatures(self, module: ModuleDef) -> None:
        """
        Computes and saves the current signatures of the module to disk.
        """
        fingerprints = self.compute_module_fingerprints(module)
        if not fingerprints:
            return

        sig_path = self._get_sig_path(module)
        sig_path.parent.mkdir(parents=True, exist_ok=True)
        
        with sig_path.open("w", encoding="utf-8") as f:
            json.dump(fingerprints, f, indent=2, sort_keys=True)
~~~~~
~~~~~python.new
    def save_signatures(self, module: ModuleDef) -> None:
        """
        Computes and saves the current signatures of the module to disk.
        """
        fingerprints = self.compute_module_fingerprints(module)
        if not fingerprints:
            # If no fingerprints (e.g. empty file), we might want to clean up any old file
            # But for now, just returning is safer.
            return

        sig_path = self._get_sig_path(module)
        # Ensure the directory exists (redundant check but safe)
        if not sig_path.parent.exists():
            sig_path.parent.mkdir(parents=True, exist_ok=True)
        
        with sig_path.open("w", encoding="utf-8") as f:
            json.dump(fingerprints, f, indent=2, sort_keys=True)
~~~~~

#### Acts 3: 重写集成测试

使用 `dedent` 清理多行字符串，并在每个步骤后检查是否产生了 `error` 消息，以快速定位扫描失败的问题。

~~~~~act
write_file
tests/integration/test_check_signatures.py
~~~~~
~~~~~python
from textwrap import dedent
from stitcher.app import StitcherApp
from stitcher.needle import L
from stitcher.test_utils import SpyBus, WorkspaceFactory


def _assert_no_errors(spy_bus):
    errors = [m for m in spy_bus.get_messages() if m["level"] == "error"]
    assert not errors, f"Unexpected errors: {errors}"


def test_check_detects_signature_change(tmp_path, monkeypatch):
    """
    End-to-End test verifying that modifying a function signature
    triggers a check failure/warning.
    """
    # 1. Setup Initial Workspace
    factory = WorkspaceFactory(tmp_path)
    # Use dedent to ensure clean indentation
    initial_code = dedent("""
    def process(value: int) -> int:
        \"\"\"Process an integer.\"\"\"
        return value * 2
    """).strip()
    
    project_root = (
        factory.with_config({"scan_paths": ["src"]})
        .with_source("src/processor.py", initial_code)
        .build()
    )

    app = StitcherApp(root_path=project_root)
    
    # 2. Run Init (Baseline)
    spy_bus = SpyBus()
    with spy_bus.patch(monkeypatch, "stitcher.app.core.bus"):
        app.run_init()
        
    _assert_no_errors(spy_bus)
    spy_bus.assert_id_called(L.init.run.complete, level="success")
    
    # Verify fingerprint file exists
    sig_file = project_root / ".stitcher/signatures/src/processor.json"
    assert sig_file.exists(), "Fingerprint file was not created during Init"
    
    # 3. Modify Code
    modified_code = dedent("""
    def process(value: str) -> int:
        \"\"\"Process a string (Changed).\"\"\"
        return len(value) * 2
    """).strip()
    (project_root / "src/processor.py").write_text(modified_code, encoding="utf-8")
    
    # 4. Run Check
    spy_bus = SpyBus()
    with spy_bus.patch(monkeypatch, "stitcher.app.core.bus"):
        success = app.run_check()
        
    # 5. Assertions
    assert success is False, "Check passed but should have failed due to signature mismatch"
    spy_bus.assert_id_called(L.check.issue.mismatch, level="error")


def test_generate_updates_signatures(tmp_path, monkeypatch):
    """
    Verify that running 'generate' updates the signature baseline.
    """
    # 1. Setup Workspace
    factory = WorkspaceFactory(tmp_path)
    # Simple one-liner to avoid any parsing ambiguity
    project_root = (
        factory.with_config({"scan_paths": ["src"]})
        .with_source("src/main.py", "def func(a: int): ...")
        .with_docs("src/main.stitcher.yaml", {"func": "doc"})
        .build()
    )
    
    app = StitcherApp(root_path=project_root)
    
    # 2. Run Init
    with SpyBus().patch(monkeypatch, "stitcher.app.core.bus"):
        app.run_init()
        
    # 3. Modify Code
    (project_root / "src/main.py").write_text("def func(a: str): ...", encoding="utf-8")
    
    # 4. Run Generate (Should update signatures)
    spy_bus = SpyBus()
    with spy_bus.patch(monkeypatch, "stitcher.app.core.bus"):
        app.run_from_config()
        
    _assert_no_errors(spy_bus)
    spy_bus.assert_id_called(L.generate.run.complete, level="success")
    
    # Verify fingerprint file timestamp or content? 
    # Better to verify via Check.
    
    # 5. Run Check (Should now pass)
    spy_bus = SpyBus()
    with spy_bus.patch(monkeypatch, "stitcher.app.core.bus"):
        success = app.run_check()
        
    assert success is True, "Check failed but should have passed after Generate"
    spy_bus.assert_id_called(L.check.run.success, level="success")
~~~~~
