from typing import Optional

from stitcher.spec import URIGeneratorProtocol


class SidecarURIGenerator(URIGeneratorProtocol):
    @property
    def scheme(self) -> str:
        return "yaml"

    def generate_file_uri(self, workspace_rel_path: str) -> str:
        return f"{self.scheme}://{workspace_rel_path}"

    def generate_symbol_uri(self, workspace_rel_path: str, fragment: str) -> str:
        return f"{self.scheme}://{workspace_rel_path}#{fragment}"

    @staticmethod
    def parse(suri: str) -> tuple[str, Optional[str]]:
        scheme_prefix = "yaml://"
        if not suri.startswith(scheme_prefix):
            raise ValueError(f"Invalid Sidecar SURI: {suri}")

        content = suri[len(scheme_prefix) :]
        if "#" in content:
            path, fragment = content.split("#", 1)
            return path, fragment
        return content, None