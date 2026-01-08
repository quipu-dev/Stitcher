简要回答
我们将实施 Phase 2，将 `DocumentManager` 与具体的文档风格解耦。这包括修改 `DocumentManager` 以支持通过 `set_strategy` 注入解析器和序列化器，并在 `StitcherApp` 中根据配置动态配置它。这实现了“配置驱动的文档处理”。

## [WIP] feat: 解耦 DocumentManager 并集成结构化文档序列化

### 用户需求
用户希望 `stitcher` 能够根据配置（如 `docstring_style = "google"`）处理不同风格的文档字符串，而不仅仅是原始文本。
具体来说，`DocumentManager` 需要能够：
1.  使用配置指定的 `Parser` 将源代码中的 Docstring 解析为 IR。
2.  使用配置指定的 `Serializer` 将 IR 序列化为结构化的 YAML，并反序列化回 IR。

### 评论
这是实现结构化文档支持的关键一步。目前 `DocumentManager` 硬编码了 `RawDocstringParser` 和简单的字符串处理逻辑。通过引入策略模式和协议，我们不仅支持了 Google/NumPy 风格，还为未来扩展其他格式打下了基础。

### 目标
1.  **重构 `DocumentManager`**:
    *   移除硬编码的解析和序列化逻辑。
    *   引入 `set_strategy(parser, serializer)` 方法。
    *   默认使用 `Raw` 策略以保持向后兼容。
2.  **集成 `StitcherApp`**:
    *   在 `_configure_and_scan` 中读取 `config.docstring_style`。
    *   利用 `stitcher-python-adapter` 提供的工厂获取对应的 Codec 和 Serializer。
    *   将它们注入到 `DocumentManager` 中。

### 基本原理
*   **单一职责原则**: `DocumentManager` 负责协调文档的生命周期（加载、保存、合并），但不应了解具体的文档格式细节。格式细节由 `Parser` 和 `Serializer` 负责。
*   **策略模式**: 允许在运行时根据用户配置切换算法（Google vs NumPy vs Raw）。
*   **SSoT (单一事实来源)**: 确保 IR 是核心的数据交换格式。

### 标签
#intent/refine #flow/ready #priority/high
#comp/runtime #concept/config #scope/core
#task/domain/storage #task/object/doc-manager #task/action/integration #task/state/continue

---

### Script

#### Acts 1: 重构 DocumentManager

我们将修改 `DocumentManager`，使其不再硬编码 `RawDocstringParser`，而是通过 `set_strategy` 方法接收 `DocstringParserProtocol` 和 `DocstringSerializerProtocol`。同时，`_serialize_ir` 和 `_deserialize_ir` 将委托给注入的 `serializer`。

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/services/doc_manager.py
~~~~~
~~~~~python.old
from stitcher.spec import ModuleDef, ClassDef, FunctionDef, DocstringIR
from stitcher.common import DocumentAdapter, YamlAdapter
from stitcher.adapter.python import RawDocstringParser


class DocumentManager:
    def __init__(self, root_path: Path, adapter: Optional[DocumentAdapter] = None):
        self.root_path = root_path
        self.adapter = adapter or YamlAdapter()
        # In Phase 1, we hardcode RawDocstringParser.
        # Future phases will inject this via config.
        self.parser = RawDocstringParser()

    def _deserialize_ir(self, data: Union[str, Dict[str, Any]]) -> DocstringIR:
        if isinstance(data, str):
            return self.parser.parse(data)

        if isinstance(data, dict):
            summary = data.get("Raw", "")
            # Assume other keys starting with "Addon." are addons
            addons = {k: v for k, v in data.items() if k.startswith("Addon.")}

            # Future: Handle structured sections (Args, Returns) here

            ir = self.parser.parse(summary)
            ir.addons = addons
            return ir

        return DocstringIR()

    def _serialize_ir(self, ir: DocstringIR) -> Union[str, Dict[str, Any]]:
        summary = ir.summary or ""

        # If we have addons, we MUST use the dictionary format (Hybrid Mode)
        if ir.addons:
            output = {"Raw": summary}
            output.update(ir.addons)
            # Future: Serialize structured sections here
            return output

        # Otherwise, degrade to simple string (Raw Mode)
        return summary

    def _extract_from_function(
        self, func: FunctionDef, prefix: str = ""
    ) -> Dict[str, DocstringIR]:
~~~~~
~~~~~python.new
from stitcher.spec import (
    ModuleDef,
    ClassDef,
    FunctionDef,
    DocstringIR,
    DocstringParserProtocol,
    DocstringSerializerProtocol,
)
from stitcher.common import DocumentAdapter, YamlAdapter
from stitcher.adapter.python import RawDocstringParser, RawSerializer


