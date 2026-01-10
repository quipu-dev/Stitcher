你又抓到了一个关键的疏忽。我的重构确实漏掉了测试代码。

根据**测试原则 (`d3-principle-pytest-monorepo-architecture`)**，测试用例必须与其验证的代码在物理上共存。既然我们将存根生成逻辑从 `stitcher-python-adapter` 迁移到了 `stitcher-stubgen`，那么对应的单元测试也必须随之迁移，并更新其导入路径。

这是一个典型的“代码先走，测试掉队”导致的 `ModuleNotFoundError`。我将生成一个计划来修复它。

## [WIP] refactor(tests): Migrate stub generator unit tests to stitcher-stubgen

### 错误分析

测试 `test_stub_generator.py` 报错 `ModuleNotFoundError` 的根本原因是：
1.  **逻辑已迁移**: 存根生成的内部核心逻辑（原 `StubGenerator`）已经从 `stitcher-python-adapter` 移动到了 `stitcher-stubgen` 包，并重命名为 `PythonStubGenerator`。
2.  **测试遗留**: 该单元测试文件被遗留在旧的 `stitcher-python-adapter` 包中，且其导入语句指向的路径已在物理上被删除。

由于该测试验证的是生成器的核心算法，它属于 `stitcher-stubgen` 领域的单元测试，必须跟随逻辑一起迁移。

### 用户需求

修复因存根生成逻辑迁移而导致的单元测试失败，并将相关测试迁移到正确的新包中。

### 评论

这次修复完善了我们的重构工作。在 Monorepo 中，保持测试与源码的物理对齐对于长期可维护性至关重要。这不仅修复了当前的报错，也确保了 `stitcher-stubgen` 包现在是一个功能完整、自包含且拥有自己测试集的独立模块。这完全符合我们的**单包高内聚**原则。

### 目标

1.  将 `test_stub_generator.py` 从 `stitcher-python-adapter` 迁移到 `stitcher-stubgen`。
2.  更新测试文件中的导入路径，使其指向新包中的 `PythonStubGenerator`。
3.  更新测试代码中的类名和调用，以匹配新的 `PythonStubGenerator`。

### 基本原理

我们将按照以下步骤执行：
1.  **物理移动**: 使用 `run_command` 创建目标测试目录，并使用 `move_file` 将测试文件移动到新包。
2.  **代码修正**: 使用 `patch_file` 对迁移后的测试文件进行“手术”，将已不存在的 `StubGenerator` 替换为新包提供的 `PythonStubGenerator`。

### 标签

#intent/refine #flow/ready #priority/high #comp/tests #comp/python-adapter #comp/stubgen #scope/dx #task/domain/architecture #task/object/stubgen-package #task/action/test-migration #task/state/continue

---

### Script

#### Acts 1: 迁移测试文件

我们首先为 `stitcher-stubgen` 创建单元测试目录，并将测试文件移动过去。

~~~~~act
run_command
~~~~~
~~~~~
mkdir -p packages/stitcher-stubgen/tests/unit
~~~~~

~~~~~act
move_file
packages/stitcher-python-adapter/tests/unit/test_stub_generator.py
packages/stitcher-stubgen/tests/unit/test_stub_generator.py
~~~~~

#### Acts 2: 更新测试代码中的引用

现在，我们修正迁移后的测试文件中的导入和类引用。

~~~~~act
patch_file
packages/stitcher-stubgen/tests/unit/test_stub_generator.py
~~~~~
~~~~~python
    ArgumentKind,
    Attribute,
)
from stitcher.adapter.python.internal.stub_generator import StubGenerator


class TestStubGenerator:
    @pytest.fixture
    def generator(self):
        return StubGenerator()
~~~~~
~~~~~python
    ArgumentKind,
    Attribute,
)
from stitcher.stubgen.generator import PythonStubGenerator


class TestStubGenerator:
    @pytest.fixture
    def generator(self):
        return PythonStubGenerator()
~~~~~

### 下一步建议

这个修复应该能解决最后一个已知的 `ImportError`。

现在，`stitcher-stubgen` 拥有了它自己的源码、配置、服务接口以及验证这些逻辑的单元测试。这是一个非常整洁的状态。我建议你再次运行测试，如果全部通过，我们就可以进行最终的 **`[COMMIT]`**。
