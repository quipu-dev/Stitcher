## [WIP] fix: 增强 SemanticGraph 鲁棒性以支持扫描非规范包结构中的文件

### 错误分析
在 `test_debug_rename_failure_analysis` 中，重命名操作失败是因为目标文件 `bus.py` 位于一个缺少 `__init__.py` 的目录 (`stitcher/common/messaging`) 中。
1.  Python 导入规则规定：如果父包 (`stitcher.common`) 是常规包，子目录必须有 `__init__.py` 才能被视为子包。
2.  Griffe 严格遵循此规则，因此在扫描时忽略了 `messaging` 目录及其内容。
3.  因此，`SemanticGraph` 未能加载 `bus.py`，`class MessageBus` 的定义也就没有被注册到 `UsageRegistry` 中，导致重命名操作无法找到该定义。

虽然这源于项目结构的不规范，但重构工具应当具有更强的鲁棒性，能够处理处于“中间状态”或“破损状态”的代码库。

### 用户需求
修改 `SemanticGraph` 的加载逻辑，使其不再仅仅依赖 Griffe 的标准导入发现机制，而是主动扫描工作区中的所有源文件。对于那些被 Griffe 忽略的“孤儿文件”（如位于非包目录下的 .py 文件），应通过文件系统遍历进行发现，并手动触发 CST 扫描，以确保其中的符号定义（如类、函数）能被正确索引。

### 评论
这是一种“Design for Failure”的策略。通过实施主动扫描，即使在项目结构不完美的情况下，Stitcher 也能提供基本的重构能力（至少能找到并重命名定义），而不是默默失败。

### 目标
1.  修改 `packages/stitcher-refactor/src/stitcher/refactor/engine/graph.py`。
2.  在 `SemanticGraph` 中引入 `_processed_files` 集合，用于跟踪已由 Griffe 处理的文件。
3.  提取 CST 扫描逻辑到独立的 `_scan_file` 方法。
4.  实现 `_scan_orphans` 方法，遍历源目录查找未处理的 `.py` 文件，推断其 FQN，并进行补漏扫描。
5.  在 `load` 方法及其递归逻辑完成后，调用 `_scan_orphans`。

### 基本原理
我们利用 `Workspace` 已经掌握的“源目录根路径”信息。在 Griffe 完成标准的、基于导入的扫描后，我们遍历这些根路径下的所有 `.py` 文件。如果发现某个文件没有被 Griffe 处理过（即不在 `_processed_files` 中），我们就认为它是“孤儿文件”。我们根据文件路径相对于源根的路径推断出它的逻辑 FQN，然后手动对其进行 CST 解析。虽然对于孤儿文件我们可能缺乏完整的符号表（无法解析复杂的引用），但我们足以识别出 `ClassDef` 和 `FunctionDef`，这足以解决当前的重命名 Bug。

### 标签
#intent/fix #flow/ready #priority/high #comp/engine #concept/history #scope/core #ai/instruct #task/domain/refactoring #task/object/semantic-graph #task/action/enhance-robustness #task/state/continue

---

### Script

#### Acts 1: 重构 SemanticGraph 以支持孤儿文件扫描

我们将对 `SemanticGraph` 进行较大规模的修改：
1.  在 `__init__` 中初始化 `_processed_files`。
2.  将 `_scan_module_usages` 中的 CST 逻辑提取到 `_scan_file`。
3.  在 `_scan_module_usages` 中记录已处理的文件。
4.  添加 `_scan_orphans` 方法来查找并处理漏网之鱼。
5.  在 `load` 中调用它。

~~~~~act
patch_file
packages/stitcher-refactor/src/stitcher/refactor/engine/graph.py
~~~~~
~~~~~python.old
class SemanticGraph:
    def __init__(self, workspace: Workspace):
        self.workspace = workspace
        self.root_path = workspace.root_path
        self.search_paths = self.workspace.get_search_paths()
        self._griffe_loader = griffe.GriffeLoader(search_paths=self.search_paths)
        self._modules: Dict[str, griffe.Module] = {}
        self.registry = UsageRegistry()

    def load(self, package_name: str, submodules: bool = True) -> None:
        module = self._griffe_loader.load(package_name, submodules=submodules)
        self._modules[package_name] = module
        self._griffe_loader.resolve_aliases()
        self._build_registry(module)

    def _build_registry(
        self, module: griffe.Module, visited: Optional[Set[str]] = None
    ):
        if visited is None:
            visited = set()

        if module.path in visited:
            return
        visited.add(module.path)

        for member in module.members.values():
            if isinstance(member, griffe.Module):
                self._build_registry(member, visited)
        if module.filepath:
            self._scan_module_usages(module)

    def _scan_module_usages(self, module: griffe.Module):
        local_symbols: Dict[str, str] = {}
        for name, member in module.members.items():
            try:
                target_fqn = member.target_path if member.is_alias else member.path
                local_symbols[name] = target_fqn
            except Exception:
                pass

        try:
            source = module.filepath.read_text(encoding="utf-8")
            wrapper = cst.MetadataWrapper(cst.parse_module(source))
            is_init = module.filepath.name == "__init__.py"
            visitor = _UsageVisitor(
                module.filepath,
                local_symbols,
                self.registry,
                current_module_fqn=module.path,
                is_init_file=is_init,
            )
            wrapper.visit(visitor)
        except Exception:
            pass

    def get_module(self, package_name: str) -> Optional[griffe.Module]:
