好的，我明白了。核心问题在于，项目架构已经从分散的 `.json` 签名文件演进为集中的 `stitcher.lock` 文件，但大量的集成测试用例仍旧在验证旧的、已被废弃的行为，同时 `Planner` 的实现也没有完全跟上新架构（尤其是在处理跨包重构时）。

## [WIP] 我将分三步解决这个问题：
1.  **修复简单的 API 调用错误**：补全缺失的 `lock_manager` 参数。
2.  **修正核心业务逻辑**：重构 `Planner` 使其能够正确处理 `stitcher.lock` 文件的更新，包括跨包移动条目的复杂场景。
3.  **全面升级测试用例**：将所有失败的测试用例从验证 `.json` 文件的旧模式，迁移到验证 `stitcher.lock` 文件的新模式，以确保它们与当前架构保持一致。

---

### Script

#### Acts 1: 修复 API 兼容性问题

首先，我将修复两个测试用例中因 `RefactorContext` 构造函数变更而导致的 `TypeError`。

~~~~~act
patch_file
packages/stitcher-refactor/tests/integration/test_rename_suri_update.py
~~~~~
~~~~~python.old
    ctx = RefactorContext(
        workspace=workspace,
        graph=graph,
        sidecar_manager=sidecar_manager,
        index_store=index_store,
    )
~~~~~
~~~~~python.new
    lock_manager = LockFileManager()
    ctx = RefactorContext(
        workspace=workspace,
        graph=graph,
        sidecar_manager=sidecar_manager,
        index_store=index_store,
        lock_manager=lock_manager,
    )
~~~~~

~~~~~act
patch_file
packages/stitcher-refactor/tests/integration/test_rename_transformer_advanced.py
~~~~~
~~~~~python.old
    ctx = RefactorContext(
        workspace=workspace,
        graph=graph,
        sidecar_manager=sidecar_manager,
        index_store=index_store,
    )
~~~~~
~~~~~python.new
    lock_manager = LockFileManager()
    ctx = RefactorContext(
        workspace=workspace,
        graph=graph,
        sidecar_manager=sidecar_manager,
        index_store=index_store,
        lock_manager=lock_manager,
    )
~~~~~

#### Acts 2: 修正 Planner 核心逻辑

接下来，我将重构 `Planner`，使其能够正确、健壮地处理 `stitcher.lock` 文件的更新，包括跨包（即跨锁文件）的数据迁移。

~~~~~act
write_file
packages/stitcher-refactor/src/stitcher/refactor/engine/planner.py
~~~~~
~~~~~python
from collections import defaultdict
from pathlib import Path
from typing import List, Dict, TYPE_CHECKING
import json

if TYPE_CHECKING:
    from stitcher.refactor.migration import MigrationSpec
from stitcher.refactor.engine.context import RefactorContext
from stitcher.common.transaction import (
    FileOp,
    MoveFileOp,
    WriteFileOp,
    DeleteFileOp,
    DeleteDirectoryOp,
)
from stitcher.refactor.engine.intent import (
    RefactorIntent,
    RenameIntent,
    SidecarUpdateIntent,
    MoveFileIntent,
    DeleteFileIntent,
    ScaffoldIntent,
    DeleteDirectoryIntent,
    LockSymbolUpdateIntent,
    LockPathUpdateIntent,
)
from stitcher.refactor.engine.renamer import GlobalBatchRenamer
from stitcher.lang.sidecar import (
    SidecarTransformer,
    SidecarTransformContext,
    SidecarAdapter,
)
from stitcher.lang.python.uri import PythonURIGenerator
from .utils import path_to_fqn
from stitcher.spec import Fingerprint


