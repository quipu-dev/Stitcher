from dataclasses import dataclass

from stitcher.analysis.semantic import SemanticGraph
from stitcher.refactor.sidecar.manager import SidecarManager
from stitcher.spec import IndexStoreProtocol, LockManagerProtocol, URIGeneratorProtocol
from stitcher.workspace import Workspace


@dataclass
class RefactorContext:
    workspace: Workspace
    graph: SemanticGraph
    sidecar_manager: SidecarManager
    index_store: IndexStoreProtocol
    lock_manager: LockManagerProtocol
    uri_generator: URIGeneratorProtocol