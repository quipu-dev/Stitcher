from typing import Optional

from stitcher.spec.protocols import URIGeneratorProtocol


class PythonURIGenerator(URIGeneratorProtocol):
    """
    Python-specific implementation of the SURI Generator Protocol.
    This class expects workspace-relative paths and does no path calculation itself.
    """
    @property
    def scheme(self) -> str:
        return "py"

    def generate_file_uri(self, workspace_rel_path: str) -> str:
        return f"{self.scheme}://{workspace_rel_path}"

    def generate_symbol_uri(self, workspace_rel_path: str, fragment: str) -> str:
        return f"{self.scheme}://{workspace_rel_path}#{fragment}"

    @staticmethod
    def parse(suri: str) -> tuple[str, Optional[str]]:
        """
        Utility method to parse a SURI into its path and fragment components.
        Note: This is a utility and not part of the URIGeneratorProtocol.
        """
        scheme_prefix = "py://"
        if not suri.startswith(scheme_prefix):
            raise ValueError(f"Invalid Python SURI: {suri}")

        content = suri[len(scheme_prefix):]
        if "#" in content:
            path, fragment = content.split("#", 1)
            return path, fragment
        return content, None