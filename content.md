分析完全正确。由于 `_UsageVisitor`（更名为 `UsageScanVisitor`）和 `UsageRegistry` 的物理位置已经从 `stitcher-refactor` 下沉到了 `stitcher-python-analysis`，原有的单元测试也必须同步迁移并更新引用，以符合“测试与其验证的代码共存”的原则。

我将生成一个计划，将该测试文件迁移到新包并修复其导入。

## [WIP] fix(testing): 迁移并修复 UsageVisitor 测试至 stitcher-python-analysis

### 错误分析

测试 `packages/stitcher-refactor/tests/unit/engine/test_graph_visitor.py` 失败，是因为它尝试从 `stitcher.refactor.engine.graph` 导入已经不存在的 `_UsageVisitor` 和 `UsageRegistry`。

在之前的重构中：
1.  `_UsageVisitor` 被更名为 `UsageScanVisitor` 并移动到了 `stitcher.python.analysis.cst.usage_visitor`。
2.  `UsageRegistry` 被移动到了 `stitcher.python.analysis.cst.usage_visitor`。

因此，该测试文件目前处于“逻辑真空”状态，必须迁移到新包并指向正确的类名和路径。

### 用户需求

解决由于重构导致的测试搜集失败，确保 `UsageScanVisitor` 的逻辑仍然得到正确验证。

### 评论

这是 Monorepo 架构中典型的测试迁移任务。将测试与逻辑同步迁移，不仅解决了当前的导入错误，也确保了 `stitcher-python-analysis` 作为一个独立包，其核心分析组件拥有完备的单元测试。

### 目标

1.  在 `stitcher-python-analysis` 包中创建相应的测试目录结构。
2.  将测试逻辑迁移至 `packages/stitcher-python-analysis/tests/unit/cst/test_usage_visitor.py`。
3.  更新测试代码，使用新的类名 `UsageScanVisitor` 并修正导入路径。
4.  删除 `stitcher-refactor` 中过时的测试文件。

### 基本原理

遵循 Monorepo 测试原则，单元测试必须位于其所验证的代码所在的包内。这有助于保持包的自治性，并简化 CI 流程中的测试搜集逻辑。

### 标签

#intent/fix #flow/ready #priority/high #comp/tests #scope/core #ai/instruct #task/domain/testing #task/object/usage-visitor-tests #task/action/migrate #task/state/continue

---

### Script

#### Acts 1: 创建新包的测试目录

~~~~~act
run_command
~~~~~
~~~~~
mkdir -p packages/stitcher-python-analysis/tests/unit/cst
~~~~~

#### Acts 2: 迁移并修正测试文件

我们将原有的测试逻辑写入新位置，并修正所有导入引用和类名。

~~~~~act
write_file
packages/stitcher-python-analysis/tests/unit/cst/test_usage_visitor.py
~~~~~
~~~~~python
import libcst as cst
from pathlib import Path
from stitcher.python.analysis.cst.usage_visitor import UsageScanVisitor, UsageRegistry


def parse_and_visit(code: str, module_fqn: str = "mypkg.mod"):
    """
    Helper to run UsageScanVisitor on a snippet of code.
    """
    registry = UsageRegistry()
    wrapper = cst.MetadataWrapper(cst.parse_module(code))

    # Mock symbols not needed for Import testing unless we test Name resolution
    local_symbols = {}

    is_init = module_fqn.endswith(".__init__")

    visitor = UsageScanVisitor(
        file_path=Path("dummy.py"),
        local_symbols=local_symbols,
        registry=registry,
        current_module_fqn=module_fqn,
        is_init_file=is_init,
    )
    wrapper.visit(visitor)
    return registry


def test_visitor_absolute_import_from():
    code = "from mypkg.core import Helper"
    registry = parse_and_visit(code, module_fqn="main")

    # We expect 'Helper' in the import statement to be registered as usage of 'mypkg.core.Helper'
    usages = registry.get_usages("mypkg.core.Helper")
    assert len(usages) == 1
    # Verify it points to 'Helper'
    # "from mypkg.core import Helper"
    #                        ^
    assert usages[0].col_offset > 0


def test_visitor_absolute_import_from_with_alias():
    code = "from mypkg.core import Helper as H"
    registry = parse_and_visit(code, module_fqn="main")

    # We expect 'Helper' (the source name) to be usage of 'mypkg.core.Helper'
    usages = registry.get_usages("mypkg.core.Helper")
    assert len(usages) == 1


def test_visitor_relative_import():
    # Context: mypkg.sub.mod
    # Code: from . import sibling
    code = "from . import sibling"
    registry = parse_and_visit(code, module_fqn="mypkg.sub.mod")

    # Should resolve to mypkg.sub.sibling
    usages = registry.get_usages("mypkg.sub.sibling")
    assert len(usages) == 1


def test_visitor_relative_import_from_parent():
    # Context: mypkg.sub.mod
    # Code: from ..core import Helper
    code = "from ..core import Helper"
    registry = parse_and_visit(code, module_fqn="mypkg.sub.mod")

    # Should resolve to mypkg.core.Helper
    usages = registry.get_usages("mypkg.core.Helper")
    assert len(usages) == 1


def test_visitor_top_level_import():
    # Context: main (top level)
    # Code: from mypkg import core
    code = "from mypkg import core"
    registry = parse_and_visit(code, module_fqn="main")

    # Should resolve to mypkg.core
    usages = registry.get_usages("mypkg.core")
    assert len(usages) == 1
~~~~~

#### Acts 3: 清理旧测试文件

~~~~~act
delete_file
packages/stitcher-refactor/tests/unit/engine/test_graph_visitor.py
~~~~~

### 下一步建议

测试迁移完成后，建议再次运行所有测试。如果此时 `stitcher-refactor` 包的测试搜集通过且 `stitcher-python-analysis` 的新测试通过，则证明基础层的下沉已经完全稳固。

接下来的工作可以聚焦于：
- **统一 Griffe 缓存管理**: 目前 `SemanticGraph` 手动管理 `GriffeLoader`。我们可以在 `stitcher-python-analysis` 中建立一个 `PythonAnalysisService`，用来管理共享的 `GriffeLoader` 实例，从而进一步减少内存占用并提高跨组件的分析速度。
