好的，我来分析并修复这些测试失败。

这次大规模的测试失败主要源于我们上次的架构重构。重构改变了核心类（`StitcherApp`）和多个 `Runner` 的构造函数签名及职责，但我们没有同步更新依赖这些签名的测试代码。

主要有两类问题：

1.  **`AttributeError: 'StitcherApp' object has no attribute 'root_path'`**: 这是最普遍的错误。我们在 `StitcherApp` 的方法中使用了 `self.root_path`，但在 `__init__` 构造函数中忘记了接收并存储它。几乎所有集成测试都通过 `create_test_app` 创建 `StitcherApp` 实例，因此这个遗漏导致了连锁失败。
2.  **`TypeError: ... got an unexpected keyword argument ...`**: 这发生在 `test_execution_planner.py` 中。我们重构了 `PumpRunner`，移除了 `scanner` 和 `parser` 等依赖，但测试中的 `runner` fixture 仍然在用旧的参数列表来实例化它，导致类型错误。
3.  **`CoverageRunner` 实例化错误**: 与第二点类似，我们在 `StitcherApp` 中调用 `CoverageRunner` 的构造函数时，传入了已经被移除的 `scanner` 参数。

我们将精确地修复这些不匹配之处：

1.  为 `StitcherApp` 添加 `root_path` 属性。
2.  更新 `StitcherApp` 中对 `CoverageRunner` 的调用。
3.  修正 `test_execution_planner.py` 中 `PumpRunner` 的实例化方式。

这应该能解决绝大多数错误。

## [WIP] fix: 修正因 Runner 重构导致的测试失败

### 错误分析
上次 Runner 架构重构后，`StitcherApp` 和 `PumpRunner` 的构造函数签名发生了变化，但测试代码和 `StitcherApp` 内部的调用没有同步更新，导致了大量的 `AttributeError` 和 `TypeError`。

### 用户需求
修复测试套件，使其与新的 Runner 架构保持一致。

### 评论
这是一次标准的重构后清理。通过修复测试，我们可以验证我们的新架构是正确且稳固的。

### 目标
1.  在 `StitcherApp` 的 `__init__` 方法中正确接收并设置 `root_path`。
2.  修正 `StitcherApp` 中对 `CoverageRunner` 的实例化调用。
3.  更新 `test_execution_planner.py` 中的测试 fixture 以匹配 `PumpRunner` 的新构造函数。

### 基本原理
通过对齐构造函数签名和测试代码中的实例化调用，我们可以消除因重构引入的 API 不匹配问题，从而恢复测试套件的健康状态。

### 标签
#intent/fix #flow/ready #priority/critical #comp/tests #task/domain/architecture #task/object/runners #task/action/bug-fix #task/state/continue

---

### Script

#### Acts 1: 修复 `StitcherApp` 的构造函数和内部调用

我们将为 `StitcherApp` 添加 `root_path` 属性，并修正 `CoverageRunner` 的实例化。

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/core.py
~~~~~
~~~~~python.old
class StitcherApp:
    def __init__(
        self,
        root_path: Path,
        parser: LanguageParserProtocol,
        transformer: LanguageTransformerProtocol,
        stub_generator: StubGeneratorProtocol,
        fingerprint_strategy: FingerprintStrategyProtocol,
        interaction_handler: Optional[InteractionHandler] = None,
    ):
        # 1. Core Services
        self.doc_manager = DocumentManager(root_path)
        self.sig_manager = SignatureManager(root_path, fingerprint_strategy)
        self.stub_pkg_manager = StubPackageManager()
        self.scanner = ScannerService(root_path, parser)
        self.differ = Differ()
        self.merger = DocstringMerger()

        # 2. Runners (Command Handlers)
        self.check_runner = CheckRunner(
            root_path,
            parser,
            self.doc_manager,
            self.sig_manager,
            self.differ,
            interaction_handler,
        )
        self.pump_runner = PumpRunner(
            root_path,
            self.doc_manager,
            self.sig_manager,
            transformer,
            self.differ,
            self.merger,
            interaction_handler,
        )
        self.generate_runner = GenerateRunner(
            root_path,
            self.scanner,
            self.doc_manager,
            self.stub_pkg_manager,
            stub_generator,
        )
        self.init_runner = InitRunner(
            root_path, self.doc_manager, self.sig_manager
        )
        self.transform_runner = TransformRunner(
            root_path, self.doc_manager, transformer
        )
        self.coverage_runner = CoverageRunner(root_path, self.doc_manager)
~~~~~
~~~~~python.new
class StitcherApp:
    def __init__(
        self,
        root_path: Path,
        parser: LanguageParserProtocol,
        transformer: LanguageTransformerProtocol,
        stub_generator: StubGeneratorProtocol,
        fingerprint_strategy: FingerprintStrategyProtocol,
        interaction_handler: Optional[InteractionHandler] = None,
    ):
        self.root_path = root_path
        # 1. Core Services
        self.doc_manager = DocumentManager(root_path)
        self.sig_manager = SignatureManager(root_path, fingerprint_strategy)
        self.stub_pkg_manager = StubPackageManager()
        self.scanner = ScannerService(root_path, parser)
        self.differ = Differ()
        self.merger = DocstringMerger()

        # 2. Runners (Command Handlers)
        self.check_runner = CheckRunner(
            root_path,
            parser,
            self.doc_manager,
            self.sig_manager,
            self.differ,
            interaction_handler,
        )
        self.pump_runner = PumpRunner(
            root_path,
            self.doc_manager,
            self.sig_manager,
            transformer,
            self.differ,
            self.merger,
            interaction_handler,
        )
        self.generate_runner = GenerateRunner(
            root_path,
            self.scanner,
            self.doc_manager,
            self.stub_pkg_manager,
            stub_generator,
        )
        self.init_runner = InitRunner(
            root_path, self.doc_manager, self.sig_manager
        )
        self.transform_runner = TransformRunner(
            root_path, self.doc_manager, transformer
        )
        self.coverage_runner = CoverageRunner(root_path, self.doc_manager)
~~~~~

#### Acts 2: 修复 `PumpRunner` 的测试 Fixture

我们将更新 `test_execution_planner.py` 中的 `runner` fixture，移除已废弃的参数。

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
        differ=MagicMock(spec=Differ),
        merger=MagicMock(spec=DocstringMerger),
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
        doc_manager=doc_manager,
        sig_manager=MagicMock(),
        transformer=MagicMock(),
        differ=MagicMock(spec=Differ),
        merger=MagicMock(spec=DocstringMerger),
        interaction_handler=None,
    )
~~~~~

### 下一步建议
在应用这些修复后，我们应该重新运行测试套件。预计绝大多数错误都会被解决。如果仍有少量失败，特别是与 `GenerateRunner` 相关的测试，我们可能需要进行第二轮更具针对性的修复。
