import pytest
from pathlib import Path
from stitcher.spec import ModuleDef, FunctionDef, ClassDef, Attribute
from stitcher.app.services import DocumentManager
from stitcher.io import DocumentAdapter

@pytest.fixture
def sample_module_ir():
    """
    def func():
    '''Func doc'''

class MyClass:
    '''Class doc'''
    attr: int
    '''Attr doc'''

    def method(self):
        '''Method doc'''
    """
    ...

def test_flatten_module_docs(tmp_path, sample_module_ir): ...

def test_save_docs_for_module(tmp_path, sample_module_ir): ...

class MockAdapter(DocumentAdapter):
    def __init__(self): ...

    def load(self, path: Path): ...

    def save(self, path: Path, data: dict): ...