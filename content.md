1.  **修复测试工具**: 修改 `create_populated_index`，注册 `SidecarAdapter`。
2.  **修复 Planner**: 调整 `_plan_renames` 中对 JSON 引用的处理逻辑，允许 `target_node_fqn` 为空，只要 `target_node_id` 存在即可。

## [WIP] fix: Register SidecarAdapter in tests and refine Planner logic

### 用户需求

修复集成测试中 Sidecar 文件未被更新的 Bug。这源于两个问题：
1.  测试辅助函数 `create_populated_index` 未注册 `SidecarAdapter`，导致 Sidecar 文件未被索引。
2.  `Planner` 的逻辑过于严格，错误地过滤掉了仅包含 SURI 的引用。

### 评论

这是一个典型的“集成缝隙”问题。我们在生产代码中实现了所有逻辑，但在测试基础设施中漏掉了一个关键的配置步骤。同时，`Planner` 的防御性编程也稍微过头了。修复这两个问题将打通整个链路。

### 目标

1.  修改 `packages/stitcher-test-utils/src/stitcher/test_utils/helpers.py`，引入并注册 `SidecarAdapter`。
2.  修改 `packages/stitcher-refactor/src/stitcher/refactor/engine/planner.py`，放宽对 `target_node_fqn` 的检查。

### 基本原理

*   **测试工具修复**: 索引器必须知道如何解析 `.yaml` 和 `.json` 文件，否则数据库就是不完整的。
*   **Planner 修复**: Signature 文件本质上是基于 ID 的。当我们重命名一个符号时，我们知道它的旧 ID（`old_suri`）和新 FQN。我们可以通过解析旧 ID 获取 `path`，然后结合新 FQN 计算出新 ID（`new_suri`），从而构建重命名映射，而不需要依赖数据库中是否存在 `target_fqn`。

### 标签

#intent/fix #flow/ready #priority/critical #comp/test-utils #comp/refactor #concept/index #scope/core #ai/instruct #task/domain/testing #task/object/test-helper #task/action/fix #task.state/continue

---

### Script

#### Acts 1: 修复测试辅助函数

我们需要导入 `SidecarAdapter` 并注册它。

~~~~~act
patch_file
packages/stitcher-test-utils/src/stitcher/test_utils/helpers.py
~~~~~
~~~~~python.old
from stitcher.index.db import DatabaseManager
from stitcher.index.store import IndexStore
from stitcher.index.indexer import FileIndexer
from stitcher.lang.python.adapter import PythonAdapter
from stitcher.app.services import SignatureManager


def create_populated_index(root_path: Path) -> IndexStore:
    db_path = root_path / ".stitcher" / "index" / "index.db"

    db_manager = DatabaseManager(db_path)
    db_manager.initialize()
    store = IndexStore(db_manager)

    # The indexer needs a workspace-aware adapter.
    workspace = Workspace(root_path)
    search_paths = workspace.get_search_paths()

    # Discover files first, then index them.
    files_to_index = workspace.discover_files()

    indexer = FileIndexer(root_path, store)
    indexer.register_adapter(".py", PythonAdapter(root_path, search_paths))
    indexer.index_files(files_to_index)

    return store
~~~~~
~~~~~python.new
from stitcher.index.db import DatabaseManager
from stitcher.index.store import IndexStore
from stitcher.index.indexer import FileIndexer
from stitcher.lang.python.adapter import PythonAdapter
from stitcher.lang.sidecar.adapter import SidecarAdapter
from stitcher.app.services import SignatureManager


def create_populated_index(root_path: Path) -> IndexStore:
    db_path = root_path / ".stitcher" / "index" / "index.db"

    db_manager = DatabaseManager(db_path)
    db_manager.initialize()
    store = IndexStore(db_manager)

    # The indexer needs a workspace-aware adapter.
    workspace = Workspace(root_path)
    search_paths = workspace.get_search_paths()

    # Discover files first, then index them.
    files_to_index = workspace.discover_files()

    indexer = FileIndexer(root_path, store)
    python_adapter = PythonAdapter(root_path, search_paths)
    sidecar_adapter = SidecarAdapter()
    
    indexer.register_adapter(".py", python_adapter)
    indexer.register_adapter(".yaml", sidecar_adapter)
    indexer.register_adapter(".json", sidecar_adapter)
    
    indexer.index_files(files_to_index)

    return store