class DocumentManager:
    def __init__(self, root_path: Path, adapter: Optional[DocumentAdapter] = None):
        self.root_path = root_path
        self.adapter = adapter or YamlAdapter()
        # Defaults to Raw mode for backward compatibility
        self.parser: DocstringParserProtocol = RawDocstringParser()
        self.serializer: DocstringSerializerProtocol = RawSerializer()

    def set_strategy(
        self,
        parser: DocstringParserProtocol,
        serializer: DocstringSerializerProtocol,
    ):
        """Injects the parsing and serialization strategy."""
        self.parser = parser
        self.serializer = serializer

    def _deserialize_ir(self, data: Union[str, Dict[str, Any]]) -> DocstringIR:
        return self.serializer.from_yaml(data)

    def _serialize_ir(self, ir: DocstringIR) -> Union[str, Dict[str, Any]]:
        return self.serializer.to_yaml(ir)

    def _extract_from_function(
        self, func: FunctionDef, prefix: str = ""
    ) -> Dict[str, DocstringIR]:
~~~~~

#### Acts 2: 更新 DocumentManager 的 docstring

更新 `DocumentManager.stitcher.yaml` 以反映 `set_strategy` 方法的添加和序列化方法的行为变更。

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/services/doc_manager.stitcher.yaml
~~~~~
~~~~~yaml.old
"DocumentManager.root_path": |-
  The root path of the project.
"DocumentManager.save_docs_for_module": |-
  Extracts docs from module (code), serializes them, and saves to YAML.
~~~~~
~~~~~yaml.new
"DocumentManager.root_path": |-
  The root path of the project.
"DocumentManager.save_docs_for_module": |-
  Extracts docs from module (code), serializes them, and saves to YAML.
"DocumentManager.set_strategy": |-
  Configures the parser and serializer used by the manager.
  Allows switching between Raw, Google, and NumPy styles dynamically.
~~~~~

#### Acts 3: 在 StitcherApp 中集成配置驱动的策略注入

修改 `StitcherApp`，使其在处理配置时，根据 `docstring_style` 加载并设置 `DocumentManager` 的策略。

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/core.py
~~~~~
~~~~~python.old
from .runners import (
    CheckRunner,
    GenerateRunner,
    InitRunner,
    PumpRunner,
    TransformRunner,
    CoverageRunner,
)
from .types import PumpResult, FileCheckResult, CoverageResult


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

    def _load_configs(self) -> Tuple[List[StitcherConfig], Optional[str]]:
        return load_config_from_path(self.root_path)

    def _configure_and_scan(self, config: StitcherConfig) -> List[ModuleDef]:
        if config.name != "default":
            bus.info(L.generate.target.processing, name=config.name)
        
        # Future: self.doc_manager.set_strategy(config.docstring_style)

        # Handle Plugins
        plugin_modules = self.scanner.process_plugins(config.plugins)
        
        # Handle Files
        unique_files = self.scanner.get_files_from_config(config)
~~~~~
~~~~~python.new
from .runners import (
    CheckRunner,
    GenerateRunner,
    InitRunner,
    PumpRunner,
    TransformRunner,
    CoverageRunner,
)
from .types import PumpResult, FileCheckResult, CoverageResult
from stitcher.adapter.python.docstring import (
    get_docstring_codec,
    get_docstring_serializer,
)


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

    def _load_configs(self) -> Tuple[List[StitcherConfig], Optional[str]]:
        return load_config_from_path(self.root_path)

    def _configure_and_scan(self, config: StitcherConfig) -> List[ModuleDef]:
        if config.name != "default":
            bus.info(L.generate.target.processing, name=config.name)

        # Configure Docstring Strategy
        parser, _ = get_docstring_codec(config.docstring_style)
        serializer = get_docstring_serializer(config.docstring_style)
        self.doc_manager.set_strategy(parser, serializer)

        # Handle Plugins
        plugin_modules = self.scanner.process_plugins(config.plugins)

        # Handle Files
        unique_files = self.scanner.get_files_from_config(config)
~~~~~

### 下一步建议

现在 `DocumentManager` 已经具备了处理结构化文档的能力。接下来的步骤是：
1.  **阶段 3: 渲染管线集成**: 修改 `GenerateRunner` 和 `StubGenerator`，以便在生成 `.pyi` 文件时使用结构化信息（如 `Args`、`Returns`），而不仅仅是简单的字符串。这将需要更新 `DocumentManager.apply_docs_to_module` 逻辑，以及引入 Renderer。
2.  **验证**: 添加针对 Google 和 NumPy 风格的端到端测试，验证从代码到 YAML 再回代码的完整循环。
