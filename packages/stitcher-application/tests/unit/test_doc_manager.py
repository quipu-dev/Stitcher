import pytest
from pathlib import Path
from stitcher.spec import ModuleDef, FunctionDef, ClassDef, Attribute
from stitcher.app.services import DocumentManager
from stitcher.io import DocumentAdapter


class MockAdapter(DocumentAdapter):
    def __init__(self):
        self.saved_data = {}
        self.saved_path = None

    def load(self, path: Path):
        return {}

    def save(self, path: Path, data: dict):
        self.saved_path = path
        self.saved_data = data


@pytest.fixture
def sample_module_ir():
    return ModuleDef(
        file_path="src/main.py",
        docstring="Module doc",
        functions=[FunctionDef(name="func", docstring="Func doc")],
        classes=[
            ClassDef(
                name="MyClass",
                docstring="Class doc",
                attributes=[Attribute(name="attr", docstring="Attr doc")],
                methods=[FunctionDef(name="method", docstring="Method doc")],
            )
        ],
    )


def test_flatten_module_docs(tmp_path, sample_module_ir):
    manager = DocumentManager(root_path=tmp_path)
    docs = manager.flatten_module_docs(sample_module_ir)

    assert docs["__doc__"] == "Module doc"
    assert docs["func"] == "Func doc"
    assert docs["MyClass"] == "Class doc"
    assert docs["MyClass.method"] == "Method doc"
    assert docs["MyClass.attr"] == "Attr doc"


def test_save_docs_for_module(tmp_path, sample_module_ir):
    mock_adapter = MockAdapter()
    manager = DocumentManager(root_path=tmp_path, adapter=mock_adapter)

    output_path = manager.save_docs_for_module(sample_module_ir)

    expected_path = tmp_path / "src/main.stitcher.yaml"
    assert output_path == expected_path
    assert mock_adapter.saved_path == expected_path
    assert mock_adapter.saved_data["MyClass.method"] == "Method doc"
