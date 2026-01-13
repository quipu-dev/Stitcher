from pathlib import Path
from typing import List, Optional

from stitcher.lang.python.analysis.utils import path_to_logical_fqn


def path_to_fqn(path: Path, search_paths: List[Path]) -> Optional[str]:
    base_path = None
    # Sort search paths by length (depth) to find the most specific match first
    for sp in sorted(search_paths, key=lambda p: len(p.parts), reverse=True):
        try:
            # Use is_relative_to for modern Python
            if path.is_relative_to(sp):
                base_path = sp
                break
        except (ValueError, AttributeError):
            # Fallback for older Python or different path object types
            if str(path).startswith(str(sp)):
                base_path = sp
                break
            continue

    if base_path is None:
        return None

    rel_path = path.relative_to(base_path)
    return path_to_logical_fqn(rel_path.as_posix())
