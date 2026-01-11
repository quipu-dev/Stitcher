from stitcher.refactor.engine.graph import SemanticGraph
from stitcher.workspace import Workspace
from stitcher.test_utils import create_populated_index


def test_semantic_graph_load_package(tmp_path):
    # 1. Setup: Create a dummy python package and a pyproject.toml
    (tmp_path / "pyproject.toml").write_text("[project]\nname='test-proj'")
    pkg_dir = tmp_path / "mypkg"
    pkg_dir.mkdir()
    (pkg_dir / "__init__.py").write_text("x = 1", encoding="utf-8")

    sub_dir = pkg_dir / "utils"
    sub_dir.mkdir()
    (sub_dir / "__init__.py").write_text("", encoding="utf-8")
    (sub_dir / "math.py").write_text(
        "def add(a, b): return a + b\n\nclass Calculator:\n    def multiply(self, a, b): return a * b",
        encoding="utf-8",
    )

    # 2. Execute: Load into SemanticGraph
    index_store = create_populated_index(tmp_path)
    workspace = Workspace(root_path=tmp_path)
    graph = SemanticGraph(workspace=workspace, index_store=index_store)
    graph.load("mypkg")

    # 3. Verify: Check if modules are loaded
    module = graph.get_module("mypkg")
    assert module is not None
    assert module.path == "mypkg"

    # 4. Verify: Check flattened members
    members = graph.iter_members("mypkg")
    fqns = {node.fqn for node in members}

    expected_fqns = {
        "mypkg",
        "mypkg.x",
        "mypkg.utils",
        "mypkg.utils.math",
        "mypkg.utils.math.add",
        "mypkg.utils.math.Calculator",
        "mypkg.utils.math.Calculator.multiply",
    }

    # Check that all expected FQNs are present
    # Note: Griffe might return more stuff or handle things differently depending on version
    # but these core definitions should be there.
    for expected in expected_fqns:
        assert expected in fqns, f"Missing {expected} in graph"

    # Verify a specific node details
    add_func = next(n for n in members if n.fqn == "mypkg.utils.math.add")
    assert add_func.kind == "function"
    # Path might be absolute or relative depending on Griffe, usually absolute
    assert str(add_func.path).endswith("math.py")
