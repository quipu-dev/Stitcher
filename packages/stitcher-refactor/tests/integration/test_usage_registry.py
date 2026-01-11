from stitcher.refactor.engine.graph import SemanticGraph
from stitcher.workspace import Workspace
from stitcher.test_utils import create_populated_index


def test_usage_query_via_index(tmp_path):
    """验证 SemanticGraph.find_usages 正确从 Index DB 获取引用。"""
    # 1. ARRANGE
    (tmp_path / "pyproject.toml").write_text("[project]\nname='test-proj'")
    pkg_dir = tmp_path / "mypkg"
    pkg_dir.mkdir()
    (pkg_dir / "__init__.py").write_text("", encoding="utf-8")
    (pkg_dir / "core.py").write_text("class Helper:\n    pass", encoding="utf-8")
    (pkg_dir / "app.py").write_text(
        "from mypkg.core import Helper as H\n\ndef main():\n    obj = H()",
        encoding="utf-8",
    )

    # 2. ACT
    index_store = create_populated_index(tmp_path)
    workspace = Workspace(root_path=tmp_path)
    graph = SemanticGraph(workspace=workspace, index_store=index_store)
    graph.load("mypkg")

    # 3. ASSERT
    # 我们查询 'mypkg.core.Helper'
    usages = graph.find_usages("mypkg.core.Helper")

    # 我们期望找到：
    # 1. app.py 中的导入：'Helper' as H (ReferenceRecord)
    # 2. app.py 中的使用：'H()'

    app_usages = [u for u in usages if u.file_path.name == "app.py"]
    assert len(app_usages) >= 2

    # 验证位置信息是否正确
    call_usage = next(u for u in app_usages if u.lineno == 4)
    assert call_usage.col_offset == 10  # H()