class Planner:
    def plan(self, spec: "MigrationSpec", ctx: RefactorContext) -> List[FileOp]:
        all_ops: List[FileOp] = []

        # --- 1. Intent Collection ---
        all_intents: List[RefactorIntent] = []
        for operation in spec.operations:
            all_intents.extend(operation.collect_intents(ctx))

        # --- 2. Intent Aggregation & Processing ---

        # Aggregate renames for batch processing
        rename_map: Dict[str, str] = {}
        for intent in all_intents:
            if isinstance(intent, RenameIntent):
                rename_map[intent.old_fqn] = intent.new_fqn

        # Process symbol renames in code
        renamer = GlobalBatchRenamer(rename_map, ctx)
        all_ops.extend(renamer.analyze())

        module_rename_map: Dict[str, str] = {}
        for intent in all_intents:
            if isinstance(intent, MoveFileIntent):
                old_mod_fqn = path_to_fqn(intent.src_path, ctx.graph.search_paths)
                new_mod_fqn = path_to_fqn(intent.dest_path, ctx.graph.search_paths)
                if old_mod_fqn and new_mod_fqn:
                    module_rename_map[old_mod_fqn] = new_mod_fqn

        # Aggregate and process sidecar updates
        sidecar_updates: defaultdict[Path, List[SidecarUpdateIntent]] = defaultdict(
            list
        )
        for intent in all_intents:
            if isinstance(intent, SidecarUpdateIntent):
                sidecar_updates[intent.sidecar_path].append(intent)

        sidecar_adapter = SidecarAdapter(ctx.workspace.root_path)
        sidecar_transformer = SidecarTransformer()
        for path, intents in sidecar_updates.items():
            is_yaml = path.suffix in [".yaml", ".yml"]
            data = (
                sidecar_adapter.load_raw_data(path)
                if is_yaml
                else json.loads(path.read_text("utf-8")) if path.exists() else {}
            )

            for intent in intents:
                old_module_fqn = intent.module_fqn
                new_module_fqn = (
                    module_rename_map.get(old_module_fqn, old_module_fqn)
                    if old_module_fqn
                    else None
                )
                transform_ctx = SidecarTransformContext(
                    old_module_fqn=old_module_fqn,
                    new_module_fqn=new_module_fqn,
                    old_fqn=intent.old_fqn,
                    new_fqn=intent.new_fqn,
                    old_file_path=intent.old_file_path,
                    new_file_path=intent.new_file_path,
                )
                data = sidecar_transformer.transform(path, data, transform_ctx)

            content = (
                sidecar_adapter.dump_raw_data_to_string(data)
                if is_yaml
                else json.dumps(data, indent=2, sort_keys=True)
            )
            all_ops.append(WriteFileOp(path.relative_to(ctx.graph.root_path), content))

        # --- Process Lock Update Intents ---
        lock_states: Dict[Path, Dict[str, Fingerprint]] = {}

        def get_lock_data(pkg_root: Path) -> Dict[str, Fingerprint]:
            if pkg_root not in lock_states:
                lock_states[pkg_root] = ctx.lock_manager.load(pkg_root)
            return lock_states[pkg_root]

        sorted_lock_intents = sorted(
            [i for i in all_intents if isinstance(i, (LockSymbolUpdateIntent, LockPathUpdateIntent))],
            key=lambda x: 0 if isinstance(x, LockPathUpdateIntent) else 1,
        )

        for intent in sorted_lock_intents:
            if isinstance(intent, LockPathUpdateIntent):
                src_pkg = ctx.workspace.find_owning_package(ctx.workspace.root_path / intent.old_path_prefix)
                dest_pkg = ctx.workspace.find_owning_package(ctx.workspace.root_path / intent.new_path_prefix)
                src_data = get_lock_data(src_pkg)

                suris_to_move = {}
                for suri in list(src_data.keys()):
                    path, fragment = PythonURIGenerator.parse(suri)
                    new_path = None
                    if path == intent.old_path_prefix:
                        new_path = intent.new_path_prefix
                    elif path.startswith(intent.old_path_prefix + "/"):
                        suffix = path[len(intent.old_path_prefix) :]
                        new_path = intent.new_path_prefix + suffix

                    if new_path:
                        uri_gen = PythonURIGenerator()
                        new_suri = uri_gen.generate_symbol_uri(new_path, fragment) if fragment else uri_gen.generate_file_uri(new_path)
                        suris_to_move[suri] = new_suri

                if src_pkg == dest_pkg:
                    for old, new in suris_to_move.items():
                        if old in src_data:
                            src_data[new] = src_data.pop(old)
                else:
                    dest_data = get_lock_data(dest_pkg)
                    for old, new in suris_to_move.items():
                        if old in src_data:
                            dest_data[new] = src_data.pop(old)

            elif isinstance(intent, LockSymbolUpdateIntent):
                data = get_lock_data(intent.package_root)
                if intent.old_suri in data:
                    data[intent.new_suri] = data.pop(intent.old_suri)

        for pkg_root, data in lock_states.items():
            content = ctx.lock_manager.serialize(data)
            rel_lock_path = (pkg_root / "stitcher.lock").relative_to(ctx.graph.root_path)
            all_ops.append(WriteFileOp(rel_lock_path, content))

        # Process simple filesystem intents
        for intent in all_intents:
            if isinstance(intent, MoveFileIntent):
                all_ops.append(MoveFileOp(intent.src_path.relative_to(ctx.graph.root_path), intent.dest_path.relative_to(ctx.graph.root_path)))
            elif isinstance(intent, DeleteFileIntent):
                all_ops.append(DeleteFileOp(intent.path.relative_to(ctx.graph.root_path)))
            elif isinstance(intent, DeleteDirectoryIntent):
                all_ops.append(DeleteDirectoryOp(intent.path.relative_to(ctx.graph.root_path)))
            elif isinstance(intent, ScaffoldIntent):
                all_ops.append(WriteFileOp(intent.path.relative_to(ctx.graph.root_path), intent.content))

        return all_ops
~~~~~

#### Acts 3: 全面升级集成测试用例

最后，我将逐一重构所有失败的测试用例，使其符合新的 `stitcher.lock` 架构。

~~~~~act
write_file
packages/stitcher-refactor/tests/integration/test_debug_rename_failure.py
~~~~~
~~~~~python
import yaml
import json

from stitcher.analysis.semantic import SemanticGraph
from stitcher.refactor.engine.context import RefactorContext
from stitcher.common.transaction import TransactionManager
from stitcher.refactor.operations.rename_symbol import RenameSymbolOperation
from stitcher.refactor.sidecar.manager import SidecarManager
from stitcher.lang.sidecar import LockFileManager
from stitcher.workspace import Workspace
from stitcher.test_utils import WorkspaceFactory, create_populated_index
from stitcher.common.transaction import WriteFileOp
from stitcher.spec import Fingerprint


BUS_PY_CONTENT = """
from typing import Any, Optional, Union, Callable

from needle.pointer import SemanticPointer
from .protocols import Renderer


class MessageBus:
    def __init__(self, operator: Callable[[Union[str, SemanticPointer]], str]):
        self._renderer: Optional[Renderer] = None
        self._operator = operator

    def set_renderer(self, renderer: Renderer):
        self._renderer = renderer

    def _render(
        self, level: str, msg_id: Union[str, SemanticPointer], **kwargs: Any
    ) -> None:
        if not self._renderer:
            return
        template = self._operator(msg_id)
        if template is None:
            template = str(msg_id)
        try:
            message = template.format(**kwargs)
        except KeyError:
            message = f"<formatting_error for '{str(msg_id)}'>"
        self._renderer.render(message, level)

    def info(self, msg_id: Union[str, SemanticPointer], **kwargs: Any) -> None:
        self._render("info", msg_id, **kwargs)

    def success(self, msg_id: Union[str, SemanticPointer], **kwargs: Any) -> None:
        self._render("success", msg_id, **kwargs)

    def warning(self, msg_id: Union[str, SemanticPointer], **kwargs: Any) -> None:
        self._render("warning", msg_id, **kwargs)

    def error(self, msg_id: Union[str, SemanticPointer], **kwargs: Any) -> None:
        self._render("error", msg_id, **kwargs)

    def debug(self, msg_id: Union[str, SemanticPointer], **kwargs: Any) -> None:
        self._render("debug", msg_id, **kwargs)

    def render_to_string(
        self, msg_id: Union[str, SemanticPointer], **kwargs: Any
    ) -> str:
        template = self._operator(msg_id)
        if template is None:
            return str(msg_id)
        try:
            return template.format(**kwargs)
        except KeyError:
            return f"<formatting_error for '{str(msg_id)}'>"
"""


