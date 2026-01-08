import copy
from typing import Optional
from stitcher.spec import DocstringIR


class DocstringMerger:
    """
    Service responsible for merging DocstringIR objects.
    Encapsulates strategies for resolving conflicts and preserving data (like Addons).
    """

    def merge(
        self, base: Optional[DocstringIR], incoming: DocstringIR
    ) -> DocstringIR:
        """
        Merges an incoming docstring (usually from source code) into a base docstring (usually from YAML).

        Strategy:
        - The `incoming` content (summary/sections) takes precedence (Overwrite).
        - The `base` metadata (Addons) is preserved.

        Args:
            base: The existing documentation (can be None if new).
            incoming: The new documentation from source.

        Returns:
            A new DocstringIR object representing the merged state.
        """
        # If there is no base, there is nothing to preserve.
        if not base:
            return incoming

        # Create a deep copy of incoming to serve as the result foundation
        # We use incoming as the base for content because this is an "Overwrite/Update" merge.
        merged = copy.deepcopy(incoming)

        # Preserve Addons from base
        # This is the critical logic: Code changes shouldn't wipe out manual addons.
        if base.addons:
            merged.addons = copy.deepcopy(base.addons)

        # Future Phase: Smart merging of sections (e.g. keep parameter descriptions if missing in code)
        # would happen here.

        return merged