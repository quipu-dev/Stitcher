import difflib
from typing import List


class Differ:
    """
    Service responsible for generating human-readable differences between text or objects.
    """

    def generate_text_diff(
        self, a: str, b: str, label_a: str = "old", label_b: str = "new"
    ) -> str:
        """
        Generates a unified diff string between two text blocks.
        """
        return "\n".join(
            difflib.unified_diff(
                a.splitlines(),
                b.splitlines(),
                fromfile=label_a,
                tofile=label_b,
                lineterm="",
            )
        )