def test_rename_class_updates_code_yaml_and_lock_file(tmp_path):
    # 1. ARRANGE
    factory = WorkspaceFactory(tmp_path)
    old_fqn = "stitcher.common.messaging.bus.MessageBus"
    new_fqn = "stitcher.common.messaging.bus.FeedbackBus"

    py_rel_path = "packages/stitcher-common/src/stitcher/common/messaging/bus.py"
    old_suri = f"py://{py_rel_path}#MessageBus"
    new_suri = f"py://{py_rel_path}#FeedbackBus"

    lock_manager = LockFileManager()
    fingerprints = {old_suri: Fingerprint.from_dict({"hash": "abc"})}
    lock_content = lock_manager.serialize(fingerprints)

    project_root = (
        factory.with_pyproject(".")
        .with_pyproject("packages/stitcher-common")
        .with_source(
            "packages/stitcher-common/src/stitcher/common/__init__.py",
            "from .messaging.bus import MessageBus\n",
        )
        .with_source(
            "packages/stitcher-common/src/stitcher/common/messaging/protocols.py",
            "class Renderer: pass",
        )
        .with_source(
            "packages/stitcher-common/src/stitcher/common/messaging/__init__.py", ""
        )
        .with_source(
            "packages/stitcher-common/src/stitcher/common/messaging/bus.py",
            BUS_PY_CONTENT.replace("class MessageBus:", "class MessageBus: pass"),
        )
        .with_docs(
            "packages/stitcher-common/src/stitcher/common/messaging/bus.stitcher.yaml",
            {
                "MessageBus": "Docs for MessageBus.",
                "MessageBus.info": "Docs for info method.",
            },
        )
        .with_raw_file(
            "packages/stitcher-common/stitcher.lock",
            lock_content,
        )
        .build()
    )

    bus_path = project_root / py_rel_path
    bus_yaml_path = bus_path.with_suffix(".stitcher.yaml")
    bus_lock_path = project_root / "packages/stitcher-common/stitcher.lock"

    # 2. ACT
    index_store = create_populated_index(project_root)
    workspace = Workspace(root_path=project_root)
    graph = SemanticGraph(workspace=workspace, index_store=index_store)
    graph.load("stitcher")

    sidecar_manager = SidecarManager(root_path=project_root)
    ctx = RefactorContext(
        workspace=workspace,
        graph=graph,
        sidecar_manager=sidecar_manager,
        index_store=index_store,
        lock_manager=lock_manager,
    )
    from stitcher.refactor.migration import MigrationSpec
    from stitcher.refactor.engine.planner import Planner

    op = RenameSymbolOperation(old_fqn, new_fqn)
    spec = MigrationSpec().add(op)
    planner = Planner()
    file_ops = planner.plan(spec, ctx)

    tm = TransactionManager(project_root)
    for fop in file_ops:
        if isinstance(fop, WriteFileOp):
            tm.add_write(fop.path, fop.content)
    tm.commit()

    # 4. ASSERT
    updated_content = bus_path.read_text()
    assert "class FeedbackBus:" in updated_content

    updated_yaml_data = yaml.safe_load(bus_yaml_path.read_text())
    assert "FeedbackBus" in updated_yaml_data
    assert "MessageBus" not in updated_yaml_data
    assert "FeedbackBus.info" in updated_yaml_data

    updated_lock_data = json.loads(bus_lock_path.read_text())["fingerprints"]
    assert new_suri in updated_lock_data
    assert old_suri not in updated_lock_data
    assert updated_lock_data[new_suri] == {"hash": "abc"}
~~~~~
~~~~~act
write_file
packages/stitcher-refactor/tests/integration/test_monorepo_refactor_e2e.py
~~~~~
~~~~~python
import json
import yaml
from stitcher.refactor.engine.context import RefactorContext
from stitcher.analysis.semantic import SemanticGraph
from stitcher.common.transaction import (
    TransactionManager,
    MoveFileOp,
    WriteFileOp,
)
from stitcher.refactor.operations.move_file import MoveFileOperation
from stitcher.refactor.sidecar.manager import SidecarManager
from stitcher.lang.sidecar import LockFileManager
from stitcher.workspace import Workspace
from stitcher.test_utils import WorkspaceFactory, create_populated_index
from stitcher.spec import Fingerprint


def test_move_file_in_monorepo_updates_cross_package_imports(tmp_path):
    # 1. ARRANGE
    factory = WorkspaceFactory(tmp_path)
    py_rel_path = "packages/pkg_a/src/pkga_lib/core.py"
    old_suri = f"py://{py_rel_path}#SharedClass"
    
    lock_manager = LockFileManager()
    fingerprints = {old_suri: Fingerprint.from_dict({"hash": "abc"})}
    lock_content = lock_manager.serialize(fingerprints)

    project_root = (
        factory.with_pyproject("packages/pkg_a")
        .with_source("packages/pkg_a/src/pkga_lib/__init__.py", "")
        .with_source("packages/pkg_a/src/pkga_lib/core.py", "class SharedClass: pass")
        .with_docs(
            "packages/pkg_a/src/pkga_lib/core.stitcher.yaml",
            {"SharedClass": "A shared class."},
        )
        .with_raw_file("packages/pkg_a/stitcher.lock", lock_content)
        .with_pyproject("packages/pkg_b")
        .with_source("packages/pkg_b/src/pkgb_app/__init__.py", "")
        .with_source(
            "packages/pkg_b/src/pkgb_app/main.py",
            "from pkga_lib.core import SharedClass\n\ninstance = SharedClass()",
        )
        .build()
    )

    src_path = project_root / "packages/pkg_a/src/pkga_lib/core.py"
    dest_path = project_root / "packages/pkg_a/src/pkga_lib/utils/tools.py"
    consumer_path = project_root / "packages/pkg_b/src/pkgb_app/main.py"

    # 2. ACT
    index_store = create_populated_index(project_root)
    workspace = Workspace(root_path=project_root)
    graph = SemanticGraph(workspace=workspace, index_store=index_store)
    graph.load("pkga_lib")
    graph.load("pkgb_app")
    
    sidecar_manager = SidecarManager(root_path=project_root)
    ctx = RefactorContext(
        workspace=workspace,
        graph=graph,
        sidecar_manager=sidecar_manager,
        index_store=index_store,
        lock_manager=lock_manager,
    )

    from stitcher.refactor.migration import MigrationSpec
    from stitcher.refactor.engine.planner import Planner

    op = MoveFileOperation(src_path, dest_path)
    spec = MigrationSpec().add(op)
    planner = Planner()
    file_ops = planner.plan(spec, ctx)

    tm = TransactionManager(project_root)
    for fop in file_ops:
        if isinstance(fop, MoveFileOp):
            tm.add_move(fop.path, fop.dest)
        elif isinstance(fop, WriteFileOp):
            tm.add_write(fop.path, fop.content)
    tm.commit()

    # 3. ASSERT
    assert not src_path.exists()
    assert dest_path.exists()
    assert dest_path.with_suffix(".stitcher.yaml").exists()
    
    lock_path = project_root / "packages/pkg_a/stitcher.lock"
    assert lock_path.exists()

    updated_consumer_code = consumer_path.read_text()
    assert "from pkga_lib.utils.tools import SharedClass" in updated_consumer_code

    new_py_rel_path = "packages/pkg_a/src/pkga_lib/utils/tools.py"
    expected_suri = f"py://{new_py_rel_path}#SharedClass"
    
    lock_data = json.loads(lock_path.read_text())["fingerprints"]
    assert expected_suri in lock_data
    assert old_suri not in lock_data
    assert lock_data[expected_suri] == {"hash": "abc"}
