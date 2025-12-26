Of course. Defining the error reporting clearly is the most critical part of the `check` command. It must be explicit, actionable, and machine-readable (via exit codes) for CI integration.

Here is the plan to implement `stitcher check`, with a detailed breakdown of the validation logic.

## [WIP] feat: 实现 `stitcher check` 命令以保证同步

### 用户需求
实现 **任务 2.4: `stitcher check` 命令**。此命令是项目健康度的守护者，必须能够检测并报告代码与外部文档 (`.stitcher.yaml`) 之间的所有不一致性。

具体来说，它必须能明确区分并报告以下两种核心错误：
1.  **代码中存在，但文档中缺失 (Missing Documentation)**: 例如，开发者新增了一个函数但忘记在 YAML 中为其添加文档。
2.  **文档中存在，但代码中缺失 (Stale Documentation)**: 例如，开发者删除了一个函数，但忘记清理其在 YAML 文件中的旧文档条目。

如果检测到任何不一致，命令必须以非零状态码退出。

### 评论
`check` 命令是整个解耦工作流的“闭环”。没有它，`init` 和 `generate` 创造的便利性会随着时间推移被代码的“熵增”所侵蚀。我们的实现将引入一个 `ConsistencyChecker` 服务，它封装了核心的“diff”逻辑，使其独立于 `StitcherApp` 的编排流程，从而更易于单元测试。

### 目标
1.  在 Needle 中为 `check` 命令定义一套清晰、结构化的反馈消息。
2.  创建一个 `ConsistencyChecker` 服务，负责比较代码结构（IR）与文档数据。
3.  在 `StitcherApp` 中实现 `run_check` 方法，该方法编排扫描、检查和报告流程。
4.  在 `stitcher-cli` 中实现 `check` 命令，并根据检查结果正确处理退出码。
5.  编写集成测试，覆盖所有不一致的场景。

### 基本原理
我们将把 **代码结构（AST 解析结果）视为“事实来源”**。`check` 命令的核心是比较两个集合：
-   `code_keys`: 从 `ModuleDef` 中提取出的所有可文档化符号的 FQN 集合。
-   `doc_keys`: 从对应的 `.stitcher.yaml` 文件中加载的所有 key 的集合。

比较逻辑如下：
1.  **计算“缺失” (Missing)**: `missing_keys = code_keys - doc_keys`。结果集中的每一个 key 都代表一个需要添加文档的符号。
2.  **计算“过时” (Stale)**: `stale_keys = doc_keys - code_keys`。结果集中的每一个 key 都代表一个需要从 YAML 文件中删除的无效条目。
3.  **判断成功**: 如果 `missing_keys` 和 `stale_keys` 两个集合都为空，则检查通过。

### 标签
#intent/build #flow/ready #priority/high #comp/cli #comp/runtime #scope/core #ai/instruct #task/domain/validation #task/object/command-check #task/action/implementation #task/state/continue

---

### Script

#### Acts 1: 添加 Needle 消息

为 `check` 命令的各种输出状态定义消息。

~~~~~act
run_command
~~~~~
~~~~~bash
mkdir -p .stitcher/needle/en/check
~~~~~

~~~~~act
write_file
.stitcher/needle/en/check/main.json
~~~~~
~~~~~json
{
    "check.header": "🔎 Checking consistency for: {path}",
    "check.success": "✅ OK",
    "check.error.missing": "  - 🟡 MISSING: '{key}' found in code but not in docs.",
    "check.error.stale": "  - 🔴 STALE: '{key}' found in docs but not in code.",
    "check.run.success": "✅ All files are consistent.",
    "check.run.failure": "❌ Found {count} inconsistencies. Please fix them."
}
~~~~~

#### Acts 2: 实现 `ConsistencyChecker` 服务

这个服务将包含核心的 diff 逻辑。

~~~~~act
write_file
packages/stitcher-application/src/stitcher/app/services/checker.py
~~~~~
~~~~~python
from dataclasses import dataclass, field
from typing import List, Set
from stitcher.spec import ModuleDef
from .doc_manager import DocumentManager


@dataclass
class CheckResult:
    is_consistent: bool
    missing_keys: Set[str] = field(default_factory=set)
    stale_keys: Set[str] = field(default_factory=set)


class ConsistencyChecker:
    def __init__(self, doc_manager: DocumentManager):
        self._doc_manager = doc_manager

    def check_module(self, module: ModuleDef) -> CheckResult:
        """
        Compares the IR of a module against its external documentation.
        """
        # Get keys from code structure
        code_keys = set(self._doc_manager.flatten_module_docs(module).keys())
        
        # Get keys from doc file
        doc_keys = set(self._doc_manager.load_docs_for_module(module).keys())
        
        missing_keys = code_keys - doc_keys
        stale_keys = doc_keys - code_keys
        
        is_consistent = not missing_keys and not stale_keys
        
        return CheckResult(
            is_consistent=is_consistent,
            missing_keys=missing_keys,
            stale_keys=stale_keys
        )
~~~~~

#### Acts 3: 在 StitcherApp 中集成 Checker

