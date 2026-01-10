You are absolutely right. The test failures are a direct result of my previous plan. I successfully refactored the `StitcherApp` constructor in the `stitcher-application` package, but I failed to update the factory function (`make_app`) in the `stitcher-cli` package that is responsible for instantiating it.

This created a mismatch between the class definition and its usage, leading to the `TypeError` you've correctly identified. My apologies for this oversight.

I will now generate a plan to correct this error by aligning the factory with the new `StitcherApp` constructor.

## [WIP] fix(cli): Align StitcherApp factory with updated constructor

### 错误分析

测试套件大面积失败的根本原因是 `stitcher-cli` 包中的工厂函数 `make_app` 依然在使用旧的 `StitcherApp` 构造函数签名。

在之前的重构中，我们修改了 `stitcher.app.core.StitcherApp` 的 `__init__` 方法，移除了 `stub_generator: StubGeneratorProtocol` 参数。然而，负责创建 `StitcherApp` 实例的 `stitcher.cli.factories.make_app` 函数没有被同步更新。

因此，当测试或 CLI 命令尝试通过 `make_app` 创建 `StitcherApp` 实例时，它仍然传递了已被移除的 `stub_generator` 关键字参数，从而导致了 `TypeError`。几乎所有集成测试都依赖这个工厂，所以这个单一的错误导致了整个测试套件的崩溃。

### 用户需求

修复因 `StitcherApp` 构造函数签名变更而导致的 `TypeError`，使测试套件能够恢复正常运行。

### 评论

这是一个在 monorepo 架构中进行跨包重构时典型的集成错误。它凸显了修改一个包的公共 API（即使只是构造函数）后，必须立即更新所有消费方的重要性。修复这个问题的正确位置正是在 `make_app` 工厂中，因为它作为“组合根”，是连接 `cli` 包和 `application` 包的关键枢纽。修正它将一次性修复所有依赖此工厂的测试用例。

### 目标

1.  定位 `packages/stitcher-cli/src/stitcher/cli/factories.py` 中的 `make_app` 函数。
2.  修改其中对 `StitcherApp(...)` 的调用，移除 `stub_generator=generator` 这个参数，使其与 `stitcher.app.core.StitcherApp` 的新构造函数签名保持一致。

### 基本原理

我们将使用一个精确的 `patch_file` 操作来修复这个问题。`old_str` 将会包含 `make_app` 函数中整个 `return StitcherApp(...)` 的调用块。`new_str` 将是同样的代码块，但会删除掉传递 `stub_generator` 的那一行。这是一个外科手术式的修复，能以最小的改动解决这个阻断性的问题。

### 标签

#intent/fix #flow/ready #priority/critical #comp/cli #comp/application #scope/dx #task/domain/architecture #task/object/stubgen-package #task/action/integration #task/state/continue

---

### Script

#### Acts 1: 修正 `make_app` 工厂函数

我们将更新 `stitcher-cli` 中的 `make_app` 函数，使其调用 `StitcherApp` 的新构造函数签名。

~~~~~act
patch_file
packages/stitcher-cli/src/stitcher/cli/factories.py
~~~~~
~~~~~python
def make_app(
    handler: Optional[InteractionHandler] = None,
) -> StitcherApp:
    # Composition Root: Assemble the dependencies
    # UNIFIED: Always use Griffe for analysis
    parser = GriffePythonParser()

    transformer = PythonTransformer()
    generator = PythonStubGenerator()
    strategy = PythonFingerprintStrategy()

    return StitcherApp(
        root_path=get_project_root(),
        parser=parser,
        transformer=transformer,
        stub_generator=generator,
        fingerprint_strategy=strategy,
        interaction_handler=handler,
    )
~~~~~
~~~~~python
def make_app(
    handler: Optional[InteractionHandler] = None,
) -> StitcherApp:
    # Composition Root: Assemble the dependencies
    # UNIFIED: Always use Griffe for analysis
    parser = GriffePythonParser()

    transformer = PythonTransformer()
    strategy = PythonFingerprintStrategy()

    return StitcherApp(
        root_path=get_project_root(),
        parser=parser,
        transformer=transformer,
        fingerprint_strategy=strategy,
        interaction_handler=handler,
    )
~~~~~

### 下一步建议

这个修复应该能够解决所有由 `TypeError` 引起的测试失败。一旦测试通过，我们就可以继续我们重构的最后一步：

**清理冗余文件**。我将生成一个计划来删除 `stitcher-application` 和 `stitcher-python-adapter` 中现在已经不再被使用的旧文件 (`GenerateRunner`, `StubPackageManager`, `PythonStubGenerator` 等)，以完成整个架构重构。
