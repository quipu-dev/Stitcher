好的，切换回 Quipu 模式。

我将生成一个临时计划来修复测试用例，通过补全缺失的 `__init__.py` 文件来验证我们的分析。如果测试通过，就证明了问题的根源在于项目结构而非引擎核心逻辑。

## [WIP] test: 补全缺失的 `__init__.py` 以验证重构引擎的假设

### 错误分析
根据我们的战略分析，`test_debug_rename_failure_analysis` 失败的根本原因是测试工作区中的 `stitcher.common.messaging` 目录缺少 `__init__.py` 文件。这导致 Python 的导入系统（以及 Griffe）无法将其识别为一个合法的子包，从而跳过了对 `bus.py` 文件的扫描。因此，`MessageBus` 的类定义从未被 `UsageRegistry` 索引，导致重命名操作失败。

### 用户需求
临时修改 `test_debug_rename_failure_analysis.py` 测试用例，在 `WorkspaceFactory` 的构建指令中为 `messaging` 目录添加一个空的 `__init__.py` 文件，以验证修复项目结构后，重构引擎能否成功重命名符号定义。

### 评论
这是一个至关重要的验证步骤。它能清晰地将问题隔离出来，证明我们对问题根源的判断是正确的，并为后续是“修复引擎”还是“规范项目”提供决策依据。

### 目标
1.  定位 `packages/stitcher-refactor/tests/integration/test_debug_rename_failure.py` 文件。
2.  在 `WorkspaceFactory` 的链式调用中，为 `packages/stitcher-common/src/stitcher/common/messaging/` 路径添加一个 `__init__.py` 文件。

### 基本原理
通过添加 `__init__.py`，`stitcher.common.messaging` 目录将成为一个常规的 Python 包。Griffe 在扫描 `stitcher.common` 时将能够正确地递归进入该子包，进而解析 `bus.py`。`_UsageVisitor` 将扫描到 `class MessageBus` 的定义，并将其 FQN (`stitcher.common.messaging.bus.MessageBus`) 及其位置注册到 `UsageRegistry` 中。最终，`RenameSymbolOperation` 在分析阶段就能找到这个定义的位置，并生成正确的 `WriteFileOp` 来修改它。

### 标签
#intent/tooling #flow/ready #priority/critical #comp/tests #concept/state #scope/dx #ai/instruct #task/domain/testing #task/object/test-case #task/action/validation #task/state/continue

---

### Script

#### Acts 1: 在测试用例中补全 `__init__.py`

我们将在 `WorkspaceFactory` 的构建流程中，为 `messaging` 目录添加一个空的 `__init__.py`，使其成为一个有效的包。

~~~~~act
patch_file
packages/stitcher-refactor/tests/integration/test_debug_rename_failure.py
~~~~~
~~~~~python.old
        # Simulate the protocols.py needed for import resolution
        .with_source(
            "packages/stitcher-common/src/stitcher/common/messaging/protocols.py",
            "class Renderer: pass"
        )
        # Use REAL content for bus.py
        .with_source(
            "packages/stitcher-common/src/stitcher/common/messaging/bus.py", 
            BUS_PY_CONTENT
        )
        .build()
~~~~~
~~~~~python.new
        # Simulate the protocols.py needed for import resolution
        .with_source(
            "packages/stitcher-common/src/stitcher/common/messaging/protocols.py",
            "class Renderer: pass"
        )
        # Add the missing __init__.py to make 'messaging' a valid package
        .with_source(
            "packages/stitcher-common/src/stitcher/common/messaging/__init__.py",
            ""
        )
        # Use REAL content for bus.py
        .with_source(
            "packages/stitcher-common/src/stitcher/common/messaging/bus.py", 
            BUS_PY_CONTENT
        )
        .build()
~~~~~

### 下一步建议
请执行此计划并重新运行测试。如果测试通过，就证实了我们的分析是正确的。

确认成功后，请告诉我，我将生成一个计划来**回滚**这次的测试文件修改，以便我们接下来可以专注于从根本上解决引擎的鲁棒性问题。
