from typing import List, Optional
from pathlib import Path

from stitcher.common import bus
from needle.pointer import L
from stitcher.workspace import StitcherConfig
from typing import Dict

from stitcher.spec import (
    ModuleDef,
    StubGeneratorProtocol,
    LanguageTransformerProtocol,
    DocstringRendererProtocol,
)
from stitcher.services import (
    DocumentManager,
    ScannerService,
)
from stitcher.common.transaction import TransactionManager
from .services import StubPackageManager


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
        self,
        config: StitcherConfig,
        stub_base_name: Optional[str],
        tm: TransactionManager,
    ):
        if not config.stub_package or not stub_base_name:
            return
        pkg_path = self.root_path / config.stub_package
        package_namespace: str = ""
        for path_str in config.scan_paths:
            path_parts = Path(path_str).parts
            if path_parts and path_parts[-1] != "src":
                # This handles cases like 'src/my_app' where 'my_app' is the namespace.
                package_namespace = path_parts[-1]
                break

        if not package_namespace:
            # Fallback for when all scan_paths end in 'src'.
            # Derives namespace from the target name (e.g., 'stitcher-cli' -> 'stitcher').
            package_namespace = stub_base_name.split("-")[0]
        stub_pkg_name = f"{stub_base_name}-stubs"
        bus.info(L.generate.stub_pkg.scaffold, name=stub_pkg_name)
        created = self.stub_pkg_manager.scaffold(
            pkg_path, stub_base_name, package_namespace, tm, self.root_path
        )
        if created:
            bus.success(L.generate.stub_pkg.success, name=stub_pkg_name)
        else:
            bus.info(L.generate.stub_pkg.exists, name=stub_pkg_name)

    def run_batch(
        self,
        modules: List[ModuleDef],
        config: StitcherConfig,
        tm: TransactionManager,
        project_name: Optional[str] = None,
    ) -> List[Path]:
        generated_files: List[Path] = []
        created_py_typed: set[Path] = set()

        if config.stub_package:
            stub_base_name = config.name if config.name != "default" else project_name
            self._scaffold_stub_package(config, stub_base_name, tm)

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
                stub_logical_path = self.stub_pkg_manager._get_pep561_logical_path(
                    logical_path
                )
                output_path = (
                    self.root_path
                    / config.stub_package
                    / "src"
                    / stub_logical_path.with_suffix(".pyi")
                )
                if stub_logical_path.parts:
                    top_level_pkg_dir = (
                        self.root_path
                        / config.stub_package
                        / "src"
                        / stub_logical_path.parts[0]
                    )
                    if top_level_pkg_dir not in created_py_typed:
                        py_typed_path = top_level_pkg_dir / "py.typed"
                        tm.add_write(str(py_typed_path.relative_to(self.root_path)), "")
                        created_py_typed.add(top_level_pkg_dir)
            elif config.stub_path:
                logical_path = self.scanner.derive_logical_path(module.file_path)
                output_path = (
                    self.root_path / config.stub_path / logical_path.with_suffix(".pyi")
                )
            else:
                output_path = self.root_path / Path(module.file_path).with_suffix(
                    ".pyi"
                )

            relative_path = output_path.relative_to(self.root_path)

            if config.stub_package:
                src_root = self.root_path / config.stub_package / "src"
                current = output_path.parent
                while current != src_root and src_root in current.parents:
                    init_path = current / "__init__.pyi"
                    tm.add_write(str(init_path.relative_to(self.root_path)), "")
                    current = current.parent

            tm.add_write(str(relative_path), final_content)
            bus.success(L.generate.file.success, path=relative_path)
            generated_files.append(output_path)
        return generated_files
