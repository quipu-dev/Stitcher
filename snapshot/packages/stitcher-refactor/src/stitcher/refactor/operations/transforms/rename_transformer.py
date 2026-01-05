import libcst as cst
from libcst.metadata import PositionProvider, CodeRange
from typing import Dict, List, Tuple, Optional, cast
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
        pos = cast(CodeRange, self.get_metadata(PositionProvider, node))
        key = (pos.start.line, pos.start.column)
        loc = self._location_index.get(key)
        if loc:
            # Check if the FQN of this specific usage location is in our rename map
            if loc.target_node_fqn in self.rename_map:
                return self.rename_map[loc.target_node_fqn]
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
            pos = cast(CodeRange, self.get_metadata(PositionProvider, original_node))
            key = (pos.start.line, pos.start.column)
            loc = self._location_index.get(key)
            if loc:
                old_fqn = loc.target_node_fqn
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

    def leave_ImportFrom(
        self, original_node: cst.ImportFrom, updated_node: cst.ImportFrom
    ) -> cst.ImportFrom:
        # If the module part of the import matches a target, we rewrite the whole
        # import to use the absolute FQN. This handles relative imports gracefully
        # by converting them to absolute ones.
        if original_node.module:
            new_fqn = self._is_target(original_node.module)
            if new_fqn:
                return updated_node.with_changes(
                    module=self._create_node_from_fqn(new_fqn),
                    relative=[],  # Force absolute import by removing dots
                )
        return updated_node
