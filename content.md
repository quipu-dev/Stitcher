You are absolutely right. The integration tests were insufficient to pinpoint the exact failure point within the refactoring engine. Your request to create more fine-grained unit tests is the correct engineering approach. Blindly patching without understanding the root cause violates the HFEA protocol.

After a deeper, more rigorous analysis guided by the principles of the **Assumption-Driven Analysis Protocol (ADAP)**, I have identified a critical, systemic flaw in the `Planner`'s architecture.

**Detection of "Certainty Missing" Violation (ADAP v1.0)**

*   **Triggering Assumption (Contract Assumption):** The `Planner` was implicitly assuming that multiple `RenameSymbolOperation`s targeting the same file could be processed independently and their resulting `WriteFileOp`s would magically compose. This is false. Each operation was reading the *original* file content, leading to a classic **"Lost Edit" problem**, where the last write operation would overwrite all previous ones.

**The "Lost Edit" Bug: A Deeper Analysis**

The previous fix was insufficient because the problem isn't in the `SymbolRenamerTransformer`'s ability to rename a symbol, but in the `Planner`'s orchestration of multiple, concurrent modifications to the same file.

Here is the failure scenario that our integration tests couldn't isolate:
1.  **Operation 1:** `Rename("A", "B")` in `file.py`. The planner reads `file.py`, produces `content_with_B`, and queues `WriteFileOp("file.py", content_with_B)`.
2.  **Operation 2:** `Rename("X", "Y")` in the *same* `file.py`. The planner reads the *original* `file.py` again (which still contains "A" and "X"), produces `content_with_Y`, and queues `WriteFileOp("file.py", content_with_Y)`.
3.  **Execution:** The `TransactionManager` executes the first `WriteFileOp`, writing `content_with_B`. Immediately after, it executes the second `WriteFileOp`, completely overwriting the file with `content_with_Y`. The rename of "A" to "B" is lost.

This explains why `test_refactor_apply_e2e` fails: it involves renaming a class (`Old` -> `New`) and updating an import (`from mypkg.core import Old` -> `... New`), which are treated as separate rename intents that conflict.

**ADAP v1.0 Response Protocol: Refusing Tactical Fix & Proposing Strategic Solution**

According to the ADAP v1.0 protocol, any attempt to patch this without addressing the architectural flaw is prohibited.

Therefore, I propose to change the current task's objective from "Fix Failing Tests" to **"Re-architect the Refactoring Planner to be Transaction-Aware"**.

I will generate a plan to:
1.  **Create new, highly-focused tests** that specifically and unequivocally prove the existence of the "Lost Edit" bug and other related concurrency issues. This provides the safety net and diagnostic power we currently lack.
2.  **Rewrite the `Planner`** to use a new, robust strategy: it will group all transformations *per file*, chain them together in-memory using their CST representations, and only then generate a *single*, final `WriteFileOp` for each modified file.

This new architecture eliminates the possibility of lost edits and provides a solid foundation for more complex refactorings.

## [WIP] test: Add granular tests to diagnose and prove refactor engine flaws

### 错误分析

如上所述，`Planner` 的核心设计无法处理对同一文件的多个并发修改意图，导致 "Lost Edit" bug。现有的集成测试不足以隔离和证明这个问题。

### 用户需求

创建新的单元测试和专门的集成测试，以暴露 `Planner` 和 `TransactionManager` 中的并发修改和路径重整问题，为重构引擎的修复提供确定性的依据。

### 评论

这是解决根本问题的正确路径。通过编写失败的测试，我们遵循了“回归驱动开发”原则，并为后续的架构重构建立了明确的目标和验收标准。

### 目标

