from textwrap import dedent
from stitcher.index.indexer import FileIndexer
from stitcher.lang.python.adapter import PythonAdapter
from stitcher.test_utils.workspace import WorkspaceFactory
from stitcher.workspace import Workspace


def test_indexer_resolves_aliases_and_references(tmp_path, store):
    """
    End-to-end test for alias resolution and reference scanning.
    Verifies that:
    1. Aliases (imports) are stored as symbols with kind='alias'.
    2. `alias_target_id` correctly points to the original symbol's SURI.
    3. Usages of aliases create correct ReferenceRecords.
    """
    # 1. Setup: A multi-file python package
    wf = WorkspaceFactory(tmp_path)
    wf.with_source("pkg/__init__.py", "")
    wf.with_source(
        "pkg/defs.py",
        dedent(
            """
            class MyClass:
                pass

            def my_func():
                pass
            """
        ),
    )
    wf.with_source(
        "pkg/main.py",
        dedent(
            """
            import pkg.defs
            from pkg.defs import MyClass
            from pkg.defs import my_func as func_alias

            # Usages
            instance = MyClass()
            pkg.defs.my_func()
            func_alias()
            """
        ),
    )
    project_root = wf.build()

    # 2. Execution: Run the full indexer pipeline
    workspace = Workspace(project_root)
    files_to_index = workspace.discover_files()

    indexer = FileIndexer(project_root, store)
    # Manual search_paths to avoid dependency on Workspace service in pure index tests
    adapter = PythonAdapter(project_root, [project_root])
    indexer.register_adapter(".py", adapter)
    indexer.index_files(files_to_index)

    # 3. Verification
    main_py_record = store.get_file_by_path("pkg/main.py")
    assert main_py_record is not None

    # 3a. Verify Alias Symbols in main.py
    symbols = store.get_symbols_by_file(main_py_record.id)
    symbols_by_name = {s.name: s for s in symbols}

    # from pkg.defs import MyClass
    alias_myclass = symbols_by_name.get("MyClass")
    assert alias_myclass is not None
    assert alias_myclass.kind == "alias"
    assert alias_myclass.alias_target_id == "py://pkg/defs.py#MyClass"

    # from pkg.defs import my_func as func_alias
    alias_funcalias = symbols_by_name.get("func_alias")
    assert alias_funcalias is not None
    assert alias_funcalias.kind == "alias"
    assert alias_funcalias.alias_target_id == "py://pkg/defs.py#my_func"

    # import pkg.defs
    alias_pkg_defs = symbols_by_name.get("pkg")
    assert alias_pkg_defs is not None
    assert alias_pkg_defs.kind == "alias"
    assert alias_pkg_defs.alias_target_id == "py://pkg/__init__.py"

    # 3b. Verify References in main.py
    references = store.get_references_by_file(main_py_record.id)
    ref_targets = {ref.target_id for ref in references}

    assert "py://pkg/defs.py#MyClass" in ref_targets
    assert "py://pkg/defs.py#my_func" in ref_targets
