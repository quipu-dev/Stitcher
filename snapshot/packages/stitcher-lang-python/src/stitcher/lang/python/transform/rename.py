import libcst as cst
from libcst.metadata import PositionProvider, CodeRange
from typing import Dict, List, Tuple, Optional, cast
from stitcher.lang.python.analysis.models import UsageLocation, ReferenceType


class SymbolRenamerTransformer(cst.CSTTransformer):
    METADATA_DEPENDENCIES = (PositionProvider,)

    def __init__(
        self, rename_map: Dict[str, str], target_locations: List[UsageLocation]
    ):
        self.rename_map = rename_map
        self._location_index = self._build_location_index(target_locations)

    def _build_location_index(
        self, locations: List[UsageLocation]
    ) -> Dict[Tuple[int, int], UsageLocation]:
        index = {}
        for loc in locations:
            key = (loc.lineno, loc.col_offset)
            index[key] = loc
        return index

    def _get_rename_for_node(self, node: cst.CSTNode) -> Optional[Tuple[str, str]]:
        pos = cast(CodeRange, self.get_metadata(PositionProvider, node))
        key = (pos.start.line, pos.start.column)
        loc = self._location_index.get(key)
        if loc:
            old_fqn = loc.target_node_fqn
            if old_fqn in self.rename_map:
                new_fqn = self.rename_map[old_fqn]
                return (old_fqn, new_fqn)
        return None

    def _create_node_from_fqn(self, fqn: str) -> cst.BaseExpression:
        parts = fqn.split(".")
        node = cst.Name(value=parts[0])
        for part in parts[1:]:
            node = cst.Attribute(value=node, attr=cst.Name(value=part))
        return node

    def leave_Name(
        self, original_node: cst.Name, updated_node: cst.Name
    ) -> cst.BaseExpression:
        rename_info = self._get_rename_for_node(original_node)
        if rename_info:
            old_fqn, new_fqn = rename_info
            old_short_name = old_fqn.split(".")[-1]

            # Name Match Guard: Only rename if the node's text matches the old name.
            if original_node.value == old_short_name:
                new_short_name = new_fqn.split(".")[-1]
                return updated_node.with_changes(value=new_short_name)

        return updated_node

    def leave_Attribute(
        self, original_node: cst.Attribute, updated_node: cst.Attribute
    ) -> cst.BaseExpression:
        rename_info = self._get_rename_for_node(original_node)
        if rename_info:
            old_fqn, new_fqn = rename_info
            from libcst import helpers

            node_textual_fqn = helpers.get_full_name_for_node(original_node)

            # Name Match Guard: Only rename if the node's full text matches the old FQN.
            if node_textual_fqn == old_fqn:
                return self._create_node_from_fqn(new_fqn)

        return updated_node

    def leave_ImportFrom(
        self, original_node: cst.ImportFrom, updated_node: cst.ImportFrom
    ) -> cst.ImportFrom:
        # If the module part of the import matches a target, we rewrite the whole
        # import to use the absolute FQN. This handles relative imports gracefully
        # by converting them to absolute ones.
        if original_node.module:
            rename_info = self._get_rename_for_node(original_node.module)
            if rename_info:
                _old_fqn, new_fqn = rename_info
                return updated_node.with_changes(
                    module=self._create_node_from_fqn(new_fqn),
                    relative=[],  # Force absolute import by removing dots
                )
        return updated_node


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
        pos = cast(CodeRange, self.get_metadata(PositionProvider, node))
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
