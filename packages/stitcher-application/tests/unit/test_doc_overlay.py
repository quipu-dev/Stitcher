from pathlib import Path
from stitcher.spec import ModuleDef, FunctionDef
from stitcher.app.services import DocumentManager
from stitcher.io import YamlAdapter


def test_apply_docs_overlay(tmp_path: Path):
    # 1. Setup IR with "Source Docs"
    module = ModuleDef(
        file_path="src/main.py",
        docstring="Source Module Doc",
        functions=[FunctionDef(name="func", docstring="Source Func Doc")],
    )

    # 2. Setup External Docs (Mocking file system via YamlAdapter)
    # create src/main.stitcher.yaml
    doc_file = tmp_path / "src" / "main.stitcher.yaml"
    doc_file.parent.mkdir(parents=True)

    adapter = YamlAdapter()
    external_docs = {"__doc__": "YAML Module Doc", "func": "YAML Func Doc"}
    adapter.save(doc_file, external_docs)

    # 3. Apply
    manager = DocumentManager(root_path=tmp_path)
    manager.apply_docs_to_module(module)

    # 4. Assert IR is updated
    assert module.docstring == "YAML Module Doc"
    assert module.functions[0].docstring == "YAML Func Doc"


def test_apply_docs_partial_overlay(tmp_path: Path):
    module = ModuleDef(
        file_path="src/main.py",
        functions=[
            FunctionDef(name="func1", docstring="Source 1"),
            FunctionDef(name="func2", docstring="Source 2"),
        ],
    )

    doc_file = tmp_path / "src" / "main.stitcher.yaml"
    doc_file.parent.mkdir(parents=True)

    adapter = YamlAdapter()
    # Only overriding func1
    adapter.save(doc_file, {"func1": "YAML 1"})

    manager = DocumentManager(root_path=tmp_path)
    manager.apply_docs_to_module(module)

    assert module.functions[0].docstring == "YAML 1"
    assert module.functions[1].docstring == "Source 2"