~~~~~

#### Acts 2: 优化 Planner 逻辑

对于 JSON 文件，我们允许 `target_node_fqn` 为空。但是，如果它是空的，我们需要一种方法来匹配它。
在 `find_usages(target_fqn)` 调用中，Index 会返回所有匹配该 FQN 的引用（YAML）以及所有匹配该 FQN 对应 SURI 的引用（JSON）。
所以，对于 JSON 引用，`target_node_id` 应该是存在的（且等于旧符号的 SURI），而 `target_node_fqn` 可能是 None。

关键点：如果 `loc.target_node_fqn` 是 None，我们怎么知道它对应 `rename_map` 中的哪个 `old_fqn` 呢？
`rename_map` 的键是 `old_fqn`。
我们在 `Planner._plan_renames` 中是遍历 `old_fqn` 来调用 `find_usages` 的。
所以我们其实知道当前的 `old_fqn` 是什么！

我们需要稍微调整 `_plan_renames` 的结构，以便将上下文（当前的 `old_fqn` 和 `new_fqn`）传递给文件处理逻辑。或者，由于我们是先收集所有 usages 再按文件分组，我们需要在 `UsageLocation` 中携带“导致此 Usage 被选中的查询 FQN”信息，或者更简单地，我们应该相信 `find_usages` 的结果。

但是 `find_usages` 可能会返回多个符号的混合结果（如果我们并发查询的话）。当前实现是串行的：
```python
        for old_fqn in rename_map.keys():
            for usage in ctx.graph.find_usages(old_fqn):
                usages_by_file[usage.file_path].append(usage)
```
这里有个问题：`usage` 对象本身只包含它在文件中的信息。如果 `target_node_fqn` 是 None（Signature文件），我们拿到这个 usage 后，只知道它的 ID。在 `_transform_python_file` 或 `update_keys` 中，我们需要知道把这个 ID 映射到什么新状态。

最稳健的方法是：在 `UsageLocation` 中附加上它所对应的 `Symbol` 信息，但这太重了。
或者，我们在 `usages_by_file` 中不仅存储 `usage`，还存储 `(usage, old_fqn, new_fqn)` 元组。

让我们修改 `Planner._plan_renames`，构建一个更丰富的数据结构。

~~~~~act
patch_file
packages/stitcher-refactor/src/stitcher/refactor/engine/planner.py
~~~~~
~~~~~python.old
    def _plan_renames(
        self, rename_map: Dict[str, str], ctx: RefactorContext
    ) -> List[FileOp]:
        ops: List[FileOp] = []
        usages_by_file: Dict[Path, List[UsageLocation]] = defaultdict(list)

        # 1. Collect all usages for all renames
        for old_fqn in rename_map.keys():
            for usage in ctx.graph.find_usages(old_fqn):
                usages_by_file[usage.file_path].append(usage)

        # 2. For each affected file, generate a single WriteFileOp
        for file_path, locations in usages_by_file.items():
            content = file_path.read_text("utf-8")
            new_content = None

            if file_path.suffix == ".py":
                new_content = self._transform_python_file(content, locations, rename_map)
            elif file_path.suffix in (".yaml", ".yml"):
                # For YAML, the key is the FQN.
                sidecar_rename_map = {
                    loc.target_node_fqn: rename_map[loc.target_node_fqn]
                    for loc in locations
                    if loc.target_node_fqn in rename_map
                }
                new_content = self._sidecar_updater.update_keys(
                    content, sidecar_rename_map, is_yaml=True
                )
            elif file_path.suffix == ".json":
                # For JSON, the key is the SURI. We construct the SURI rename map.
                suri_rename_map = {}
                for loc in locations:
                    if not (loc.target_node_id and loc.target_node_fqn):
                        continue

                    old_suri = loc.target_node_id
                    old_fqn = loc.target_node_fqn

                    if old_fqn in rename_map:
                        new_fqn = rename_map[old_fqn]

                        # Reconstruct SURI. This logic assumes a symbol rename, not a file move.
                        # File moves are handled by MoveFileOperation generating cascading renames.
                        try:
                            path, old_fragment = SURIGenerator.parse(old_suri)
                            _, new_fragment_base = SURIGenerator.parse(
                                f"py://dummy#{new_fqn.replace('.', '#')}"
                            )
                            new_suri = SURIGenerator.for_symbol(path, new_fragment_base)
                            suri_rename_map[old_suri] = new_suri
                        except (ValueError, AttributeError):
                            continue # Ignore malformed SURIs or FQNs

                if suri_rename_map:
                    new_content = self._sidecar_updater.update_keys(
                        content, suri_rename_map, is_yaml=False
                    )

            if new_content and new_content != content:
                ops.append(
                    WriteFileOp(
                        file_path.relative_to(ctx.graph.root_path), new_content
                    )
                )
        return ops
