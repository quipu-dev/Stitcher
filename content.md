## [WIP] feat: 实现 `stitcher check` 命令

### 用户需求
实现 **任务 2.4: `stitcher check` 命令**。用于校验源代码与外部文档文件的一致性，确保没有“僵尸文档”（代码删了文档还在）和“缺失文档”（代码加了文档没补）。

### 评论
这是 CI/CD 流水线中的关键一环。虽然需求中提到了“签名比对”，但鉴于目前的 `Dict[str, str]` 简单存储结构，我们将在 MVP 中专注于 **键值存在性比对 (Existence Check)**，即确保 YAML 中的 Key 集合与代码中的符号集合完全一致。这足以捕获最常见的“代码与文档漂移”问题。

### 目标
1.  在 `stitcher-needle` 中定义 Check 相关的反馈消息。
2.  在 `DocumentManager` 中实现 `check_module` 逻辑，比对内存中的 IR 符号与加载的 YAML Key。
3.  实现 `StitcherApp.run_check`，收集所有错误并在发现问题时返回非空结果。
4.  在 CLI 中实现 `check` 命令，根据结果设置非零退出码。

### 基本原理
1.  **代码符号集 (Code Keys)**: 利用现有的 `flatten_module_docs` 逻辑（稍作修改或复用）提取当前代码中所有的可文档化符号（类、函数、方法、模块）。
2.  **文档符号集 (Doc Keys)**: 加载对应的 `.stitcher.yaml` 文件中的 Key。
3.  **集合运算**:
    *   `Missing = Code - Doc`: 代码里有，文档里没（需要补充文档）。
    *   `Extra = Doc - Code`: 文档里有，代码里没（需要清理僵尸文档）。
4.  **反馈**: 任何 Missing 或 Extra 都被视为不一致。

### 标签
#intent/build #flow/ready #priority/high #comp/cli #comp/runtime #scope/core #ai/instruct #task/domain/cli #task/object/command-check #task/action/implementation #task/state/continue

---

### Script

#### Acts 1: 定义 Needle 消息

~~~~~act
run_command
~~~~~
~~~~~
mkdir -p .stitcher/needle/en/check
~~~~~

~~~~~act
write_file
.stitcher/needle/en/check/main.json
~~~~~
~~~~~json
{
    "check.file.pass": "✅ {path}: Synced.",
    "check.file.fail": "❌ {path}: Found {count} issues.",
    "check.issue.missing": "   - [MISSING] {key} (present in code, missing in YAML)",
    "check.issue.extra": "   - [EXTRA]   {key} (present in YAML, missing in code)",
    "check.run.success": "✨ All checks passed. Documentation is in sync.",
    "check.run.fail": "🚫 Check failed. Found issues in {count} files."
}
~~~~~

#### Acts 2: 扩展 DocumentManager 实现检查逻辑

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/services/doc_manager.py
~~~~~
~~~~~python.old
        for attr in module.attributes:
            if attr.name in docs:
                attr.docstring = docs[attr.name]
~~~~~
~~~~~python.new
        for attr in module.attributes:
            if attr.name in docs:
                attr.docstring = docs[attr.name]

    def check_module(self, module: ModuleDef) -> Dict[str, set]:
        """
        Compares module structure against external docs.
        Returns a dict of issues: {'missing': set(...), 'extra': set(...)}
        """
        # 1. Get keys from Code (Source of Truth for Existence)
        # We use flatten_module_docs to get all addressable keys in the code.
        # Note: flatten_module_docs currently extracts keys ONLY if docstring exists?
        # Let's check implementation. 
        # Wait, flatten_module_docs extracts keys for functions/classes regardless of docstring?
        # Looking at _extract_from_function: 
        #   if func.docstring: docs[full_name] = func.docstring
        # This is a problem for 'check'. We want to know if the symbol EXISTS, 
        # not just if it has a docstring in code.
        # We need a method that extracts ALL keys.
        
        code_keys = self._extract_all_keys(module)
        
        # 2. Get keys from YAML
        yaml_docs = self.load_docs_for_module(module)
        doc_keys = set(yaml_docs.keys())
        
        # 3. Diff
        missing = code_keys - doc_keys
        extra = doc_keys - code_keys
        
        return {
            "missing": missing,
            "extra": extra
        }

    def _extract_all_keys(self, module: ModuleDef) -> set:
        """Extracts all addressable FQNs from the module IR."""
        keys = set()
        
        # Module itself
        # We always expect a module to optionally have a docstring.
        # Should we force __doc__ key? Maybe not strict for now.
        # keys.add("__doc__") 
        
        # But if the user put __doc__ in YAML, and we don't put it in keys, it shows as Extra.
        # So we should consider __doc__ as a valid key for any module.
        keys.add("__doc__")

        for func in module.functions:
            keys.add(func.name)
            
        for cls in module.classes:
            keys.add(cls.name)
            for method in cls.methods:
                keys.add(f"{cls.name}.{method.name}")
            for attr in cls.attributes:
                keys.add(f"{cls.name}.{attr.name}")
                
        # Module attributes
        for attr in module.attributes:
            keys.add(attr.name)
            
        return keys
~~~~~

#### Acts 3: 在 StitcherApp 中实现 `run_check`

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/core.py
~~~~~
~~~~~python.old
        else:
            bus.info(L.init.no_docs_found)
            
        return created_files
