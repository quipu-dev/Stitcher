from pathlib import Path
from typing import Optional


class SURIGenerator:
    @staticmethod
    def for_file(rel_path: str) -> str:
        # Ensure forward slashes for cross-platform consistency
        normalized_path = Path(rel_path).as_posix()
        return f"py://{normalized_path}"

    @staticmethod
    def for_symbol(rel_path: str, fragment: str) -> str:
        normalized_path = Path(rel_path).as_posix()
        return f"py://{normalized_path}#{fragment}"

    @staticmethod
    def parse(suri: str) -> tuple[str, Optional[str]]:
        if not suri.startswith("py://"):
            raise ValueError(f"Invalid Python SURI: {suri}")

        content = suri[5:]  # Strip 'py://'
        if "#" in content:
            path, fragment = content.split("#", 1)
            return path, fragment
        return content, None