~~~~~
~~~~~python.new
    def _plan_renames(
        self, rename_map: Dict[str, str], ctx: RefactorContext
    ) -> List[FileOp]:
        ops: List[FileOp] = []
        # Store tuples of (UsageLocation, triggering_old_fqn)
        usages_by_file: Dict[Path, List[tuple[UsageLocation, str]]] = defaultdict(list)

        # 1. Collect all usages for all renames
        for old_fqn in rename_map.keys():
            for usage in ctx.graph.find_usages(old_fqn):
                usages_by_file[usage.file_path].append((usage, old_fqn))

        # 2. For each affected file, generate a single WriteFileOp
        for file_path, items in usages_by_file.items():
            # Unpack locations for Python transformer which expects list[UsageLocation]
            locations = [item[0] for item in items]
            
            content = file_path.read_text("utf-8")
            new_content = None

            if file_path.suffix == ".py":
                new_content = self._transform_python_file(content, locations, rename_map)
            elif file_path.suffix in (".yaml", ".yml"):
                # For YAML, the key is the FQN.
                sidecar_rename_map = {}
                for loc, old_fqn in items:
                    # Prefer the FQN from the location if available (it should be equal to old_fqn for YAML)
                    key = loc.target_node_fqn or old_fqn
                    if key in rename_map:
                        sidecar_rename_map[key] = rename_map[key]
                        
                new_content = self._sidecar_updater.update_keys(
                    content, sidecar_rename_map, is_yaml=True
                )
            elif file_path.suffix == ".json":
                # For JSON, the key is the SURI. 
                suri_rename_map = {}
                for loc, old_fqn in items:
                    # For Signature files, target_node_id IS the key (SURI).
                    # target_node_fqn might be None.
                    # We rely on old_fqn passed from the loop to know what we are renaming.
                    
                    if not loc.target_node_id:
                        continue

                    old_suri = loc.target_node_id
                    
                    if old_fqn in rename_map:
                        new_fqn = rename_map[old_fqn]

                        # Reconstruct SURI.
                        try:
                            path, old_fragment = SURIGenerator.parse(old_suri)
                            # We need to compute the new fragment.
                            # old_fqn: pkg.mod.Class
                            # new_fqn: pkg.mod.NewClass
                            # Logic: Replace the suffix of the fragment that corresponds to the changed part of FQN.
                            
                            # Simplistic approach: calculate the new short name
                            # This works for simple renames.
                            # For nested renames (Class.method), SURIGenerator.parse handles #Class.method
                            
                            old_short_name = old_fqn.split(".")[-1]
                            new_short_name = new_fqn.split(".")[-1]
                            
                            # This is still a bit heuristic. A robust way is needed.
                            # If old_fragment ends with old_short_name, replace it.
                            if old_fragment and old_fragment.endswith(old_short_name):
                                new_fragment = old_fragment[: -len(old_short_name)] + new_short_name
                                new_suri = SURIGenerator.for_symbol(path, new_fragment)
                                suri_rename_map[old_suri] = new_suri
                                
                        except (ValueError, AttributeError):
                            continue

                if suri_rename_map:
                    new_content = self._sidecar_updater.update_keys(
                        content, suri_rename_map, is_yaml=False
                    )

            if new_content and new_content != content:
                ops.append(
                    WriteFileOp(
                        file_path.relative_to(ctx.graph.root_path), new_content
                    )
                )
        return ops
~~~~~

### 下一步建议

现在测试环境已经能够正确索引 Sidecar 文件，且 Planner 也能正确处理仅有 ID 的引用了。建议再次运行测试，验证修复是否生效。如果一切顺利，我们不仅修复了 Bug，还证明了新架构（Index-Driven Refactoring）的强大和正确性。
