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
        parsed = urlparse(suri)
        if parsed.scheme != "py":
            raise ValueError(f"Invalid SURI scheme: '{parsed.scheme}'")

        # The path component from urlparse includes the leading '/', which we strip.
        # It also handles URL-encoded characters, which we decode.
        path = unquote(parsed.path).lstrip("/")
        fragment = unquote(parsed.fragment)

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