1.  **创建 `test_fail_concurrent_move_and_rename.py`**: 一个“冒烟测试”，它将精确地复现“Lost Edit” bug，即在一个事务中同时移动文件并重命名其内部的多个符号，并断言所有更改都已应用。这个测试在当前的架构下**必须失败**。
2.  **创建 `test_debug_rename_failure.py`**: 一个高保真度的诊断测试，使用与生产代码完全相同的 `bus.py` 内容和相关的 `stitcher.yaml` 和签名文件，来验证端到端的重命名和边车文件更新。
3.  **创建 `test_transaction_aggregator.py` 和 `test_planner_v2.py` (后续计划)**: 为新的、经过重构的 Planner V2 编写单元测试。
4.  **创建 `test_rename_transformer_advanced.py`**: 确保CST转换器可以处理更复杂的场景，例如通过属性访问 (`pkg.Class`) 或别名 (`import Class as C`) 进行的符号使用。

### 基本原理

通过“分而治之”的策略，我们首先创建能够稳定复现错误的最小化测试用例。这些测试不仅是诊断工具，更是我们新架构的验收标准。一旦这些测试就位，我们就可以在下一个计划中安全地、有信心地重构 `Planner`，直到所有新旧测试都通过为止。

### 标签

#intent/tooling #flow/ready #priority/critical #comp/tests #comp/engine #scope/dx #ai/brainstorm #task/domain/testing #task/object/refactor-engine #task/action/test-creation #task/state/continue

---

### Script

#### Acts 1: 创建新的单元测试和诊断集成测试

我将创建一系列新的测试文件，以精确地定位和证明当前重构引擎中的核心缺陷。

首先，在 `packages/stitcher-refactor/tests/unit/engine/` 目录下创建 `test_transaction_rebase.py` 来测试事务管理器中的路径重整逻辑。

~~~~~act
write_file
packages/stitcher-refactor/tests/unit/engine/test_transaction_rebase.py
~~~~~
~~~~~python
from pathlib import Path
from stitcher.common.transaction import (
    TransactionManager,
    WriteFileOp,
    MoveFileOp,
    DeleteFileOp,
)


def test_rebase_write_after_move():
    """
    Scenario:
    1. Move A -> B
    2. Write A (content updated)

    Expected:
    1. Move A -> B
    2. Write B (content updated)
    """
    tm = TransactionManager(Path("/"))
    # The internal ops list that will be processed
    ops = [
        MoveFileOp(Path("A"), Path("B")),
        WriteFileOp(Path("A"), "new content"),
    ]

    rebased = tm._rebase_ops(ops)

    assert len(rebased) == 2
    assert isinstance(rebased[0], MoveFileOp)
    assert rebased[0].path == Path("A")
    assert rebased[0].dest == Path("B")

    assert isinstance(rebased[1], WriteFileOp)
    assert rebased[1].path == Path("B")  # Rebased!
    assert rebased[1].content == "new content"


def test_rebase_chain_moves():
    """
    Scenario:
    1. Move A -> B
    2. Move B -> C
    3. Write A

    Expected:
    1. Move A -> B
    2. Move B -> C
    3. Write C
    """
    ops = [
        MoveFileOp(Path("A"), Path("B")),
        MoveFileOp(Path("B"), Path("C")),
        WriteFileOp(Path("A"), "final content"),
    ]
    tm = TransactionManager(Path("/"))
    rebased = tm._rebase_ops(ops)

    assert len(rebased) == 3
    assert isinstance(rebased[2], WriteFileOp)
    assert rebased[2].path == Path("C")


def test_rebase_no_effect_if_write_first():
    """
    Scenario:
    1. Write A
    2. Move A -> B

    Expected: No change in paths (Write A happens before it moves)
    """
    ops = [
        WriteFileOp(Path("A"), "content"),
        MoveFileOp(Path("A"), Path("B")),
    ]
    tm = TransactionManager(Path("/"))
    rebased = tm._rebase_ops(ops)

    assert rebased[0].path == Path("A")
    assert rebased[1].path == Path("A")
    # Cast to access subtype attribute
    assert isinstance(rebased[1], MoveFileOp)
    assert rebased[1].dest == Path("B")


def test_rebase_delete_after_move():
    """
    Scenario:
    1. Move A -> B
    2. Delete A

    Expected:
    1. Move A -> B
    2. Delete B
    """
    ops = [
        MoveFileOp(Path("A"), Path("B")),
        DeleteFileOp(Path("A")),
    ]
    tm = TransactionManager(Path("/"))
    rebased = tm._rebase_ops(ops)

    assert rebased[1].path == Path("B")
