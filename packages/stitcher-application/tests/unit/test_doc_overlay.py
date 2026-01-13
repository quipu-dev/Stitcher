from pathlib import Path

from stitcher.app.services import DocumentManager
from stitcher.lang.sidecar import SidecarAdapter
from stitcher.lang.python.docstring import RawSerializer, RawDocstringParser
from stitcher.spec import ModuleDef, FunctionDef, DocstringIR


def test_apply_docs_overlay(tmp_path: Path):
    # 1. Setup IR with "Source Docs"
    module = ModuleDef(
        file_path="src/main.py",
        docstring="Source Module Doc",
        functions=[FunctionDef(name="func", docstring="Source Func Doc")],
    )

    # 2. Setup External Docs using the correct SidecarAdapter
    doc_file = tmp_path / "src" / "main.stitcher.yaml"
    adapter = SidecarAdapter(root_path=tmp_path)
    serializer = RawSerializer()
    external_irs = {
        "__doc__": DocstringIR(summary="YAML Module Doc"),
        "func": DocstringIR(summary="YAML Func Doc"),
    }
    adapter.save_doc_irs(doc_file, external_irs, serializer)

    # 3. Apply
    manager = DocumentManager(root_path=tmp_path)
    # The manager needs the correct serializer strategy to parse the file.
    manager.set_strategy(RawDocstringParser(), serializer)
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
    adapter = SidecarAdapter(root_path=tmp_path)
    serializer = RawSerializer()
    # Only overriding func1
    external_irs = {"func1": DocstringIR(summary="YAML 1")}
    adapter.save_doc_irs(doc_file, external_irs, serializer)

    manager = DocumentManager(root_path=tmp_path)
    manager.set_strategy(RawDocstringParser(), serializer)
    manager.apply_docs_to_module(module)

    assert module.functions[0].docstring == "YAML 1"
    assert module.functions[1].docstring == "Source 2"