~~~~~
~~~~~python.new
        else:
            bus.info(L.init.no_docs_found)
            
        return created_files

    def run_check(self) -> bool:
        """
        Checks consistency between source code and documentation files.
        Returns True if passed, False if issues found.
        """
        config = load_config_from_path(self.root_path)
        
        files_to_scan = []
        for scan_path_str in config.scan_paths:
            scan_path = self.root_path / scan_path_str
            if scan_path.is_dir():
                files_to_scan.extend(scan_path.rglob("*.py"))
            elif scan_path.is_file():
                files_to_scan.append(scan_path)
                
        unique_files = sorted(list(set(files_to_scan)))
        modules = self._scan_files(unique_files)
        
        if not modules:
            bus.warning(L.warning.no_files_or_plugins_found)
            return True # No files to check implies success? Or warning.

        failed_files = 0
        
        for module in modules:
            issues = self.doc_manager.check_module(module)
            missing = issues["missing"]
            extra = issues["extra"]
            
            file_rel_path = module.file_path # string
            
            if not missing and not extra:
                # Optional: verbose mode could show success
                # bus.success(L.check.file.pass, path=file_rel_path)
                continue
            
            failed_files += 1
            bus.error(L.check.file.fail, path=file_rel_path, count=len(missing)+len(extra))
            
            # Sort for deterministic output
            for key in sorted(list(missing)):
                bus.error(L.check.issue.missing, key=key)
            for key in sorted(list(extra)):
                bus.error(L.check.issue.extra, key=key)
                
        if failed_files > 0:
            bus.error(L.check.run.fail, count=failed_files)
            return False
        
        bus.success(L.check.run.success)
        return True
~~~~~

#### Acts 4: CLI 挂载与退出码控制

~~~~~act
patch_file
packages/stitcher-cli/src/stitcher/cli/main.py
~~~~~
~~~~~python.old
@app.command()
def check():
    """Verify consistency between code and docs."""
    bus.info(L.cli.command.not_implemented, command="check")
~~~~~
~~~~~python.new
@app.command()
def check():
    """Verify consistency between code and docs."""
    project_root = Path.cwd()
    app_instance = StitcherApp(root_path=project_root)
    success = app_instance.run_check()
    if not success:
        raise typer.Exit(code=1)
~~~~~

#### Acts 5: 测试

~~~~~act
write_file
tests/integration/test_check_command.py
~~~~~
~~~~~python
import pytest
from pathlib import Path
from textwrap import dedent
from unittest.mock import MagicMock
from stitcher.app import StitcherApp
from stitcher.needle import L


@pytest.fixture
def mock_bus(monkeypatch):
    mock = MagicMock()
    monkeypatch.setattr("stitcher.app.core.bus", mock)
    return mock


def test_check_detects_missing_and_extra(tmp_path, mock_bus):
    project_root = tmp_path
    src_dir = project_root / "src"
    src_dir.mkdir()
    
    (project_root / "pyproject.toml").write_text(dedent("""
        [tool.stitcher]
        scan_paths = ["src"]
    """))
    
    # 1. Source has 'new_func', lacks 'deleted_func'
    (src_dir / "main.py").write_text(dedent("""
        def new_func():
            pass
    """))
    
    # 2. YAML has 'deleted_func', lacks 'new_func'
    (src_dir / "main.stitcher.yaml").write_text(dedent("""
        __doc__: Module doc
        deleted_func: Old doc
    """))
    
    app = StitcherApp(root_path=project_root)
    success = app.run_check()
    
    assert success is False
    
    # Expect error for file
    mock_bus.error.assert_any_call(L.check.file.fail, path="src/main.py", count=2)
    
    # Expect specific issues
    # new_func is in code, not in YAML -> MISSING
    mock_bus.error.assert_any_call(L.check.issue.missing, key="new_func")
    
    # deleted_func is in YAML, not in code -> EXTRA
    mock_bus.error.assert_any_call(L.check.issue.extra, key="deleted_func")
    
    # Run fail summary
    mock_bus.error.assert_any_call(L.check.run.fail, count=1)


def test_check_passes_when_synced(tmp_path, mock_bus):
    project_root = tmp_path
    src_dir = project_root / "src"
    src_dir.mkdir()
    
    (project_root / "pyproject.toml").write_text(dedent("""
        [tool.stitcher]
        scan_paths = ["src"]
    """))
    
    (src_dir / "main.py").write_text("def func(): pass")
    
    # Exact match (including __doc__ which is implicitly valid key)
    (src_dir / "main.stitcher.yaml").write_text(dedent("""
        __doc__: Doc
        func: Doc
    """))
    
    app = StitcherApp(root_path=project_root)
    success = app.run_check()
    
    assert success is True
    mock_bus.success.assert_called_with(L.check.run.success)
~~~~~

### 下一步建议
我们已经完成了 P0 阶段核心的文档解耦工作流（Init -> Generate -> Check）。
接下来，我们可以开始处理 **任务 3.1: 错误处理与日志记录**，或者 **P1 阶段：Needle 运行时增强**。
考虑到 `stitcher check` 对于 CI 的重要性，增强日志和错误处理（Task 3.1）是一个非常好的后续步骤，能提升工具的生产环境可用性。
