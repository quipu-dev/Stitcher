import json
from stitcher.analysis.semantic import SemanticGraph
from stitcher.refactor.engine.context import RefactorContext
from stitcher.common.transaction import TransactionManager, WriteFileOp
from stitcher.refactor.operations.rename_symbol import RenameSymbolOperation
from stitcher.refactor.sidecar.manager import SidecarManager
from stitcher.workspace import Workspace
from stitcher.test_utils import WorkspaceFactory, create_populated_index


def test_rename_symbol_updates_suri_fragment_in_signatures(tmp_path):
    """
    验证 RenameSymbolOperation 能够正确更新 Signature 文件中的 SURI 键。
    场景: 重命名类 MyClass -> YourClass
    预期: 签名文件中的键从 py://...#MyClass 变为 py://...#YourClass
    """
    # 1. ARRANGE
    factory = WorkspaceFactory(tmp_path)

    # 构造 SURI (注意: 路径相对于项目根目录)
    rel_py_path = "src/mypkg/core.py"
    old_suri = f"py://{rel_py_path}#MyClass"
    new_suri = f"py://{rel_py_path}#YourClass"

    project_root = (
        factory.with_pyproject(".")
        .with_source("src/mypkg/__init__.py", "")
        .with_source(rel_py_path, "class MyClass:\n    pass\n")
        .build()
    )

    # Manually create lock file
    lock_file = project_root / "stitcher.lock"
    lock_data = {
        "version": "1.0",
        "fingerprints": {old_suri: {"baseline_code_structure_hash": "original_hash"}},
    }
    lock_file.write_text(json.dumps(lock_data))

    # 2. ACT
    index_store = create_populated_index(project_root)
    workspace = Workspace(root_path=project_root)
    graph = SemanticGraph(workspace=workspace, index_store=index_store)
    graph.load("mypkg")

    sidecar_manager = SidecarManager(root_path=project_root)
    ctx = RefactorContext(
        workspace=workspace,
        graph=graph,
        sidecar_manager=sidecar_manager,
        index_store=index_store,
    )

    # 执行重命名
    from stitcher.refactor.migration import MigrationSpec
    from stitcher.refactor.engine.planner import Planner

    op = RenameSymbolOperation(
        old_fqn="mypkg.core.MyClass", new_fqn="mypkg.core.YourClass"
    )
    spec = MigrationSpec().add(op)
    planner = Planner()
    file_ops = planner.plan(spec, ctx)

    # 提交更改
    tm = TransactionManager(project_root)
    for fop in file_ops:
        if isinstance(fop, WriteFileOp):
            tm.add_write(fop.path, fop.content)
    tm.commit()

    # 3. ASSERT
    from stitcher.test_utils import get_stored_hashes

    updated_data = get_stored_hashes(project_root, rel_py_path)

    # 验证旧 SURI 已消失
    assert old_suri not in updated_data, f"旧 SURI Key 未被移除: {old_suri}"

    # 验证新 SURI 存在
    assert new_suri in updated_data, f"新 SURI Key 未生成: {new_suri}"

    # 验证数据完整性 (Hash 值应保留)
    assert updated_data[new_suri]["baseline_code_structure_hash"] == "original_hash"


def test_rename_nested_method_updates_suri_fragment(tmp_path):
    """
    验证嵌套符号（方法）重命名时的 SURI 更新。
    场景: 重命名 MyClass.old_method -> MyClass.new_method
    """
    # 1. ARRANGE
    factory = WorkspaceFactory(tmp_path)
    rel_py_path = "src/mypkg/logic.py"

    # SURI for methods usually looks like #Class.method
    old_suri = f"py://{rel_py_path}#MyClass.old_method"
    new_suri = f"py://{rel_py_path}#MyClass.new_method"

    project_root = (
        factory.with_pyproject(".")
        .with_source(
            rel_py_path,
            """
class MyClass:
    def old_method(self):
        pass
""",
        )
        .build()
    )

    # Manually create lock file
    lock_file = project_root / "stitcher.lock"
    lock_data = {"version": "1.0", "fingerprints": {old_suri: {"hash": "123"}}}
    lock_file.write_text(json.dumps(lock_data))

    # 2. ACT
    index_store = create_populated_index(project_root)
    workspace = Workspace(root_path=project_root)
    graph = SemanticGraph(workspace=workspace, index_store=index_store)
    graph.load("mypkg")

    sidecar_manager = SidecarManager(root_path=project_root)
    ctx = RefactorContext(
        workspace=workspace,
        graph=graph,
        sidecar_manager=sidecar_manager,
        index_store=index_store,
    )

    from stitcher.refactor.migration import MigrationSpec
    from stitcher.refactor.engine.planner import Planner

    op = RenameSymbolOperation(
        old_fqn="mypkg.logic.MyClass.old_method",
        new_fqn="mypkg.logic.MyClass.new_method",
    )
    spec = MigrationSpec().add(op)
    planner = Planner()
    file_ops = planner.plan(spec, ctx)

    tm = TransactionManager(project_root)
    for fop in file_ops:
        if isinstance(fop, WriteFileOp):
            tm.add_write(fop.path, fop.content)
    tm.commit()

    # 3. ASSERT
    from stitcher.test_utils import get_stored_hashes

    updated_data = get_stored_hashes(project_root, rel_py_path)
    assert old_suri not in updated_data
    assert new_suri in updated_data
    assert updated_data[new_suri]["hash"] == "123"
