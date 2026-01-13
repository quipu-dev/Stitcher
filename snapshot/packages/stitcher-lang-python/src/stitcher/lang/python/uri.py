from pathlib import Path
from urllib.parse import urlparse, unquote


class SURIGenerator:
    """
    A stateless utility for creating and parsing Stitcher Uniform Resource Identifiers (SURIs).

    SURIs follow the format: `py://<workspace_relative_path>#<fragment>`
    - `workspace_relative_path`: The POSIX-style path of the file relative to the workspace root.
    - `fragment`: The symbol's logical path within the file (e.g., `MyClass.my_method`).
    """

    @staticmethod
    def for_symbol(workspace_relative_path: str, fragment: str) -> str:
        """Creates a SURI for a specific symbol within a file."""
        return f"py://{workspace_relative_path}#{fragment}"

    @staticmethod
    def for_file(workspace_relative_path: str) -> str:
        """Creates a SURI for a file itself, without a symbol fragment."""
        return f"py://{workspace_relative_path}"

    @staticmethod
    def parse(suri: str) -> tuple[str, str]:
        """
        Parses a SURI into its path and fragment components.

        Returns:
            A tuple of (workspace_relative_path, fragment).
            The fragment will be an empty string if not present.
        """
        if not suri.startswith("py://"):
            raise ValueError(f"Invalid SURI scheme: {suri}")

        # We manually parse because urllib.parse treats the first path segment
        # after 'py://' as the netloc (host), causing it to be lost from .path.
        # e.g. py://src/main.py -> netloc='src', path='/main.py'.
        # By treating it as a plain string, we preserve the full relative path.

        body = suri[5:]  # Strip 'py://'

        if "#" in body:
            path, fragment = body.split("#", 1)
        else:
            path = body
            fragment = ""

        # Decode percent-encoding if necessary (standard URI behavior)
        path = unquote(path)
        fragment = unquote(fragment)

        # Ensure no leading slashes remain (SURIs are relative)
        path = path.lstrip("/")

        return path, fragment

    @staticmethod
    def from_path(
        root_path: Path, absolute_path: Path, fragment: str | None = None
    ) -> str:
        """
        [DEPRECATED] Creates a SURI from absolute paths.
        Prefer creating workspace-relative paths upstream and using `for_symbol`.
        """
        rel_path = absolute_path.relative_to(root_path).as_posix()
        if fragment:
            return SURIGenerator.for_symbol(rel_path, fragment)
        return SURIGenerator.for_file(rel_path)
