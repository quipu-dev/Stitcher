from pathlib import Path
from typing import List
import typer

from stitcher.config import load_config_from_path
from stitcher.app.services import DocumentManager, ScannerService
from stitcher.app.types import CoverageResult


class CoverageRunner:
    def __init__(
        self,
        root_path: Path,
        scanner: ScannerService,
        doc_manager: DocumentManager,
    ):
        self.root_path = root_path
        self.scanner = scanner
        self.doc_manager = doc_manager

    def _analyze_module_coverage(self, module) -> CoverageResult:
        public_fqns = module.get_public_documentable_fqns()
        documented_fqns = set(self.doc_manager.load_docs_for_module(module).keys())

        # The module docstring is checked via 'is_documentable' but the key is '__doc__'
        if module.docstring and "__doc__" in public_fqns:
            documented_fqns.add("__doc__")

        total = len(public_fqns)
        documented = len(public_fqns.intersection(documented_fqns))
        missing = total - documented
        coverage = (documented / total * 100) if total > 0 else 100.0

        return CoverageResult(
            path=module.file_path,
            total_symbols=total,
            documented_symbols=documented,
            missing_symbols=missing,
            coverage=coverage,
        )

    def _render_report(self, results: List[CoverageResult]):
        if not results:
            return

        # Dynamically determine column width
        paths = [r.path for r in results if r.total_symbols > 0]
        max_path_len = max(len(p) for p in paths) if paths else 0
        name_col_width = max(len("Name"), len("TOTAL"), max_path_len)

        # Define other column widths
        stmts_col_width = 7
        miss_col_width = 7
        cover_col_width = 10

        # Calculate total width for the horizontal rule
        total_width = (
            name_col_width + stmts_col_width + miss_col_width + cover_col_width + 3
        )  # For spaces

        typer.echo("\n" + ("-" * total_width))
        typer.secho(
            f"{'Name':<{name_col_width}} {'Stmts':>{stmts_col_width}} {'Miss':>{miss_col_width}} {'Cover':>{cover_col_width}}",
            bold=True,
        )
        typer.echo("-" * total_width)

        total_stmts = 0
        total_miss = 0

        for res in sorted(results, key=lambda r: r.path):
            if res.total_symbols == 0:
                continue

            total_stmts += res.total_symbols
            total_miss += res.missing_symbols

            cover_str = f"{res.coverage:.1f}%"

            color = typer.colors.GREEN
            if res.coverage < 50:
                color = typer.colors.RED
            elif res.coverage < 90:
                color = typer.colors.YELLOW

            typer.secho(
                (
                    f"{res.path:<{name_col_width}} "
                    f"{res.total_symbols:>{stmts_col_width}} "
                    f"{res.missing_symbols:>{miss_col_width}} "
                    f"{cover_str:>{cover_col_width}}"
                ),
                fg=color,
            )

        typer.echo("-" * total_width)

        total_coverage = (
            ((total_stmts - total_miss) / total_stmts * 100)
            if total_stmts > 0
            else 100.0
        )
        cover_str = f"{total_coverage:.1f}%"
        typer.secho(
            (
                f"{'TOTAL':<{name_col_width}} "
                f"{total_stmts:>{stmts_col_width}} "
                f"{total_miss:>{miss_col_width}} "
                f"{cover_str:>{cover_col_width}}"
            ),
            bold=True,
        )
        typer.echo("")

    def run(self) -> bool:
        configs, _ = load_config_from_path(self.root_path)
        all_results: List[CoverageResult] = []

        for config in configs:
            unique_files = self.scanner.get_files_from_config(config)
            modules = self.scanner.scan_files(unique_files)
            for module in modules:
                result = self._analyze_module_coverage(module)
                all_results.append(result)

        self._render_report(all_results)
        return True