~~~~~
~~~~~python.new
class SemanticGraph:
    def __init__(self, workspace: Workspace):
        self.workspace = workspace
        self.root_path = workspace.root_path
        self.search_paths = self.workspace.get_search_paths()
        self._griffe_loader = griffe.GriffeLoader(search_paths=self.search_paths)
        self._modules: Dict[str, griffe.Module] = {}
        self.registry = UsageRegistry()
        self._processed_files: Set[Path] = set()

    def load(self, package_name: str, submodules: bool = True) -> None:
        module = self._griffe_loader.load(package_name, submodules=submodules)
        self._modules[package_name] = module
        self._griffe_loader.resolve_aliases()
        self._build_registry(module)
        self._scan_orphans(package_name)

    def _build_registry(self, module: griffe.Module):
        for member in module.members.values():
            if isinstance(member, griffe.Module) and not member.is_alias:
                self._build_registry(member)
        if module.filepath:
            self._scan_module_usages(module)

    def _scan_module_usages(self, module: griffe.Module):
        if module.filepath in self._processed_files:
            return
        
        local_symbols: Dict[str, str] = {}
        for name, member in module.members.items():
            try:
                target_fqn = member.target_path if member.is_alias else member.path
                local_symbols[name] = target_fqn
            except Exception:
                pass
        
        self._scan_file(
            module.filepath, 
            module.path, 
            module.filepath.name == "__init__.py", 
            local_symbols
        )

    def _scan_file(
        self, 
        path: Path, 
        fqn: str, 
        is_init: bool, 
        local_symbols: Optional[Dict[str, str]] = None
    ):
        try:
            self._processed_files.add(path)
            source = path.read_text(encoding="utf-8")
            wrapper = cst.MetadataWrapper(cst.parse_module(source))
            visitor = _UsageVisitor(
                path,
                local_symbols or {},
                self.registry,
                current_module_fqn=fqn,
                is_init_file=is_init,
            )
            wrapper.visit(visitor)
        except Exception:
            pass

    def _scan_orphans(self, package_name: str):
        # Active scan for files missed by Griffe (e.g. inside directories missing __init__.py)
        source_dirs = self.workspace.import_to_source_dirs.get(package_name, set())
        
        # Also check if package_name is actually a sub-package. 
        # import_to_source_dirs only indexes top-level packages.
        # If we loaded a sub-package, we might need to search in all source dirs.
        # For simplicity/robustness, we search all known source dirs in the workspace
        # that match the loaded package.
        
        target_roots = []
        if package_name in self.workspace.import_to_source_dirs:
            target_roots = self.workspace.import_to_source_dirs[package_name]
        else:
            # Fallback: search all roots, filter by package name prefix later?
            # Or just rely on the fact that load() is usually called with top-level pkg.
            # Let's start with the direct lookup.
            pass

        for root in target_roots:
            for py_file in root.rglob("*.py"):
                if py_file in self._processed_files:
                    continue
                
                # Infer FQN
                try:
                    rel_path = py_file.relative_to(root)
                    parts = list(rel_path.with_suffix("").parts)
                    if parts[-1] == "__init__":
                        parts.pop()
                    
                    inferred_fqn = ".".join(parts)
                    
                    # Only process if it matches the package we are loading
                    # This prevents scanning unrelated files if multiple pkgs share a root (rare but possible)
                    if inferred_fqn == package_name or inferred_fqn.startswith(package_name + "."):
                         self._scan_file(
                            py_file, 
                            inferred_fqn, 
                            py_file.name == "__init__.py", 
                            local_symbols={} # No local symbols for orphans
                        )
                except ValueError:
                    continue

    def get_module(self, package_name: str) -> Optional[griffe.Module]:
~~~~~

### 下一步建议
运行测试 `test_debug_rename_failure_analysis` 验证修复效果。如果成功，引擎现在不仅能处理规范的包结构，也能在缺失 `__init__.py` 的情况下正确索引和重命名符号定义。
