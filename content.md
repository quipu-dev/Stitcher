# [WIP] refactor: 重构文档生成流程为骨架生成加注入的两阶段模式

## 摘要头

### 用户需求
修复文档字符串生成时的格式错误（空行缩进问题）和 Google 风格渲染的缩进问题。

### 评论
当前的“字符串拼接”方式在处理复杂的文档格式化时显得极其脆弱且难以维护。通过引入 LibCST 进行后处理注入，我们将代码结构的生成（骨架）与文档内容的生成（注入）解耦，这符合“正规军”工程标准，能从根本上解决缩进和格式化问题。

### 目标
1.  重构 `GenerateRunner`，使其采用“生成骨架 -> 渲染文档 -> 注入文档”的三步走策略。
2.  修改 `StubGenerator`，使其仅负责生成无文档的 Python 存根骨架。
3.  在 `GenerateRunner` 中集成 `Renderer` 和 `Transformer`，以支持文档的渲染和注入。

### 基本原理
1.  **骨架生成**: `StubGenerator` 不再关心文档字符串的格式化，只生成纯净的 Python 语法结构（如 `def foo(): ...`）。这消除了手动拼接 docstring 时的缩进错误风险。
2.  **文档渲染**: `GenerateRunner` 使用 `DocstringRenderer` 将 IR 转换为符合特定风格（如 Google Style）的字符串。
3.  **CST 注入**: 利用 `LibCST`（通过 `Transformer`）将渲染好的文档字符串解析并插入到对应的语法节点中。LibCST 会自动处理缩进和换行，确保输出代码的语法正确性和格式规范性。

### 标签
#intent/refine #flow/ready #priority/high #comp/runtime #comp/adapter #concept/codegen #task/domain/testing #task/object/docstring-generation #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 修改 `GenerateRunner` 以支持两阶段生成

我们需要修改 `GenerateRunner`，使其能够接收 `transformer` 和 `renderer`，并在 `run_batch` 中执行骨架生成和文档注入的逻辑。

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/runners/generate.py
~~~~~
~~~~~python.old
from stitcher.spec import ModuleDef, StubGeneratorProtocol
from stitcher.app.services import (
    DocumentManager,
    StubPackageManager,
    ScannerService,
)


