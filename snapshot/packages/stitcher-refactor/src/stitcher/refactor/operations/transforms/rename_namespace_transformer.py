import libcst as cst
from libcst.metadata import PositionProvider
from typing import Optional, Dict, Tuple

from stitcher.refactor.engine.graph import ReferenceType, UsageLocation


class NamespaceRenamerTransformer(cst.CSTTransformer):
    METADATA_DEPENDENCIES = (PositionProvider,)

    def __init__(
        self,
        old_prefix: str,
        new_prefix: str,
        locations: Dict[Tuple[int, int], UsageLocation],
    ):
        self.old_prefix = old_prefix
        self.new_prefix = new_prefix
        self.locations = locations

    def _create_node_from_fqn(self, fqn: str) -> cst.BaseExpression:
        parts = fqn.split(".")
        node = cst.Name(value=parts[0])
        for part in parts[1:]:
            node = cst.Attribute(value=node, attr=cst.Name(value=part))
        return node

    def _get_import_path_fqn(self, node: cst.CSTNode) -> Optional[str]:
        pos = self.get_metadata(PositionProvider, node)
        start = (pos.start.line, pos.start.column)
        if start in self.locations:
            loc = self.locations[start]
            if loc.ref_type == ReferenceType.IMPORT_PATH:
                return loc.target_node_fqn
        return None

    def leave_Attribute(
        self, original_node: cst.Attribute, updated_node: cst.Attribute
    ) -> cst.BaseExpression:
        import_path_fqn = self._get_import_path_fqn(original_node)
        if import_path_fqn and import_path_fqn.startswith(self.old_prefix):
            suffix = import_path_fqn[len(self.old_prefix) :]
            new_fqn = self.new_prefix + suffix
            return self._create_node_from_fqn(new_fqn)
        return updated_node

    def leave_Name(
        self, original_node: cst.Name, updated_node: cst.Name
    ) -> cst.BaseExpression:
        import_path_fqn = self._get_import_path_fqn(original_node)
        if import_path_fqn and import_path_fqn.startswith(self.old_prefix):
            suffix = import_path_fqn[len(self.old_prefix) :]
            new_fqn = self.new_prefix + suffix
            return self._create_node_from_fqn(new_fqn)
        return updated_node