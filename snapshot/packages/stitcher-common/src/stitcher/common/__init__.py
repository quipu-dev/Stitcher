__path__ = __import__("pkgutil").extend_path(__path__, __name__)

import os
from pathlib import Path
from needle.nexus import OverlayOperator
from needle.operators import FileSystemOperator
from needle.runtime import _find_project_root
from .formatting import format_docstring, parse_docstring
from .messaging.bus import MessageBus
from .interfaces import DocumentAdapter
from .adapters.yaml_adapter import YamlAdapter

# --- Composition Root for Stitcher's Core Services ---

def _create_scoped_operator(scope: str):
    """
    Factory function to create the final composed operator for a given scope (e.g. language).
    This replaces the implicit logic inside the old FileSystemLoader.
    """
    
    # 1. Discover Roots
    project_root = _find_project_root()
    common_assets_root = Path(__file__).parent / "assets"

    # 2. Sub-paths for the requested scope (e.g. "needle/en")
    #    Assumption: scope is something like "en" or "needle/en".
    #    In the old system, FSLoader looked into root/needle/{domain} and root/.stitcher/needle/{domain}
    #    Let's reconstruct the pointer semantics. 
    #    Normally we pass the *base* to FS Operator, and it does key -> filename.
    #    So we need Operators pointing to `.../needle/{lang}`.
    
    #    Let's check Env Vars for language, defaulting to 'en'
    #    Strictly, this should be an I18NFactory, but for now we hardcode the pipeline for 'en' default
    #    or fetch from env to bootstrap.
    lang = os.getenv("STITCHER_LANG", "en")
    
    # 3. Create Operators
    #    Priorities: 
    #    A. User Overrides: project/.stitcher/needle/{lang}
    #    B. Default Assets: common/needle/{lang}
    
    user_override_path = project_root / ".stitcher" / "needle" / lang
    default_assets_path = common_assets_root / "needle" / lang
    
    ops = []
    
    # Only add if directory exists? FS Operator lazily handles missing files but expects root to exist?
    # FS Operator will do path joining. If root doesn't exist, file open fails -> returns empty.
    # So it is safe to just create them.
    
    ops.append(FileSystemOperator(user_override_path))
    ops.append(FileSystemOperator(default_assets_path))
    
    return OverlayOperator(ops)

# Global singleton representing the "Current Context"
# In a future refactor, this should be dynamic or request-scoped.
stitcher_operator = _create_scoped_operator("en")

# 4. Create the bus instance.
bus = MessageBus(nexus_instance=stitcher_operator)

# Note: stitcher_loader (writable) is temporarily removed until Write Operator is defined.
# stitcher_nexus is removed.

__all__ = [
    "bus",
    "stitcher_operator",
    "format_docstring",
    "parse_docstring",
    "DocumentAdapter",
    "YamlAdapter",
]