~~~~~
~~~~~act
write_file
packages/stitcher-refactor/tests/integration/test_move_directory_e2e.py
~~~~~
~~~~~python
import yaml
import json

from stitcher.analysis.semantic import SemanticGraph
from stitcher.refactor.engine.context import RefactorContext
from stitcher.common.transaction import (
    TransactionManager,
    MoveFileOp,
    DeleteDirectoryOp,
    WriteFileOp,
)
from stitcher.refactor.operations.move_directory import MoveDirectoryOperation
from stitcher.refactor.sidecar.manager import SidecarManager
from stitcher.lang.sidecar import LockFileManager
from stitcher.workspace import Workspace
from stitcher.test_utils import WorkspaceFactory, create_populated_index
from stitcher.spec import Fingerprint


def test_move_directory_updates_all_contents_and_references(tmp_path):
    factory = WorkspaceFactory(tmp_path)
    py_rel_path = "mypkg/core/utils.py"
    old_suri = f"py://{py_rel_path}#Helper"

    lock_manager = LockFileManager()
    fingerprints = {old_suri: Fingerprint.from_dict({"hash": "123"})}
    lock_content = lock_manager.serialize(fingerprints)

    project_root = (
        factory.with_pyproject(".")
        .with_source("mypkg/core/__init__.py", "")
        .with_source("mypkg/core/utils.py", "class Helper: pass")
        .with_raw_file("mypkg/core/config.txt", "setting=value")
        .with_source("app.py", "from mypkg.core.utils import Helper\n\nh = Helper()")
        .with_docs("mypkg/core/utils.stitcher.yaml", {"Helper": "Doc for Helper"})
        .with_raw_file("stitcher.lock", lock_content)
        .build()
    )

    core_dir = project_root / "mypkg/core"
    services_dir = project_root / "mypkg/services"
    app_py = project_root / "app.py"
    lock_path = project_root / "stitcher.lock"

    index_store = create_populated_index(project_root)
    workspace = Workspace(root_path=project_root)
    graph = SemanticGraph(workspace=workspace, index_store=index_store)
    graph.load("mypkg")
    graph.load("app")
    
    sidecar_manager = SidecarManager(root_path=project_root)
    ctx = RefactorContext(
        workspace=workspace,
        graph=graph,
        sidecar_manager=sidecar_manager,
        index_store=index_store,
        lock_manager=lock_manager,
    )

    from stitcher.refactor.migration import MigrationSpec
    from stitcher.refactor.engine.planner import Planner

    op = MoveDirectoryOperation(core_dir, services_dir)
    spec = MigrationSpec().add(op)
    planner = Planner()
    file_ops = planner.plan(spec, ctx)

    tm = TransactionManager(project_root)
    for fop in file_ops:
        if isinstance(fop, MoveFileOp):
            tm.add_move(fop.path, fop.dest)
        elif isinstance(fop, DeleteDirectoryOp):
            tm.add_delete_dir(fop.path)
        elif isinstance(fop, WriteFileOp):
            tm.add_write(fop.path, fop.content)
    tm.commit()

    assert not core_dir.exists()
    assert services_dir.exists()
    assert (services_dir / "utils.py").exists()
    assert (services_dir / "utils.stitcher.yaml").exists()
    assert lock_path.exists()

    new_py_rel_path = "mypkg/services/utils.py"
    expected_suri = f"py://{new_py_rel_path}#Helper"
    
    lock_data = json.loads(lock_path.read_text())["fingerprints"]
    assert expected_suri in lock_data
    assert lock_data[expected_suri] == {"hash": "123"}
    
    updated_app_code = app_py.read_text(encoding="utf-8")
    assert "from mypkg.services.utils import Helper" in updated_app_code
~~~~~
~~~~~act
write_file
packages/stitcher-refactor/tests/integration/test_move_directory_monorepo_e2e.py
~~~~~
~~~~~python
import json
import yaml

from stitcher.analysis.semantic import SemanticGraph
from stitcher.refactor.engine.context import RefactorContext
from stitcher.common.transaction import (
    TransactionManager,
    MoveFileOp,
    DeleteDirectoryOp,
    WriteFileOp,
)
from stitcher.refactor.operations.move_directory import MoveDirectoryOperation
from stitcher.refactor.sidecar.manager import SidecarManager
from stitcher.lang.sidecar import LockFileManager
from stitcher.workspace import Workspace
from stitcher.test_utils import WorkspaceFactory, create_populated_index
from stitcher.spec import Fingerprint


