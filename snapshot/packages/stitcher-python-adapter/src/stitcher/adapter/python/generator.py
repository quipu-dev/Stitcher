from stitcher.spec import ModuleDef
from .internal.stub_generator import StubGenerator


class PythonStubGenerator:
    def __init__(self):
        self._delegate = StubGenerator()

    def generate(self, module: ModuleDef) -> str:
        return self._delegate.generate(module)
