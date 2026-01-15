from typing import List
from pathlib import Path

from stitcher.bus import bus
from needle.pointer import L
from stitcher.spec import (
    LanguageTransformerProtocol,
    ModuleDef,
)
from stitcher.spec.managers import DocumentManagerProtocol
from stitcher.common.transaction import TransactionManager


class TransformRunner:
    def __init__(
        self,
        root_path: Path,
        doc_manager: DocumentManagerProtocol,
        transformer: LanguageTransformerProtocol,
    ):
        self.root_path = root_path
        self.doc_manager = doc_manager
        self.transformer = transformer

    def run_strip(self, files: List[Path], tm: TransactionManager) -> List[Path]:
        all_modified_files: List[Path] = []
        for file_path in files:
            try:
                original_content = file_path.read_text(encoding="utf-8")
                stripped_content = self.transformer.strip(
                    original_content, whitelist=None
                )
                if original_content != stripped_content:
                    relative_path = file_path.relative_to(self.root_path)
                    tm.add_write(str(relative_path), stripped_content)
                    all_modified_files.append(file_path)
                    bus.success(L.strip.file.success, path=relative_path)
            except Exception as e:
                bus.error(L.error.generic, error=e)

        if all_modified_files:
            bus.success(L.strip.run.complete, count=len(all_modified_files))
        return all_modified_files

    def run_inject_batch(
        self, modules: List[ModuleDef], tm: TransactionManager
    ) -> List[Path]:
        modified_files: List[Path] = []
        total_docs_found = 0

        for module in modules:
            docs_ir = self.doc_manager.load_docs_for_module(module)
            if not docs_ir:
                continue
            total_docs_found += len(docs_ir)

            docs_str = {k: v.summary or "" for k, v in docs_ir.items()}
            source_path = self.root_path / module.file_path
            try:
                original_content = source_path.read_text(encoding="utf-8")
                injected_content = self.transformer.inject(original_content, docs_str)
                if original_content != injected_content:
                    relative_path = source_path.relative_to(self.root_path)
                    tm.add_write(str(relative_path), injected_content)
                    modified_files.append(source_path)
                    bus.success(L.inject.file.success, path=relative_path)
            except Exception as e:
                bus.error(L.error.generic, error=e)

        return modified_files