def test_move_directory_in_monorepo_updates_cross_package_references(tmp_path):
    factory = WorkspaceFactory(tmp_path)
    py_rel_path = "packages/cascade-engine/src/cascade/engine/core/logic.py"
    old_suri = f"py://{py_rel_path}#EngineLogic"

    lock_manager = LockFileManager()
    fingerprints = {old_suri: Fingerprint.from_dict({"hash": "abc"})}
    lock_content = lock_manager.serialize(fingerprints)

    project_root = (
        factory
        .with_pyproject("packages/cascade-engine")
        .with_source("packages/cascade-engine/src/cascade/__init__.py", "__path__ = __import__('pkgutil').extend_path(__path__, __name__)")
        .with_source("packages/cascade-engine/src/cascade/engine/__init__.py", "")
        .with_source("packages/cascade-engine/src/cascade/engine/core/__init__.py", "")
        .with_source("packages/cascade-engine/src/cascade/engine/core/logic.py", "class EngineLogic: pass")
        .with_docs("packages/cascade-engine/src/cascade/engine/core/logic.stitcher.yaml", {"EngineLogic": "Core engine logic."})
        .with_raw_file("packages/cascade-engine/stitcher.lock", lock_content)
        
        .with_pyproject("packages/cascade-runtime")
        .with_source("packages/cascade-runtime/src/cascade/__init__.py", "__path__ = __import__('pkgutil').extend_path(__path__, __name__)")
        .with_source("packages/cascade-runtime/src/cascade/runtime/__init__.py", "")
        .with_source("packages/cascade-runtime/src/cascade/runtime/app.py", "from cascade.engine.core.logic import EngineLogic\n\nlogic = EngineLogic()")
    ).build()

    src_dir = project_root / "packages/cascade-engine/src/cascade/engine/core"
    dest_dir = project_root / "packages/cascade-runtime/src/cascade/runtime/core"
    consumer_path = project_root / "packages/cascade-runtime/src/cascade/runtime/app.py"
    src_lock_path = project_root / "packages/cascade-engine/stitcher.lock"
    dest_lock_path = project_root / "packages/cascade-runtime/stitcher.lock"

    index_store = create_populated_index(project_root)
    workspace = Workspace(root_path=project_root)
    graph = SemanticGraph(workspace=workspace, index_store=index_store)
    graph.load("cascade")
    
    sidecar_manager = SidecarManager(root_path=project_root)
    ctx = RefactorContext(
        workspace=workspace,
        graph=graph,
        sidecar_manager=sidecar_manager,
        index_store=index_store,
        lock_manager=lock_manager,
    )

    from stitcher.refactor.migration import MigrationSpec
    from stitcher.refactor.engine.planner import Planner

    op = MoveDirectoryOperation(src_dir, dest_dir)
    spec = MigrationSpec().add(op)
    planner = Planner()
    file_ops = planner.plan(spec, ctx)

    tm = TransactionManager(project_root)
    for fop in file_ops:
        if isinstance(fop, MoveFileOp):
            tm.add_move(fop.path, fop.dest)
        elif isinstance(fop, DeleteDirectoryOp):
            tm.add_delete_dir(fop.path)
        elif isinstance(fop, WriteFileOp):
            tm.add_write(fop.path, fop.content)
    tm.commit()

    assert not src_dir.exists()
    assert dest_dir.exists()
    
    updated_consumer_code = consumer_path.read_text()
    assert "from cascade.runtime.core.logic import EngineLogic" in updated_consumer_code

    src_lock_data = json.loads(src_lock_path.read_text())["fingerprints"]
    assert old_suri not in src_lock_data
    
    assert dest_lock_path.exists()
    dest_lock_data = json.loads(dest_lock_path.read_text())["fingerprints"]
    new_py_rel_path = "packages/cascade-runtime/src/cascade/runtime/core/logic.py"
    expected_suri = f"py://{new_py_rel_path}#EngineLogic"
    assert expected_suri in dest_lock_data
    assert dest_lock_data[expected_suri] == {"hash": "abc"}
~~~~~
~~~~~act
write_file
packages/stitcher-refactor/tests/integration/test_move_file_e2e.py
~~~~~
~~~~~python
import json
import yaml
from stitcher.analysis.semantic import SemanticGraph
from stitcher.refactor.engine.context import RefactorContext
from stitcher.common.transaction import (
    TransactionManager,
    MoveFileOp,
    WriteFileOp,
)
from stitcher.refactor.operations.move_file import MoveFileOperation
from stitcher.refactor.sidecar.manager import SidecarManager
from stitcher.lang.sidecar import LockFileManager
from stitcher.workspace import Workspace
from stitcher.test_utils import WorkspaceFactory, create_populated_index
from stitcher.spec import Fingerprint


def test_move_file_flat_layout(tmp_path):
    factory = WorkspaceFactory(tmp_path)
    py_rel_path = "mypkg/old.py"
    old_suri = f"py://{py_rel_path}#A"

    lock_manager = LockFileManager()
    fingerprints = {old_suri: Fingerprint.from_dict({"h": "1"})}
    lock_content = lock_manager.serialize(fingerprints)

    project_root = (
        factory.with_pyproject(".")
        .with_source("mypkg/__init__.py", "")
        .with_source("mypkg/old.py", "class A:\n    pass")
        .with_source(
            "mypkg/app.py",
            "from mypkg.old import A\n\nx = A()",
        )
        .with_docs("mypkg/old.stitcher.yaml", {"A": "Doc"})
        .with_raw_file("stitcher.lock", lock_content)
        .build()
    )

    old_py = project_root / "mypkg/old.py"
    app_py = project_root / "mypkg/app.py"
    new_py = project_root / "mypkg/new.py"
    lock_path = project_root / "stitcher.lock"

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
        lock_manager=lock_manager,
    )
    from stitcher.refactor.migration import MigrationSpec
    from stitcher.refactor.engine.planner import Planner

    op = MoveFileOperation(old_py, new_py)
    spec = MigrationSpec().add(op)
    planner = Planner()
    file_ops = planner.plan(spec, ctx)

    tm = TransactionManager(project_root)
    for fop in file_ops:
        if isinstance(fop, MoveFileOp):
            tm.add_move(fop.path, fop.dest)
        elif isinstance(fop, WriteFileOp):
            tm.add_write(fop.path, fop.content)
    tm.commit()

    assert not old_py.exists()
    assert new_py.exists()
    assert new_py.with_suffix(".stitcher.yaml").exists()
    
    new_app = app_py.read_text("utf-8")
    assert "from mypkg.new import A" in new_app

    new_py_rel_path = "mypkg/new.py"
    new_suri = f"py://{new_py_rel_path}#A"
    lock_data = json.loads(lock_path.read_text())["fingerprints"]
    assert new_suri in lock_data
    assert old_suri not in lock_data
~~~~~
~~~~~act
write_file
packages/stitcher-refactor/tests/integration/test_move_nested_directory_e2e.py
~~~~~
~~~~~python
import json
import yaml
from stitcher.refactor.engine.context import RefactorContext
from stitcher.analysis.semantic import SemanticGraph
from stitcher.common.transaction import (
    DeleteDirectoryOp,
    MoveFileOp,
    TransactionManager,
    WriteFileOp,
)
from stitcher.refactor.operations.move_directory import MoveDirectoryOperation
from stitcher.refactor.sidecar.manager import SidecarManager
from stitcher.lang.sidecar import LockFileManager
from stitcher.workspace import Workspace
from stitcher.test_utils import WorkspaceFactory, create_populated_index
from stitcher.spec import Fingerprint


