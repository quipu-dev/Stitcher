import pytest
from stitcher.lang.python.uri import PythonURIGenerator
from ruamel.yaml import YAML
from stitcher.spec import ModuleDef, FunctionDef, ClassDef, Attribute
from stitcher.lang.sidecar import DocumentManager


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
    manager = DocumentManager(root_path=tmp_path, uri_generator=PythonURIGenerator())
    docs = manager.flatten_module_docs(sample_module_ir)

    assert docs["__doc__"].summary == "Module doc"
    assert docs["func"].summary == "Func doc"
    assert docs["MyClass"].summary == "Class doc"
    assert docs["MyClass.method"].summary == "Method doc"
    assert docs["MyClass.attr"].summary == "Attr doc"


def test_save_docs_for_module(tmp_path, sample_module_ir):
    manager = DocumentManager(root_path=tmp_path, uri_generator=PythonURIGenerator())

    output_path = manager.save_docs_for_module(sample_module_ir)

    expected_path = tmp_path / "src/main.stitcher.yaml"
    assert output_path == expected_path
    assert expected_path.exists()

    # Load the content with a YAML parser to verify data correctness
    yaml = YAML()
    content = yaml.load(expected_path.read_text("utf-8"))
    assert content["MyClass.method"] == "Method doc"
    assert content["__doc__"] == "Module doc"