~~~~~

其次，创建 `packages/stitcher-refactor/tests/integration/test_fail_concurrent_move_and_rename.py` 来暴露“Lost Edit”问题。

~~~~~act
write_file
packages/stitcher-refactor/tests/integration/test_fail_concurrent_move_and_rename.py
~~~~~
~~~~~python
from stitcher.refactor.engine.graph import SemanticGraph
from stitcher.refactor.engine.context import RefactorContext
from stitcher.common.transaction import (
    TransactionManager,
    MoveFileOp,
    WriteFileOp,
    DeleteFileOp,
)
from stitcher.refactor.operations.move_file import MoveFileOperation
from stitcher.refactor.operations.rename_symbol import RenameSymbolOperation
from stitcher.refactor.sidecar.manager import SidecarManager
from stitcher.workspace import Workspace
from stitcher.test_utils import WorkspaceFactory, create_populated_index


def test_smoking_gun_concurrent_modifications_lost_edit(tmp_path):
    """
    THE SMOKING GUN TEST

    Scenario:
    We have a file 'mypkg/core.py' containing TWO symbols.
    We want to perform a transaction that:
    1. Moves the file.
    2. Renames Symbol A.
    3. Renames Symbol B.

    Old Architecture Failure Mode (The "Lost Edit"):
    1. MoveOp generates intents.
    2. RenameOp(A) generates intents.
    3. RenameOp(B) generates intents.
    4. Planner processes all RenameIntents:
       - Renamer reads 'core.py', renames A, plans Write(core.py, content_A_modified).
       - Renamer reads 'core.py' (original), renames B, plans Write(core.py, content_B_modified).
    5. Planner processes MoveIntents, plans Move(core.py -> utils.py).
    6. TransactionManager rebases paths, resulting in two conflicting writes to 'utils.py'.
       The second write overwrites the first.

    Result: The file ends up with only ONE of the renames applied.
    """
    # 1. ARRANGE
    factory = WorkspaceFactory(tmp_path)
    project_root = (
        factory.with_pyproject(".")
        .with_source("mypkg/__init__.py", "")
        .with_source(
            "mypkg/core.py",
            """
class OldClass:
    pass

def old_func():
    pass
            """,
        )
        .build()
    )

    src_path = project_root / "mypkg/core.py"
    dest_path = project_root / "mypkg/utils.py"

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

    # Three operations touching the same file
    move_op = MoveFileOperation(src_path, dest_path)
    rename_class_op = RenameSymbolOperation(
        "mypkg.core.OldClass", "mypkg.utils.NewClass"
    )
    rename_func_op = RenameSymbolOperation(
        "mypkg.core.old_func", "mypkg.utils.new_func"
    )

    from stitcher.refactor.migration import MigrationSpec
    from stitcher.refactor.engine.planner import Planner

    spec = MigrationSpec()
    spec.add(move_op)
    spec.add(rename_class_op)
    spec.add(rename_func_op)

    planner = Planner()
    all_ops = planner.plan(spec, ctx)

    tm = TransactionManager(project_root)
    for fop in all_ops:
        if isinstance(fop, MoveFileOp):
            tm.add_move(fop.path, fop.dest)
        elif isinstance(fop, WriteFileOp):
            tm.add_write(fop.path, fop.content)
        elif isinstance(fop, DeleteFileOp):
            tm.add_delete_file(fop.path)

    tm.commit()

    # 3. ASSERT
    assert dest_path.exists(), "Destination file missing!"

    content = dest_path.read_text()

    has_new_class = "class NewClass" in content
    has_new_func = "def new_func" in content

    # Debug output
    if not (has_new_class and has_new_func):
        print("\\n--- FAILURE DIAGNOSTIC ---")
        print(f"Content of {dest_path}:")
        print(content)
        print("--------------------------")

    assert has_new_class, "Lost Edit: Class rename was overwritten!"
    assert has_new_func, "Lost Edit: Function rename was overwritten!"
~~~~~

最后，创建 `packages/stitcher-refactor/tests/integration/test_rename_transformer_advanced.py` 来验证CST转换器的能力。

