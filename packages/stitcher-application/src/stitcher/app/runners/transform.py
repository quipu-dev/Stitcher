from typing import List, Optional
from pathlib import Path

from stitcher.common import bus
from needle.pointer import L
from stitcher.config import load_config_from_path
from stitcher.spec import LanguageTransformerProtocol
from stitcher.app.services import DocumentManager, ScannerService


class TransformRunner:
    def __init__(
        self,
        root_path: Path,
        scanner: ScannerService,
        doc_manager: DocumentManager,
        transformer: LanguageTransformerProtocol,
    ):
        self.root_path = root_path
        self.scanner = scanner
        self.doc_manager = doc_manager
        self.transformer = transformer

    def run_strip(self, files: Optional[List[Path]] = None) -> List[Path]:
        all_modified_files: List[Path] = []
        files_to_process = []

        if files:
            files_to_process = files
        else:
            configs, _ = load_config_from_path(self.root_path)
            for config in configs:
                files_to_process.extend(self.scanner.get_files_from_config(config))
            files_to_process = sorted(list(set(files_to_process)))

        for file_path in files_to_process:
            try:
                original_content = file_path.read_text(encoding="utf-8")
                # Call strip with whitelist=None for global stripping
                stripped_content = self.transformer.strip(
                    original_content, whitelist=None
                )
                if original_content != stripped_content:
                    file_path.write_text(stripped_content, encoding="utf-8")
                    all_modified_files.append(file_path)
                    relative_path = file_path.relative_to(self.root_path)
                    bus.success(L.strip.file.success, path=relative_path)
            except Exception as e:
                bus.error(L.error.generic, error=e)

        if all_modified_files:
            bus.success(L.strip.run.complete, count=len(all_modified_files))
        return all_modified_files

    def run_inject(self) -> List[Path]:
        configs, _ = load_config_from_path(self.root_path)
        all_modified_files: List[Path] = []
        total_docs_found = 0
        for config in configs:
            unique_files = self.scanner.get_files_from_config(config)
            modules = self.scanner.scan_files(unique_files)
            for module in modules:
                docs = self.doc_manager.load_docs_for_module(module)
                if not docs:
                    continue
                total_docs_found += len(docs)
                source_path = self.root_path / module.file_path
                try:
                    original_content = source_path.read_text(encoding="utf-8")
                    injected_content = self.transformer.inject(original_content, docs)
                    if original_content != injected_content:
                        source_path.write_text(injected_content, encoding="utf-8")
                        all_modified_files.append(source_path)
                        relative_path = source_path.relative_to(self.root_path)
                        bus.success(L.inject.file.success, path=relative_path)
                except Exception as e:
                    bus.error(L.error.generic, error=e)
        if all_modified_files:
            bus.success(L.inject.run.complete, count=len(all_modified_files))
        elif total_docs_found == 0:
            bus.info(L.inject.no_docs_found)
        return all_modified_files
