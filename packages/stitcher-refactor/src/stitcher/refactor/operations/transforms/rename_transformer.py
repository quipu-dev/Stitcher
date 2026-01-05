import libcst as cst
from libcst.metadata import PositionProvider
from typing import Dict, List, Tuple, Optional
from stitcher.refactor.engine.graph import UsageLocation


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

    def _is_target(self, node: cst.CSTNode) -> Optional[str]:
        pos = self.get_metadata(PositionProvider, node)
        key = (pos.start.line, pos.start.column)
        if key in self._location_index:
            # Assuming the rename_map contains the single {old_fqn: new_fqn}
            # relevant to this set of locations.
            if self.rename_map:
                return next(iter(self.rename_map.values()))
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
        new_fqn = self._is_target(original_node)
        if new_fqn:
            old_fqn = next(iter(self.rename_map.keys()))
            old_short_name = old_fqn.split(".")[-1]

            # Name Match Guard: Only rename if the node's text matches the old name.
            if original_node.value == old_short_name:
                new_short_name = new_fqn.split(".")[-1]
                return updated_node.with_changes(value=new_short_name)

        return updated_node

    def leave_Attribute(
        self, original_node: cst.Attribute, updated_node: cst.Attribute
    ) -> cst.BaseExpression:
        new_fqn = self._is_target(original_node)
        if new_fqn:
            from libcst import helpers

            old_fqn = next(iter(self.rename_map.keys()))
            node_textual_fqn = helpers.get_full_name_for_node(original_node)

            # Name Match Guard: Only rename if the node's full text matches the old FQN.
            if node_textual_fqn == old_fqn:
                return self._create_node_from_fqn(new_fqn)

        return updated_node
