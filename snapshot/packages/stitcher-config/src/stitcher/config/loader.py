from dataclasses import dataclass
import dataclasses
from pathlib import Path
from typing import List

@dataclass
class StitcherConfig:
    scan_paths: List[str] = dataclasses.field(default_factory=list)

def load_config_from_path(search_path: Path) -> StitcherConfig:
    """Finds and loads stitcher config from pyproject.toml."""
    # TODO: Implement file finding and toml parsing
    return StitcherConfig()