def test_move_deeply_nested_directory_updates_all_references_and_sidecars(tmp_path):
    factory = WorkspaceFactory(tmp_path)
    py_rel_path = "src/cascade/core/adapters/cache/in_memory.py"
    old_suri = f"py://{py_rel_path}#InMemoryCache"
    
    lock_manager = LockFileManager()
    fingerprints = {old_suri: Fingerprint.from_dict({"h": "123"})}
    lock_content = lock_manager.serialize(fingerprints)

    project_root = (
        factory.with_pyproject(".")
        .with_source("src/cascade/__init__.py", "")
        .with_source("src/cascade/core/__init__.py", "")
        .with_source("src/cascade/core/adapters/__init__.py", "")
        .with_source("src/cascade/core/adapters/cache/__init__.py", "")
        .with_source("src/cascade/core/adapters/cache/in_memory.py", "class InMemoryCache: pass")
        .with_docs("src/cascade/core/adapters/cache/in_memory.stitcher.yaml", {"InMemoryCache": "Doc for Cache"})
        .with_raw_file("stitcher.lock", lock_content)
        .with_source("src/app.py", "from cascade.core.adapters.cache.in_memory import InMemoryCache")
        .build()
    )

    src_dir_to_move = project_root / "src/cascade/core/adapters"
    dest_dir = project_root / "src/cascade/runtime/adapters"
    app_py_path = project_root / "src/app.py"
    lock_path = project_root / "stitcher.lock"

    index_store = create_populated_index(project_root)
    workspace = Workspace(root_path=project_root)
    graph = SemanticGraph(workspace=workspace, index_store=index_store)
    graph.load("cascade")
    graph.load("app")
    
    sidecar_manager = SidecarManager(root_path=project_root)
    ctx = RefactorContext(
        workspace=workspace,
        graph=graph,
        sidecar_manager=sidecar_manager,
        index_store=index_store,
        lock_manager=lock_manager,
    )

    from stitcher.refactor.migration import MigrationSpec
    from stitcher.refactor.engine.planner import Planner

    op = MoveDirectoryOperation(src_dir_to_move, dest_dir)
    spec = MigrationSpec().add(op)
    planner = Planner()
    file_ops = planner.plan(spec, ctx)

    tm = TransactionManager(project_root)
    for fop in file_ops:
        if isinstance(fop, MoveFileOp):
            tm.add_move(fop.path, fop.dest)
        elif isinstance(fop, DeleteDirectoryOp):
            tm.add_delete_dir(fop.path)
        elif isinstance(fop, WriteFileOp):
            tm.add_write(fop.path, fop.content)
    tm.commit()

    assert not src_dir_to_move.exists()
    assert dest_dir.exists()
    
    updated_app_code = app_py_path.read_text()
    assert "from cascade.runtime.adapters.cache.in_memory import InMemoryCache" in updated_app_code

    new_py_rel_path = "src/cascade/runtime/adapters/cache/in_memory.py"
    expected_suri = f"py://{new_py_rel_path}#InMemoryCache"
    
    lock_data = json.loads(lock_path.read_text())["fingerprints"]
    assert expected_suri in lock_data
    assert lock_data[expected_suri] == {"h": "123"}
~~~~~
~~~~~act
write_file
packages/stitcher-refactor/tests/integration/test_refactor_move_updates_suri_in_signatures.py
~~~~~
~~~~~python
import json
from pathlib import Path
from stitcher.test_utils import WorkspaceFactory, create_test_app


def test_move_file_operation_updates_suri_in_lockfile(tmp_path: Path):
    pkg_a_root = tmp_path / "packages" / "pkg-a"
    workspace_factory = WorkspaceFactory(root_path=tmp_path)
    workspace_root = (
        workspace_factory.with_config({"scan_paths": ["packages/pkg-a/src"]})
        .with_pyproject("packages/pkg-a")
        .with_source(
            "packages/pkg-a/src/my_app/logic.py",
            'def do_something():\n    """Doc"""\n    pass',
        )
        .build()
    )

    app = create_test_app(workspace_root)
    app.run_init()

    lock_path = pkg_a_root / "stitcher.lock"
    assert lock_path.exists()

    old_suri = "py://packages/pkg-a/src/my_app/logic.py#do_something"
    new_suri = "py://packages/pkg-a/src/my_app/core/logic.py#do_something"

    initial_data = json.loads(lock_path.read_text())
    assert old_suri in initial_data["fingerprints"]

    migration_script_content = """
from pathlib import Path
from stitcher.refactor.migration import MigrationSpec, Move

def upgrade(spec: MigrationSpec):
    spec.add(Move(
        Path("packages/pkg-a/src/my_app/logic.py"),
        Path("packages/pkg-a/src/my_app/core/logic.py")
    ))
"""
    migration_script_path = workspace_root / "migration.py"
    migration_script_path.write_text(migration_script_content)

    app.run_refactor_apply(migration_script_path, confirm_callback=lambda _: True)

    assert lock_path.exists()
    final_data = json.loads(lock_path.read_text())["fingerprints"]
    assert old_suri not in final_data
    assert new_suri in final_data
    assert "baseline_code_structure_hash" in final_data[new_suri]
~~~~~
~~~~~act
write_file
packages/stitcher-refactor/tests/integration/test_rename_e2e.py
~~~~~
~~~~~python
from stitcher.analysis.semantic import SemanticGraph
from stitcher.refactor.engine.context import RefactorContext
from stitcher.common.transaction import TransactionManager, WriteFileOp
from stitcher.refactor.operations.rename_symbol import RenameSymbolOperation
from stitcher.refactor.sidecar.manager import SidecarManager
from stitcher.lang.sidecar import LockFileManager
from stitcher.workspace import Workspace
from stitcher.test_utils import WorkspaceFactory, create_populated_index
from stitcher.spec import Fingerprint

import yaml
import json


