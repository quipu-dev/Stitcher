__path__ = __import__("pkgutil").extend_path(__path__, __name__)

from .adapter import SidecarAdapter
from .parser import parse_doc_references, parse_signature_references
from .transform import SidecarTransformContext, SidecarTransformer
from .signature_manager import SignatureManager

__all__ = [
    "SidecarAdapter",
    "parse_doc_references",
    "parse_signature_references",
    "SidecarTransformContext",
    "SidecarTransformer",
    "SignatureManager",
]
