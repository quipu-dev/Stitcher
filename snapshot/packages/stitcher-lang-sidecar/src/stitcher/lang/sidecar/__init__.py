__path__ = __import__("pkgutil").extend_path(__path__, __name__)

from .adapter import SidecarAdapter
from .indexer import SidecarIndexerAdapter
from .uri import SidecarURIGenerator
from .lock_manager import LockFileManager
from .parser import parse_doc_references, parse_signature_references
from .transform import SidecarTransformContext, SidecarTransformer
from .manager import DocumentManager
from .merger import DocstringMerger

__all__ = [
    "SidecarAdapter",
    "SidecarIndexerAdapter",
    "SidecarURIGenerator",
    "LockFileManager",
    "parse_doc_references",
    "parse_signature_references",
    "SidecarTransformContext",
    "SidecarTransformer",
    "DocumentManager",
    "DocstringMerger",
]