def test_rename_symbol_end_to_end(tmp_path):
    factory = WorkspaceFactory(tmp_path)
    py_rel_path = "mypkg/core.py"
    old_helper_suri = f"py://{py_rel_path}#OldHelper"
    old_func_suri = f"py://{py_rel_path}#old_func"
    new_helper_suri = f"py://{py_rel_path}#NewHelper"

    lock_manager = LockFileManager()
    fingerprints = {
        old_helper_suri: Fingerprint.from_dict({"baseline_code_structure_hash": "hash1"}),
        old_func_suri: Fingerprint.from_dict({"baseline_code_structure_hash": "hash2"}),
    }
    lock_content = lock_manager.serialize(fingerprints)

    project_root = (
        factory.with_pyproject(".")
        .with_source(
            "mypkg/core.py",
            "class OldHelper: pass\ndef old_func(): pass",
        )
        .with_source("mypkg/app.py", "from .core import OldHelper, old_func\nh = OldHelper()\nold_func()")
        .with_source("mypkg/__init__.py", "")
        .with_docs("mypkg/core.stitcher.yaml", {"OldHelper": "doc", "old_func": "doc"})
        .with_raw_file("stitcher.lock", lock_content)
        .build()
    )

    core_path = project_root / "mypkg/core.py"
    app_path = project_root / "mypkg/app.py"
    lock_path = project_root / "stitcher.lock"

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
        lock_manager=lock_manager,
    )
    
    from stitcher.refactor.migration import MigrationSpec
    from stitcher.refactor.engine.planner import Planner

    op = RenameSymbolOperation("mypkg.core.OldHelper", "mypkg.core.NewHelper")
    spec = MigrationSpec().add(op)
    planner = Planner()
    file_ops = planner.plan(spec, ctx)

    tm = TransactionManager(project_root)
    for op in file_ops:
        if isinstance(op, WriteFileOp):
            tm.add_write(op.path, op.content)
    tm.commit()

    assert "class NewHelper:" in core_path.read_text(encoding="utf-8")
    assert "from .core import NewHelper, old_func" in app_path.read_text(encoding="utf-8")
    
    modified_lock_data = json.loads(lock_path.read_text("utf-8"))["fingerprints"]
    assert new_helper_suri in modified_lock_data
    assert old_helper_suri not in modified_lock_data
    assert modified_lock_data[new_helper_suri]["baseline_code_structure_hash"] == "hash1"
    assert old_func_suri in modified_lock_data # Ensure other keys are untouched
~~~~~
~~~~~act
write_file
packages/stitcher-refactor/tests/integration/test_rename_suri_update.py
~~~~~
~~~~~python
import json
from stitcher.analysis.semantic import SemanticGraph
from stitcher.refactor.engine.context import RefactorContext
from stitcher.common.transaction import TransactionManager, WriteFileOp
from stitcher.refactor.operations.rename_symbol import RenameSymbolOperation
from stitcher.refactor.sidecar.manager import SidecarManager
from stitcher.lang.sidecar import LockFileManager
from stitcher.workspace import Workspace
from stitcher.test_utils import WorkspaceFactory, create_populated_index
from stitcher.spec import Fingerprint


def test_rename_symbol_updates_suri_in_lockfile(tmp_path):
    factory = WorkspaceFactory(tmp_path)
    rel_py_path = "src/mypkg/core.py"
    old_suri = f"py://{rel_py_path}#MyClass"
    new_suri = f"py://{rel_py_path}#YourClass"

    lock_manager = LockFileManager()
    fingerprints = {old_suri: Fingerprint.from_dict({"hash": "original_hash"})}
    lock_content = lock_manager.serialize(fingerprints)

    project_root = (
        factory.with_pyproject(".")
        .with_source("src/mypkg/__init__.py", "")
        .with_source(rel_py_path, "class MyClass: pass")
        .with_raw_file("stitcher.lock", lock_content)
        .build()
    )
    lock_path = project_root / "stitcher.lock"

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
        lock_manager=lock_manager,
    )

    from stitcher.refactor.migration import MigrationSpec
    from stitcher.refactor.engine.planner import Planner

    op = RenameSymbolOperation("mypkg.core.MyClass", "mypkg.core.YourClass")
    spec = MigrationSpec().add(op)
    planner = Planner()
    file_ops = planner.plan(spec, ctx)

    tm = TransactionManager(project_root)
    for fop in file_ops:
        if isinstance(fop, WriteFileOp):
            tm.add_write(fop.path, fop.content)
    tm.commit()

    updated_data = json.loads(lock_path.read_text(encoding="utf-8"))["fingerprints"]
    assert old_suri not in updated_data
    assert new_suri in updated_data
    assert updated_data[new_suri]["hash"] == "original_hash"


def test_rename_nested_method_updates_suri_fragment(tmp_path):
    factory = WorkspaceFactory(tmp_path)
    rel_py_path = "src/mypkg/logic.py"
    old_suri = f"py://{rel_py_path}#MyClass.old_method"
    new_suri = f"py://{rel_py_path}#MyClass.new_method"
    
    lock_manager = LockFileManager()
    fingerprints = {old_suri: Fingerprint.from_dict({"hash": "123"})}
    lock_content = lock_manager.serialize(fingerprints)

    project_root = (
        factory.with_pyproject(".")
        .with_source(rel_py_path, "class MyClass:\n    def old_method(self): pass")
        .with_raw_file("stitcher.lock", lock_content)
        .build()
    )
    lock_path = project_root / "stitcher.lock"

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
        lock_manager=lock_manager,
    )

    from stitcher.refactor.migration import MigrationSpec
    from stitcher.refactor.engine.planner import Planner

    op = RenameSymbolOperation(
        "mypkg.logic.MyClass.old_method", "mypkg.logic.MyClass.new_method"
    )
    spec = MigrationSpec().add(op)
    planner = Planner()
    file_ops = planner.plan(spec, ctx)

    tm = TransactionManager(project_root)
    for fop in file_ops:
        if isinstance(fop, WriteFileOp):
            tm.add_write(fop.path, fop.content)
    tm.commit()

    updated_data = json.loads(lock_path.read_text())["fingerprints"]
    assert old_suri not in updated_data
    assert new_suri in updated_data
    assert updated_data[new_suri]["hash"] == "123"
~~~~~
~~~~~act
write_file
packages/stitcher-refactor/tests/integration/test_rename_symbol_monorepo_e2e.py
~~~~~
~~~~~python
import json
import yaml
from stitcher.refactor.engine.context import RefactorContext
from stitcher.analysis.semantic import SemanticGraph
from stitcher.common.transaction import TransactionManager, WriteFileOp
from stitcher.refactor.operations.rename_symbol import RenameSymbolOperation
from stitcher.refactor.sidecar.manager import SidecarManager
from stitcher.lang.sidecar import LockFileManager
from stitcher.workspace import Workspace
from stitcher.test_utils import WorkspaceFactory, create_populated_index
from stitcher.spec import Fingerprint


