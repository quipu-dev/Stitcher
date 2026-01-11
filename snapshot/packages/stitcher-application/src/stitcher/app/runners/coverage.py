from pathlib import Path
from typing import List
import typer

from pathlib import Path
from typing import List
import typer

from stitcher.app.services import DocumentManager
from stitcher.app.types import CoverageResult
from stitcher.spec import ModuleDef
from stitcher.index.store import IndexStore


class CoverageRunner:
    def __init__(
        self,
        root_path: Path,
        doc_manager: DocumentManager,
        index_store: IndexStore,
    ):
        self.root_path = root_path
        self.doc_manager = doc_manager
        self.index_store = index_store

    def _analyze_path_coverage(self, file_path: str) -> CoverageResult:
        # Query index for public, defined symbols
        all_symbols = self.index_store.get_symbols_by_file_path(file_path)
        public_fqns = set()

        # is_documentable check
        has_public_members = False
        module_symbol = next((s for s in all_symbols if s.kind == "module"), None)
        if module_symbol and module_symbol.docstring_content:
            has_public_members = True

        for sym in all_symbols:
            if sym.kind == "alias" or not sym.logical_path:
                continue

            parts = sym.logical_path.split(".")
            is_public = not any(p.startswith("_") and p != "__doc__" for p in parts)
            if is_public:
                public_fqns.add(sym.logical_path)
                has_public_members = True

        if has_public_members and module_symbol:
            public_fqns.add("__doc__")

        documented_fqns = set(self.doc_manager.load_docs_for_path(file_path).keys())

        if module_symbol and module_symbol.docstring_content:
            documented_fqns.add("__doc__")

        total = len(public_fqns)
        documented = len(public_fqns.intersection(documented_fqns))
        missing = total - documented
        coverage = (documented / total * 100) if total > 0 else 100.0

        return CoverageResult(
            path=file_path,
            total_symbols=total,
            documented_symbols=documented,
            missing_symbols=missing,
            coverage=coverage,
        )

    def run_batch(self, file_paths: List[str]) -> List[CoverageResult]:
        results = []
        for file_path in file_paths:
            results.append(self._analyze_path_coverage(file_path))
        return results

    def report(self, results: List[CoverageResult]):
        if not results:
            return

        paths = [r.path for r in results if r.total_symbols > 0]
        max_path_len = max(len(p) for p in paths) if paths else 0
        name_col_width = max(len("Name"), len("TOTAL"), max_path_len)

        stmts_col_width = 7
        miss_col_width = 7
        cover_col_width = 10

        total_width = (
            name_col_width + stmts_col_width + miss_col_width + cover_col_width + 3
        )

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