添加 `run_check` 方法。

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/core.py
~~~~~
~~~~~python.old
from stitcher.scanner import parse_source_code, parse_plugin_entry, InspectionError
from stitcher.io import StubGenerator
from stitcher.spec import ModuleDef
from stitcher.common import bus
from stitcher.needle import L
from stitcher.config import load_config_from_path
from stitcher.app.services import DocumentManager
~~~~~
~~~~~python.new
from stitcher.scanner import parse_source_code, parse_plugin_entry, InspectionError
from stitcher.io import StubGenerator
from stitcher.spec import ModuleDef
from stitcher.common import bus
from stitcher.needle import L
from stitcher.config import load_config_from_path
from stitcher.app.services import DocumentManager
from stitcher.app.services.checker import ConsistencyChecker
~~~~~

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/core.py
~~~~~
~~~~~python.old
        self.root_path = root_path
        self.generator = StubGenerator()
        self.doc_manager = DocumentManager(root_path)
~~~~~
~~~~~python.new
        self.root_path = root_path
        self.generator = StubGenerator()
        self.doc_manager = DocumentManager(root_path)
        self.checker = ConsistencyChecker(self.doc_manager)
~~~~~

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
        Scans and checks all source files for consistency.
        Returns True if inconsistencies are found, False otherwise.
        """
        config = load_config_from_path(self.root_path)
        
        # Discover and scan source files
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
            return False # No errors found

        total_inconsistencies = 0
        has_errors = False
        
        for module in modules:
            relative_path = Path(module.file_path)
            bus.info(L.check.header, path=relative_path)
            
            result = self.checker.check_module(module)
            
            if result.is_consistent:
                bus.success(L.check.success)
            else:
                has_errors = True
                for key in sorted(list(result.missing_keys)):
                    bus.warning(L.check.error.missing, key=key)
                    total_inconsistencies += 1
                for key in sorted(list(result.stale_keys)):
                    bus.error(L.check.error.stale, key=key)
                    total_inconsistencies += 1
        
        if has_errors:
            bus.error(L.check.run.failure, count=total_inconsistencies)
        else:
            bus.success(L.check.run.success)
            
        return has_errors
~~~~~

#### Acts 4: 实现 CLI 命令与退出码

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
    has_errors = app_instance.run_check()
    if has_errors:
        raise typer.Exit(code=1)
~~~~~

#### Acts 5: 添加集成测试

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
from stitcher.io import YamlAdapter


@pytest.fixture
def mock_bus(monkeypatch):
    mock = MagicMock()
    monkeypatch.setattr("stitcher.app.core.bus", mock)
    return mock


@pytest.fixture
def inconsistent_project(tmp_path: Path):
    project_root = tmp_path / "proj"
    src_dir = project_root / "src"
    src_dir.mkdir(parents=True)
    
    # Config
    (project_root / "pyproject.toml").write_text("[tool.stitcher]\nscan_paths=[\"src\"]")
    
    # Source code: has func1, func2
    (src_dir / "main.py").write_text(dedent("""
    def func1():
        '''Doc for 1'''
    def func2(): # No docstring
        pass
    """))
    
    # Doc file: has func1, func3 (stale), but is missing func2
    (src_dir / "main.stitcher.yaml").write_text(dedent("""
    func1: Doc for 1
    func3: Stale doc for a deleted function
    """))
    
    return project_root


def test_check_finds_inconsistencies(inconsistent_project, mock_bus):
    app = StitcherApp(root_path=inconsistent_project)
    has_errors = app.run_check()
    
    assert has_errors is True
    
    # Assert missing key was reported
    mock_bus.warning.assert_any_call("check.error.missing", key="func2")
    
    # Assert stale key was reported
    mock_bus.error.assert_any_call("check.error.stale", key="func3")
    
    # Assert final failure message
    mock_bus.error.assert_any_call("check.run.failure", count=2)


def test_check_passes_on_consistent_project(tmp_path, mock_bus):
    project_root = tmp_path / "proj"
    (project_root / "pyproject.toml").write_text("[tool.stitcher]\nscan_paths=[\"src\"]")
    (project_root / "src").mkdir()
    (project_root / "src" / "main.py").write_text("def func():\n    '''Hi'''")
    (project_root / "src" / "main.stitcher.yaml").write_text("func: Hi")
    
    app = StitcherApp(root_path=project_root)
    has_errors = app.run_check()
    
    assert has_errors is False
    mock_bus.success.assert_any_call("check.run.success")
~~~~~

### 下一步建议
我们已经完成了第二阶段“文档解耦与工作流完善”的全部核心任务 (`init`, `generate` 升级, `check`)。
现在，项目已经具备了完整的核心价值。

下一步，我们可以进入 **第三阶段：健壮性与高级功能 (打磨与扩展)**。
一个很好的起点是 **任务 3.1: 错误处理与日志记录**。例如，当前如果某个 Python 文件有语法错误，`parse_source_code` 会抛出异常并使整个程序崩溃。我们应该优化它，使其能跳过错误文件、报告问题，然后继续处理其余文件。
