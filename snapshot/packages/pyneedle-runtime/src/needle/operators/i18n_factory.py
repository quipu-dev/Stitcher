from pathlib import Path
from typing import Union
from needle.spec import OperatorProtocol, SemanticPointerProtocol
from .fs_operator import FileSystemOperator


class I18NFactoryOperator(OperatorProtocol):
    def __init__(self, assets_root: Union[str, Path]):
        self.assets_root = Path(assets_root)

    def __call__(
        self, lang_pointer: Union[str, SemanticPointerProtocol]
    ) -> FileSystemOperator:
        # Resolve pointer to lang code string: L.en -> "en"
        lang_code = str(lang_pointer)

        # Handle case where pointer might be complex, we only want the last part?
        # Or require passing simple pointer like L.en?
        # Let's assume the string representation is the directory name.

        target_dir = self.assets_root / "needle" / lang_code

        # We return a configured executor.
        # Note: We rely on FileSystemOperator's lazy loading to handle non-existent dirs gracefully.
        return FileSystemOperator(target_dir)
