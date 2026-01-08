好的，我来修复这个测试。

[简要回答]
你的分析完全正确。由于之前的重构更改了 `PumpRunner` 的构造函数签名，注入了 `Differ` 和 `Merger` 服务，导致依赖此构造函数的单元测试 `test_execution_planner.py` 在创建 `PumpRunner` 实例时失败。

我将更新测试中的 `runner` fixture，为其提供所需的 mock 依赖项，以修复这些 `TypeError` 错误。

## [WIP] test: 修复因 PumpRunner 构造函数变更导致的单元测试失败

### 错误分析
错误 `TypeError: PumpRunner.__init__() missing 2 required positional arguments: 'differ' and 'merger'` 明确指出，在 `packages/stitcher-application/tests/unit/test_execution_planner.py` 文件中，用于创建 `PumpRunner` 实例的 `runner` fixture 没有提供新的 `differ` 和 `merger` 参数。这是上一步重构引入的必然结果，测试代码需要与产品代码的接口保持同步。

### 用户需求
修复 `test_execution_planner.py` 中的所有 `TypeError`，使单元测试套件能够成功运行。

### 评论
这是依赖注入重构中非常典型且必要的一步。测试是代码质量的守护者，确保它们与接口的变化保持一致是至关重要的。幸运的是，由于被测试的方法 `_generate_execution_plan` 并不实际使用这两个新服务，我们只需提供 mock 对象即可，修复工作非常直接。

### 目标
1.  在 `test_execution_planner.py` 中导入 `Differ` 和 `DocstringMerger`。
2.  修改 `runner` fixture，在调用 `PumpRunner` 构造函数时，传入 `differ` 和 `merger` 的 mock 对象。

### 基本原理
测试 fixture 必须与被测对象的构造函数（`__init__`）签名严格匹配。当构造函数增加新的依赖项时，fixture 必须相应地提供这些依赖项的真实实例或 mock 实例，以确保对象能够被成功创建。

### 标签
#intent/fix #flow/ready #priority/critical #comp/tests #scope/dx #ai/instruct
#task/domain/testing #task/object/unit-test #task/action/bug-fix #task/state/continue

---

### Script

#### Acts 1: 更新测试文件的导入

首先，我们需要导入 `Differ` 和 `DocstringMerger` 类，以便在创建 mock 对象时使用 `spec` 来增强类型安全性。

~~~~~act
patch_file
packages/stitcher-application/tests/unit/test_execution_planner.py
~~~~~
~~~~~python.old
import pytest
from unittest.mock import MagicMock
from stitcher.app.runners import PumpRunner
from stitcher.app.services import DocumentManager
from stitcher.spec import (
    ModuleDef,
~~~~~
~~~~~python.new
import pytest
from unittest.mock import MagicMock
from stitcher.app.runners import PumpRunner
from stitcher.app.services import DocumentManager, Differ, DocstringMerger
from stitcher.spec import (
    ModuleDef,
~~~~~

#### Acts 2: 修复 `runner` fixture

现在，更新 `runner` fixture，为 `PumpRunner` 提供缺失的 `differ` 和 `merger` 参数。

~~~~~act
patch_file
packages/stitcher-application/tests/unit/test_execution_planner.py
~~~~~
~~~~~python.old
@pytest.fixture
def runner(tmp_path) -> PumpRunner:
    """一个用于调用内部方法的PumpRunner实例。"""
    # _generate_execution_plan 仅依赖 doc_manager
    doc_manager = DocumentManager(root_path=tmp_path)
    return PumpRunner(
        root_path=tmp_path,
        scanner=MagicMock(),
        parser=MagicMock(),
        doc_manager=doc_manager,
        sig_manager=MagicMock(),
        transformer=MagicMock(),
        interaction_handler=None,
    )
~~~~~
~~~~~python.new
@pytest.fixture
def runner(tmp_path) -> PumpRunner:
    """一个用于调用内部方法的PumpRunner实例。"""
    # _generate_execution_plan 仅依赖 doc_manager
    doc_manager = DocumentManager(root_path=tmp_path)
    return PumpRunner(
        root_path=tmp_path,
        scanner=MagicMock(),
        parser=MagicMock(),
        doc_manager=doc_manager,
        sig_manager=MagicMock(),
        transformer=MagicMock(),
        differ=MagicMock(spec=Differ),
        merger=MagicMock(spec=DocstringMerger),
        interaction_handler=None,
    )
~~~~~

### 下一步建议
测试现在应该可以成功通过了。由于我们已经完成了 Pre-Phase 2 的重构和测试修复，代码库现在处于一个更健康、更解耦的状态。

我们可以安全地进入下一个阶段：
- **执行 Phase 2**: 开始实现对 Google/NumPy 风格文档的完整结构化支持，这会涉及升级 `GriffeDocstringParser` 和 `DocstringMerger` 的具体实现。
- **提交变更**: 在开始 Phase 2 之前，我们可以将当前的重构和修复作为一个完整的 `[COMMIT]` 提交，以固化这个稳定的架构节点。