class GenerateRunner:
    def __init__(
        self,
        root_path: Path,
        scanner: ScannerService,
        doc_manager: DocumentManager,
        stub_pkg_manager: StubPackageManager,
        generator: StubGeneratorProtocol,
    ):
        self.root_path = root_path
        self.scanner = scanner
        self.doc_manager = doc_manager
        self.stub_pkg_manager = stub_pkg_manager
        self.generator = generator

    def _scaffold_stub_package(
~~~~~
~~~~~python.new
from typing import List, Optional, Dict
from pathlib import Path

from stitcher.common import bus
from needle.pointer import L
from stitcher.config import StitcherConfig
from stitcher.spec import (
    ModuleDef,
    StubGeneratorProtocol,
    LanguageTransformerProtocol,
    DocstringRendererProtocol,
)
from stitcher.app.services import (
    DocumentManager,
    StubPackageManager,
    ScannerService,
)


class GenerateRunner:
    def __init__(
        self,
        root_path: Path,
        scanner: ScannerService,
        doc_manager: DocumentManager,
        stub_pkg_manager: StubPackageManager,
        generator: StubGeneratorProtocol,
        transformer: LanguageTransformerProtocol,
    ):
        self.root_path = root_path
        self.scanner = scanner
        self.doc_manager = doc_manager
        self.stub_pkg_manager = stub_pkg_manager
        self.generator = generator
        self.transformer = transformer
        self.renderer: Optional[DocstringRendererProtocol] = None

    def set_renderer(self, renderer: DocstringRendererProtocol) -> None:
        self.renderer = renderer

    def _render_docs_for_module(self, module: ModuleDef) -> Dict[str, str]:
        docs = {}
        if not self.renderer:
            return {}

        # Module doc
        if module.docstring_ir:
            docs["__doc__"] = self.renderer.render(module.docstring_ir, context=module)

        # Functions
        for func in module.functions:
            if func.docstring_ir:
                docs[func.name] = self.renderer.render(func.docstring_ir, context=func)

        # Classes
        for cls in module.classes:
            if cls.docstring_ir:
                docs[cls.name] = self.renderer.render(cls.docstring_ir, context=cls)
            # Methods
            for method in cls.methods:
                if method.docstring_ir:
                    fqn = f"{cls.name}.{method.name}"
                    docs[fqn] = self.renderer.render(
                        method.docstring_ir, context=method
                    )

        return docs

    def _scaffold_stub_package(
~~~~~

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/runners/generate.py
~~~~~
~~~~~python.old
        for module in modules:
            self.doc_manager.apply_docs_to_module(module)
            pyi_content = self.generator.generate(module)
            if config.stub_package:
                logical_path = self.scanner.derive_logical_path(module.file_path)
~~~~~
~~~~~python.new
        for module in modules:
            self.doc_manager.apply_docs_to_module(module)

            # Phase 1: Generate Skeleton
            skeleton_code = self.generator.generate(module)

            # Phase 2: Render Docs
            docs_map = self._render_docs_for_module(module)

            # Phase 3: Inject Docs
            final_content = self.transformer.inject(skeleton_code, docs_map)

            if config.stub_package:
                logical_path = self.scanner.derive_logical_path(module.file_path)
~~~~~

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/runners/generate.py
~~~~~
~~~~~python.old
            if config.stub_package:
                src_root = self.root_path / config.stub_package / "src"
                current = output_path.parent
                while current != src_root and src_root in current.parents:
                    (current / "__init__.pyi").touch(exist_ok=True)
                    current = current.parent
            output_path.write_text(pyi_content, encoding="utf-8")
            relative_path = output_path.relative_to(self.root_path)
            bus.success(L.generate.file.success, path=relative_path)
            generated_files.append(output_path)
        return generated_files
~~~~~
~~~~~python.new
            if config.stub_package:
                src_root = self.root_path / config.stub_package / "src"
                current = output_path.parent
                while current != src_root and src_root in current.parents:
                    (current / "__init__.pyi").touch(exist_ok=True)
                    current = current.parent
            output_path.write_text(final_content, encoding="utf-8")
            relative_path = output_path.relative_to(self.root_path)
            bus.success(L.generate.file.success, path=relative_path)
            generated_files.append(output_path)
        return generated_files
~~~~~

#### Acts 2: 更新 StitcherApp 以注入 Transformer 和 Renderer

我们需要更新 `StitcherApp`，将 `transformer` 传递给 `GenerateRunner`，并将 `renderer` 设置给 `GenerateRunner` 而不是 `generator`。

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/core.py
~~~~~
~~~~~python.old
        self.generate_runner = GenerateRunner(
            root_path,
            self.scanner,
            self.doc_manager,
            self.stub_pkg_manager,
            stub_generator,
        )
        self.init_runner = InitRunner(root_path, self.doc_manager, self.sig_manager)
~~~~~
~~~~~python.new
        self.generate_runner = GenerateRunner(
            root_path,
            self.scanner,
            self.doc_manager,
            self.stub_pkg_manager,
            stub_generator,
            transformer,
        )
        self.init_runner = InitRunner(root_path, self.doc_manager, self.sig_manager)
~~~~~

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/core.py
~~~~~
~~~~~python.old
        # Inject renderer into stub generator
        if hasattr(self.generate_runner.generator, "set_renderer"):
            self.generate_runner.generator.set_renderer(renderer)
~~~~~
~~~~~python.new
        # Inject renderer into generate runner
        self.generate_runner.set_renderer(renderer)
~~~~~

#### Acts 3: 简化 StubGenerator，移除文档生成逻辑

现在 `StubGenerator` 只需要生成代码骨架，不再需要处理文档字符串的拼接和格式化。

~~~~~act
patch_file
packages/stitcher-python-adapter/src/stitcher/adapter/python/internal/stub_generator.py
~~~~~
~~~~~python.old
from typing import List
from typing import Optional
from stitcher.spec import (
    Argument,
    ArgumentKind,
    Attribute,
    ClassDef,
    FunctionDef,
    ModuleDef,
    DocstringRendererProtocol,
)
from stitcher.common import format_docstring


class StubGenerator:
    def __init__(self, indent_spaces: int = 4):
        self._indent_str = " " * indent_spaces
        self._renderer: Optional[DocstringRendererProtocol] = None

    def set_renderer(self, renderer: DocstringRendererProtocol) -> None:
        self._renderer = renderer

    def generate(self, module: ModuleDef) -> str:
        lines = []

        # 1. Module Docstring
        doc_content = None
        if module.docstring_ir and self._renderer:
            doc_content = self._renderer.render(module.docstring_ir, context=module)
        elif module.docstring:
            doc_content = module.docstring

        if doc_content:
            formatted = format_docstring(doc_content, self._indent(0))
            lines.append(formatted)
            lines.append("")  # Empty line after docstring

        # 2. Imports (TODO: Pass these through from scanner later)
~~~~~
~~~~~python.new
from typing import List
from stitcher.spec import (
    Argument,
    ArgumentKind,
    Attribute,
    ClassDef,
    FunctionDef,
    ModuleDef,
)


class StubGenerator:
    def __init__(self, indent_spaces: int = 4):
        self._indent_str = " " * indent_spaces

    def generate(self, module: ModuleDef) -> str:
        lines = []

        # 1. Module Docstring (Ignored in skeleton generation)

        # 2. Imports (TODO: Pass these through from scanner later)
~~~~~

~~~~~act
patch_file
packages/stitcher-python-adapter/src/stitcher/adapter/python/internal/stub_generator.py
~~~~~
~~~~~python.old
        def_line = f"{indent}{prefix}def {func.name}({args_str}){ret_str}:"

        # Body
        doc_content = None
        if func.docstring_ir and self._renderer:
            doc_content = self._renderer.render(func.docstring_ir, context=func)
        elif func.docstring:
            doc_content = func.docstring

        if doc_content:
            lines.append(def_line)
            formatted = format_docstring(doc_content, self._indent(level + 1))
            lines.append(f"{self._indent(level + 1)}{formatted}")
            lines.append(f"{self._indent(level + 1)}...")
        else:
            # For functions without docstrings, use a single line format.
            lines.append(f"{def_line} ...")

        return "\n".join(lines)
~~~~~
~~~~~python.new
        def_line = f"{indent}{prefix}def {func.name}({args_str}){ret_str}:"

        # Body - Always use ellipsis for skeleton
        lines.append(f"{def_line} ...")

        return "\n".join(lines)
~~~~~

~~~~~act
patch_file
packages/stitcher-python-adapter/src/stitcher/adapter/python/internal/stub_generator.py
~~~~~
~~~~~python.old
        lines.append(f"{indent}class {cls.name}{bases_str}:")

        # Body
        has_content = False

        # Docstring
        doc_content = None
        if cls.docstring_ir and self._renderer:
            doc_content = self._renderer.render(cls.docstring_ir, context=cls)
        elif cls.docstring:
            doc_content = cls.docstring

        if doc_content:
            formatted = format_docstring(doc_content, self._indent(level + 1))
            lines.append(f"{self._indent(level + 1)}{formatted}")
            has_content = True

        # Attributes
        for attr in cls.attributes:
~~~~~
~~~~~python.new
        lines.append(f"{indent}class {cls.name}{bases_str}:")

        # Body
        has_content = False

        # Docstring (Ignored in skeleton)

        # Attributes
        for attr in cls.attributes:
~~~~~

#### Acts 4: 更新 PythonStubGenerator 适配器

移除 `PythonStubGenerator` 中的 `set_renderer` 方法，因为它不再被使用。

~~~~~act
patch_file
packages/stitcher-python-adapter/src/stitcher/adapter/python/generator.py
~~~~~
~~~~~python.old
from stitcher.spec import ModuleDef, DocstringRendererProtocol
from .internal.stub_generator import StubGenerator


class PythonStubGenerator:
    def __init__(self):
        self._delegate = StubGenerator()

    def set_renderer(self, renderer: DocstringRendererProtocol) -> None:
        self._delegate.set_renderer(renderer)

    def generate(self, module: ModuleDef) -> str:
        return self._delegate.generate(module)
~~~~~
~~~~~python.new
from stitcher.spec import ModuleDef
from .internal.stub_generator import StubGenerator


class PythonStubGenerator:
    def __init__(self):
        self._delegate = StubGenerator()

    def generate(self, module: ModuleDef) -> str:
        return self._delegate.generate(module)
~~~~~

### 下一步建议
重构完成后，重新运行所有测试，重点关注 `test_generate_docstring_styles.py`，验证新的两阶段生成策略是否完美解决了缩进和格式化问题。同时，这套架构为未来支持其他存根生成器（如 mypy/stubgen）铺平了道路。