~~~~~act
write_file
packages/stitcher-refactor/tests/integration/test_rename_transformer_advanced.py
~~~~~
~~~~~python
from stitcher.refactor.engine.graph import SemanticGraph
from stitcher.refactor.engine.context import RefactorContext
from stitcher.common.transaction import WriteFileOp
from stitcher.refactor.operations.rename_symbol import RenameSymbolOperation
from stitcher.refactor.sidecar.manager import SidecarManager
from stitcher.workspace import Workspace
from stitcher.test_utils import WorkspaceFactory, create_populated_index


def test_rename_symbol_via_attribute_access(tmp_path):
    # 1. Setup
    project_root = (
        WorkspaceFactory(tmp_path)
        .with_pyproject(".")
        .with_source("mypkg/__init__.py", "")
        .with_source("mypkg/core.py", "class OldHelper: pass")
        .with_source(
            "main.py",
            """
            import mypkg.core

            h = mypkg.core.OldHelper()
            """,
        )
        .build()
    )

    # 2. Analyze
    index_store = create_populated_index(project_root)
    workspace = Workspace(root_path=project_root)
    graph = SemanticGraph(workspace=workspace, index_store=index_store)
    graph.load("mypkg")
    graph.load("main")
    sidecar_manager = SidecarManager(root_path=project_root)
    ctx = RefactorContext(
        workspace=workspace,
        graph=graph,
        sidecar_manager=sidecar_manager,
        index_store=index_store,
    )

    from stitcher.refactor.migration import MigrationSpec
    from stitcher.refactor.engine.planner import Planner

    # 3. Plan
    op = RenameSymbolOperation("mypkg.core.OldHelper", "mypkg.core.NewHelper")
    spec = MigrationSpec().add(op)
    planner = Planner()
    ops = planner.plan(spec, ctx)

    # 4. Verify (without committing, just check the planned ops)
    assert len(ops) >= 2
    # Ensure we are dealing with WriteFileOps
    write_ops = {op.path.name: op for op in ops if isinstance(op, WriteFileOp)}
    assert len(write_ops) == 2

    assert "core.py" in write_ops
    assert "main.py" in write_ops
    assert "class NewHelper: pass" in write_ops["core.py"].content
    assert "h = mypkg.core.NewHelper()" in write_ops["main.py"].content


def test_rename_symbol_imported_with_alias(tmp_path):
    # 1. Setup
    project_root = (
        WorkspaceFactory(tmp_path)
        .with_pyproject(".")
        .with_source("mypkg/__init__.py", "")
        .with_source("mypkg/core.py", "class OldHelper: pass")
        .with_source(
            "main.py",
            """
            from mypkg.core import OldHelper as OH

            h = OH()
            """,
        )
        .build()
    )

    # 2. Analyze
    index_store = create_populated_index(project_root)
    workspace = Workspace(root_path=project_root)
    graph = SemanticGraph(workspace=workspace, index_store=index_store)
    graph.load("mypkg")
    graph.load("main")
    sidecar_manager = SidecarManager(root_path=project_root)
    ctx = RefactorContext(
        workspace=workspace,
        graph=graph,
        sidecar_manager=sidecar_manager,
        index_store=index_store,
    )

    from stitcher.refactor.migration import MigrationSpec
    from stitcher.refactor.engine.planner import Planner

    # 3. Plan
    op = RenameSymbolOperation("mypkg.core.OldHelper", "mypkg.core.NewHelper")
    spec = MigrationSpec().add(op)
    planner = Planner()
    ops = planner.plan(spec, ctx)

    # 4. Verify
    assert len(ops) >= 2
    write_ops = {op.path.name: op for op in ops if isinstance(op, WriteFileOp)}
    assert len(write_ops) == 2

    expected_main = "from mypkg.core import NewHelper as OH\\n\\nh = OH()"
    assert "core.py" in write_ops
    assert write_ops["core.py"].content.strip() == "class NewHelper: pass"
    assert "main.py" in write_ops
    assert expected_main in write_ops["main.py"].content
~~~~~
