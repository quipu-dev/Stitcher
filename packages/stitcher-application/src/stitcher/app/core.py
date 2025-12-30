from pathlib import Path
from typing import List, Optional

from stitcher.spec import (
    LanguageParserProtocol,
    LanguageTransformerProtocol,
    StubGeneratorProtocol,
    FingerprintStrategyProtocol,
)
from stitcher.app.services import (
    DocumentManager,
    SignatureManager,
    StubPackageManager,
    ScannerService,
)
from .protocols import InteractionHandler
from .runners import (
    CheckRunner,
    GenerateRunner,
    InitRunner,
    PumpRunner,
    TransformRunner,
)
from .types import PumpResult


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

        # 2. Runners (Command Handlers)
        self.check_runner = CheckRunner(
            root_path,
            self.scanner,
            parser,
            self.doc_manager,
            self.sig_manager,
            interaction_handler,
        )
        self.pump_runner = PumpRunner(
            root_path,
            self.scanner,
            parser,
            self.doc_manager,
            self.sig_manager,
            transformer,
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
            root_path, self.scanner, self.doc_manager, self.sig_manager
        )
        self.transform_runner = TransformRunner(
            root_path, self.scanner, self.doc_manager, transformer
        )

    def run_from_config(self) -> List[Path]:
        return self.generate_runner.run()

    def run_init(self) -> List[Path]:
        return self.init_runner.run()

    def run_check(self, force_relink: bool = False, reconcile: bool = False) -> bool:
        return self.check_runner.run(force_relink=force_relink, reconcile=reconcile)

    def run_pump(
        self, strip: bool = False, force: bool = False, reconcile: bool = False
    ) -> PumpResult:
        # Pass-through all options to the dedicated runner
        result = self.pump_runner.run(strip=strip, force=force, reconcile=reconcile)

        # The secondary, interactive strip confirmation logic remains here for now,
        # as it's a cross-command concern (pump -> strip).
        # A more advanced implementation might use an event bus or a post-execution hook.
        if (
            self.pump_runner.interaction_handler
            and result.redundant_files
            and not strip
        ):
            import typer  # Lazy import for CLI-specific interaction

            typer.echo("")
            typer.secho(
                f"Found {len(result.redundant_files)} file(s) with redundant docstrings in source code.",
                fg=typer.colors.YELLOW,
            )
            if typer.confirm("Do you want to strip them now?", default=True):
                self.run_strip(files=result.redundant_files)

        return result

    def run_strip(self, files: Optional[List[Path]] = None) -> List[Path]:
        return self.transform_runner.run_strip(files=files)

    def run_inject(self) -> List[Path]:
        return self.transform_runner.run_inject()
