from stitcher.spec import ModuleDef
from stitcher.python.analysis.cst.visitors import parse_source_code


class PythonParser:
    def parse(self, source_code: str, file_path: str = "") -> ModuleDef:
        return parse_source_code(source_code, file_path)