def test_rename_symbol_in_monorepo_updates_all_references_and_sidecars(tmp_path):
    factory = WorkspaceFactory(tmp_path)
    py_rel_path = "packages/pkg_a/src/pkga_lib/core.py"
    old_suri = f"py://{py_rel_path}#OldNameClass"
    new_suri = f"py://{py_rel_path}#NewNameClass"

    lock_manager = LockFileManager()
    fingerprints = {old_suri: Fingerprint.from_dict({"hash": "abc"})}
    lock_content = lock_manager.serialize(fingerprints)

    project_root = (
        factory.with_pyproject(".")
        .with_pyproject("packages/pkg_a")
        .with_source("packages/pkg_a/src/pkga_lib/__init__.py", "")
        .with_source("packages/pkg_a/src/pkga_lib/core.py", "class OldNameClass: pass")
        .with_docs("packages/pkg_a/src/pkga_lib/core.stitcher.yaml", {"OldNameClass": "Docs"})
        .with_raw_file("packages/pkg_a/stitcher.lock", lock_content)
        .with_source("packages/pkg_a/tests/test_core.py", "from pkga_lib.core import OldNameClass")
        
        .with_pyproject("packages/pkg_b")
        .with_source("packages/pkg_b/src/pkgb_app/__init__.py", "")
        .with_source("packages/pkg_b/src/pkgb_app/main.py", "from pkga_lib.core import OldNameClass")
        
        .with_source("tests/integration/test_system.py", "from pkga_lib.core import OldNameClass")
        .build()
    )

    pkg_a_test_path = project_root / "packages/pkg_a/tests/test_core.py"
    pkg_b_main_path = project_root / "packages/pkg_b/src/pkgb_app/main.py"
    lock_path = project_root / "packages/pkg_a/stitcher.lock"

    index_store = create_populated_index(project_root)
    workspace = Workspace(root_path=project_root)
    graph = SemanticGraph(workspace=workspace, index_store=index_store)
    graph.load("pkga_lib")
    graph.load("pkgb_app")
    
    sidecar_manager = SidecarManager(root_path=project_root)
    ctx = RefactorContext(
        workspace=workspace,
        graph=graph,
        sidecar_manager=sidecar_manager,
        index_store=index_store,
        lock_manager=lock_manager,
    )

    from stitcher.refactor.migration import MigrationSpec
    from stitcher.refactor.engine.planner import Planner

    op = RenameSymbolOperation("pkga_lib.core.OldNameClass", "pkga_lib.core.NewNameClass")
    spec = MigrationSpec().add(op)
    planner = Planner()
    file_ops = planner.plan(spec, ctx)

    tm = TransactionManager(project_root)
    for fop in file_ops:
        if isinstance(fop, WriteFileOp):
            tm.add_write(fop.path, fop.content)
    tm.commit()

    expected_import = "from pkga_lib.core import NewNameClass"
    assert expected_import in pkg_a_test_path.read_text()
    assert expected_import in pkg_b_main_path.read_text()

    lock_data = json.loads(lock_path.read_text())["fingerprints"]
    assert new_suri in lock_data
    assert old_suri not in lock_data
    assert lock_data[new_suri] == {"hash": "abc"}
~~~~~
~~~~~act
write_file
packages/stitcher-refactor/tests/integration/test_rename_transformer_advanced.py
~~~~~
~~~~~python
from stitcher.analysis.semantic import SemanticGraph
from stitcher.refactor.engine.context import RefactorContext
from stitcher.common.transaction import WriteFileOp
from stitcher.refactor.operations.rename_symbol import RenameSymbolOperation
from stitcher.refactor.sidecar.manager import SidecarManager
from stitcher.lang.sidecar import LockFileManager
from stitcher.workspace import Workspace
from stitcher.test_utils import WorkspaceFactory, create_populated_index


def test_rename_symbol_via_attribute_access(tmp_path):
    project_root = (
        WorkspaceFactory(tmp_path)
        .with_pyproject(".")
        .with_source("mypkg/__init__.py", "")
        .with_source("mypkg/core.py", "class OldHelper: pass")
        .with_source("main.py", "import mypkg.core\nh = mypkg.core.OldHelper()")
        .build()
    )

    index_store = create_populated_index(project_root)
    workspace = Workspace(root_path=project_root)
    graph = SemanticGraph(workspace=workspace, index_store=index_store)
    graph.load("mypkg")
    graph.load("main")
    
    sidecar_manager = SidecarManager(root_path=project_root)
    lock_manager = LockFileManager()
    ctx = RefactorContext(
        workspace=workspace,
        graph=graph,
        sidecar_manager=sidecar_manager,
        index_store=index_store,
        lock_manager=lock_manager,
    )

    from stitcher.refactor.migration import MigrationSpec
    from stitcher.refactor.engine.planner import Planner

    op = RenameSymbolOperation("mypkg.core.OldHelper", "mypkg.core.NewHelper")
    spec = MigrationSpec().add(op)
    planner = Planner()
    ops = planner.plan(spec, ctx)

    write_ops = {op.path.name: op for op in ops if isinstance(op, WriteFileOp)}
    assert "core.py" in write_ops
    assert "main.py" in write_ops
    assert "class NewHelper: pass" in write_ops["core.py"].content
    assert "h = mypkg.core.NewHelper()" in write_ops["main.py"].content


def test_rename_symbol_imported_with_alias(tmp_path):
    project_root = (
        WorkspaceFactory(tmp_path)
        .with_pyproject(".")
        .with_source("mypkg/__init__.py", "")
        .with_source("mypkg/core.py", "class OldHelper: pass")
        .with_source("main.py", "from mypkg.core import OldHelper as OH\nh = OH()")
        .build()
    )

    index_store = create_populated_index(project_root)
    workspace = Workspace(root_path=project_root)
    graph = SemanticGraph(workspace=workspace, index_store=index_store)
    graph.load("mypkg")
    graph.load("main")
    
    sidecar_manager = SidecarManager(root_path=project_root)
    lock_manager = LockFileManager()
    ctx = RefactorContext(
        workspace=workspace,
        graph=graph,
        sidecar_manager=sidecar_manager,
        index_store=index_store,
        lock_manager=lock_manager,
    )

    from stitcher.refactor.migration import MigrationSpec
    from stitcher.refactor.engine.planner import Planner

    op = RenameSymbolOperation("mypkg.core.OldHelper", "mypkg.core.NewHelper")
    spec = MigrationSpec().add(op)
    planner = Planner()
    ops = planner.plan(spec, ctx)

    write_ops = {op.path.name: op for op in ops if isinstance(op, WriteFileOp)}
    expected_main = "from mypkg.core import NewHelper as OH\n\nh = OH()"
    assert "core.py" in write_ops
    assert write_ops["core.py"].content.strip() == "class NewHelper: pass"
    assert "main.py" in write_ops
    assert write_ops["main.py"].content.strip() == expected_main.strip()
~~~~~

### 下一步建议

所有失败的测试都已根据新的 `stitcher.lock` 架构进行了修复和升级，并且核心的 `Planner` 逻辑也得到了增强。现在，我建议重新运行完整的测试套件，以验证所有变更是否正确，并确保没有引入新的回归问题。
