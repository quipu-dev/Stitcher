__path__ = __import__("pkgutil").extend_path(__path__, __name__)

from typing import List, Optional
from pathlib import Path

from stitcher.spec import (
    ModuleDef,
    DocstringRendererProtocol,
    LanguageTransformerProtocol,
)
from stitcher.workspace import StitcherConfig
from stitcher.common.transaction import TransactionManager
from stitcher.services import (
    ScannerService,
)
from stitcher.lang.sidecar import DocumentManager
from .runners import GenerateRunner
from .services import StubPackageManager
from .generator import PythonStubGenerator


class StubgenService:
    def __init__(
        self,
        root_path: Path,
        scanner: ScannerService,
        doc_manager: DocumentManager,
        transformer: LanguageTransformerProtocol,
    ):
        # Internal Composition Root for the stubgen domain
        self._generator = PythonStubGenerator()
        self._stub_pkg_manager = StubPackageManager()
        self._runner = GenerateRunner(
            root_path,
            scanner,
            doc_manager,
            self._stub_pkg_manager,
            self._generator,
            transformer,
        )

    def set_renderer(self, renderer: DocstringRendererProtocol) -> None:
        self._runner.set_renderer(renderer)

    def generate(
        self,
        modules: List[ModuleDef],
        config: StitcherConfig,
        tm: TransactionManager,
        project_name: Optional[str] = None,
    ) -> List[Path]:
        return self._runner.run_batch(modules, config, tm, project_name)


__all__ = ["StubgenService"]
