简要回答
好的，我们采用 Griffe 的核心别名解析机制来实现 `UsageRegistry`。

正如你所指出的，Griffe 的 `Alias` 对象已经完美封装了 Python 复杂的导入和名称解析逻辑（包括 `from ... import ... as ...`）。我们将利用这一点来构建“定义级”的引用图，并辅以轻量级的 AST 扫描来解决“函数体级”的引用，从而实现完整的 Find Usages 能力。

## [WIP] feat: 基于 Griffe Alias 实现 UsageRegistry

### 用户需求
利用 Griffe 成熟的别名解析（Alias Resolution）功能，实现 `UsageRegistry`，将代码中的引用位置（UsageLocation）与语义符号（FQN）关联起来。

### 评论
这是一个混合策略：
1.  **跨文件解析 (Resolution)**: 完全信任 Griffe。Griffe 告诉我们当前模块中的符号 `X` 其实是指向 `pkg.module.Y` 的 `Alias`。
2.  **函数体内定位 (Location)**: 由于 Griffe 不存储函数体内的 AST 节点位置，我们补充一个轻量级的 `ast.NodeVisitor`。当 Visitor 在函数体中遇到 `X` 时，它查询 Griffe 的解析结果，得知 `X -> pkg.module.Y`，从而将该位置注册为 `pkg.module.Y` 的一个 Usage。

### 目标
1.  在 `graph.py` 中实现 `UsageRegistry` 类，用于存储 `FQN -> List[UsageLocation]` 的倒排索引。
2.  在 `SemanticGraph` 中实现 `build_registry()`：
    *   遍历 Griffe 的 Module 成员，建立本地符号表（Local Symbol Table）。
    *   使用 `ast` 扫描源码，结合本地符号表，解析并记录所有 `Name` 节点的引用。
3.  编写集成测试，验证重构引擎能够识别通过 `import as` 引入的符号在函数体内的引用。

### 基本原理
-   **Griffe as Source of Truth**: Griffe 负责“通过导入路径找到真身”。
-   **AST as Locator**: AST 负责“找到代码里哪里用到了这个名字”。
-   **性能权衡**: 虽然需要再次 parse AST，但相比于自己实现一套完整的 Python 作用域和导入解析器，这是性价比最高的方案。

### 标签
#intent/build #flow/ready #priority/high #comp/runtime #task/domain/refactor #task/object/usage-registry #task/action/implementation #task/state/continue

---

### Script

#### Acts 1: 更新 SemanticGraph 与 UsageRegistry
我们将更新 `graph.py`，引入 `UsageRegistry` 并集成 AST 扫描逻辑。

~~~~~act
write_file
packages/stitcher-refactor/src/stitcher/refactor/engine/graph.py
~~~~~
~~~~~python
import ast
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Optional, Set, DefaultDict
from collections import defaultdict
import griffe


@dataclass
class UsageLocation:
    """
    Represents a specific usage of a symbol in the codebase.
    """
    file_path: Path
    lineno: int
    col_offset: int
    end_lineno: int
    end_col_offset: int
    
    @property
    def range_tuple(self):
        return (self.lineno, self.col_offset)


@dataclass
class SymbolNode:
    fqn: str
    kind: str
    path: Path


class UsageRegistry:
    def __init__(self):
        # Key: Target FQN (The "Real" Name, e.g., "pkg.mod.Class")
        # Value: List of locations where this symbol is used/referenced
        self._index: DefaultDict[str, List[UsageLocation]] = defaultdict(list)

    def register(self, target_fqn: str, location: UsageLocation):
        self._index[target_fqn].append(location)

    def get_usages(self, target_fqn: str) -> List[UsageLocation]:
        return self._index.get(target_fqn, [])


class _UsageVisitor(ast.NodeVisitor):
    """
    Scans a file's AST for Name nodes and resolves them using a local symbol table.
    """
    def __init__(self, file_path: Path, local_symbols: Dict[str, str], registry: UsageRegistry):
        self.file_path = file_path
        self.local_symbols = local_symbols  # map: local_name -> target_fqn
        self.registry = registry

    def visit_Name(self, node: ast.Name):
        # We only care about loading (reading) variables, not assigning them (defining)
        # Although for rename, we usually want to rename definitions too.
        # But definitions are handled by Griffe's iteration.
        # Here we mostly care about references inside functions/methods.
        # However, LibCST rename transformer will handle Name nodes regardless of ctx.
        # So we should record all occurrences that resolve to the target.
        
        target_fqn = self.local_symbols.get(node.id)
        if target_fqn:
            loc = UsageLocation(
                file_path=self.file_path,
                lineno=node.lineno,
                col_offset=node.col_offset,
                end_lineno=node.end_lineno if hasattr(node, "end_lineno") else node.lineno,
                end_col_offset=node.end_col_offset if hasattr(node, "end_col_offset") else node.col_offset + len(node.id)
            )
            self.registry.register(target_fqn, loc)


class SemanticGraph:
    def __init__(self, root_path: Path):
        self.root_path = root_path
        self._griffe_loader = griffe.GriffeLoader(search_paths=[self.root_path])
        self._modules: Dict[str, griffe.Module] = {}
        self.registry = UsageRegistry()

    def load(self, package_name: str, submodules: bool = True) -> None:
        # 1. Load with Griffe (resolves aliases)
        module = self._griffe_loader.load(package_name, submodules=submodules)
        self._modules[package_name] = module
        
        # 2. Resolve aliases to ensure we have full resolution
        self._griffe_loader.resolve_aliases()

        # 3. Build Usage Registry
        self._build_registry(module)

    def _build_registry(self, module: griffe.Module):
        """
        Walks the module tree, builds local symbol tables from Griffe Aliases,
        and scans AST for usages.
        """
        # We need to process each file in the package
        # Griffe stores the module structure. We can traverse it.
        
        # Collect all modules (files)
        modules_to_scan = []
        if module.filepath:
            modules_to_scan.append(module)
        
        for member in module.members.values():
            if isinstance(member, griffe.Module) and not member.is_alias:
                # Recursively add submodules
                # Note: This simple recursion might miss deeply nested ones if we don't walk properly
                # But Griffe's structure is a tree.
                # Let's use a helper walker if needed, or rely on Griffe's flatness if provided.
                # Griffe doesn't have a flat list of all submodules directly accessible easily
                # without walking.
                self._build_registry(member)

        # Process the current module
        if module.filepath:
            self._scan_module_usages(module)

    def _scan_module_usages(self, module: griffe.Module):
        # 1. Build Local Symbol Table (Name -> FQN)
        # This maps names available in this module's scope to their absolute FQNs.
        local_symbols: Dict[str, str] = {}
        
        for name, member in module.members.items():
            # If it's an Alias (from import), member.target_path is the FQN.
            if member.is_alias:
                # Resolve the target path.
                # Griffe's resolve_aliases() should have computed .target for us if possible,
                # or at least .target_path is available.
                try:
                    target_fqn = member.target_path
                    local_symbols[name] = target_fqn
                except Exception:
                    # If resolution failed or path unavailable
                    pass
            else:
                # It's a definition (Class, Function) in this module.
                # The name maps to the object's own path.
                local_symbols[name] = member.path

        # 2. Parse AST and scan
        try:
            source = module.filepath.read_text(encoding="utf-8")
            tree = ast.parse(source)
            visitor = _UsageVisitor(module.filepath, local_symbols, self.registry)
            visitor.visit(tree)
        except Exception:
            # Handle syntax errors or IO errors gracefully
            pass

    def get_module(self, package_name: str) -> Optional[griffe.Module]:
        return self._modules.get(package_name)

    def iter_members(self, package_name: str) -> List[SymbolNode]:
        # ... (Same as before) ...
        # For brevity, we keep the previous implementation or re-implement if wiped.
        # Re-implementing for safety since we are overwriting the file.
        module = self.get_module(package_name)
        if not module:
            return []
        nodes = []
        def _collect(obj: griffe.Object):
            path = obj.filepath if obj.filepath else Path("")
            kind = "unknown"
            if obj.is_module: kind = "module"
            elif obj.is_class: kind = "class"
            elif obj.is_function: kind = "function"
            elif obj.is_attribute: kind = "attribute"
            nodes.append(SymbolNode(fqn=obj.path, kind=kind, path=path))
            if hasattr(obj, "members"):
                for member in obj.members.values():
                    if not member.is_alias:
                        _collect(member)
        _collect(module)
        return nodes
~~~~~

#### Acts 2: 编写集成测试验证 UsageRegistry
创建一个测试，模拟一个包含跨文件引用的场景，验证 `UsageRegistry` 是否能正确找到引用。

~~~~~act
write_file
packages/stitcher-refactor/tests/integration/test_usage_registry.py
~~~~~
~~~~~python
from pathlib import Path
from stitcher.refactor.engine.graph import SemanticGraph, UsageLocation

def test_usage_registry_resolution(tmp_path):
    # Setup:
    # mypkg/
    #   __init__.py
    #   core.py -> defines `Helper`
    #   app.py  -> imports `Helper` as `H`, uses `H()`
    
    pkg_dir = tmp_path / "mypkg"
    pkg_dir.mkdir()
    (pkg_dir / "__init__.py").write_text("", encoding="utf-8")
    
    # core.py
    (pkg_dir / "core.py").write_text(
        "class Helper:\n    pass", 
        encoding="utf-8"
    )
    
    # app.py
    # We import Helper as H, then instantiate it.
    # The registry should map the usage of 'H' in app.py to 'mypkg.core.Helper'
    (pkg_dir / "app.py").write_text(
        "from mypkg.core import Helper as H\n\ndef main():\n    obj = H()", 
        encoding="utf-8"
    )
    
    # Execute
    graph = SemanticGraph(root_path=tmp_path)
    graph.load("mypkg")
    
    # Verify
    # We want to find usages of 'mypkg.core.Helper'
    usages = graph.registry.get_usages("mypkg.core.Helper")
    
    # Debug info
    print(f"Usages found: {usages}")
    
    # We expect usages in:
    # 1. app.py (the import statement "Helper as H" - handled by Griffe Alias scan?)
    #    Actually our _scan_module_usages scans Name nodes.
    #    The import statement creates the alias 'H'.
    #    The UsageVisitor sees 'H' in 'obj = H()' and resolves it to 'mypkg.core.Helper'.
    
    # Let's check if we caught the usage in `main`
    app_usage = next((u for u in usages if u.file_path.name == "app.py" and u.lineno == 4), None)
    
    assert app_usage is not None, "Failed to find usage of H() in app.py"
    assert app_usage.col_offset == 10  # "    obj = H()" -> H starts at index 10
    
    # Also, we implicitly registered the definition in core.py? 
    # _scan_module_usages registers local definitions too.
    # So 'class Helper' in core.py should also be a usage of 'mypkg.core.Helper' (definition is a usage)
    core_usage = next((u for u in usages if u.file_path.name == "core.py"), None)
    assert core_usage is not None
~~~~~

### 下一步建议
有了 `UsageRegistry` 和 `SymbolRenamerTransformer`，我们现在拥有了完整的“搜索”和“替换”能力。
下一步是将它们组合成 `RenameSymbolOperation` 类：
1.  **输入**: 用户指定旧 FQN 和新 FQN。
2.  **分析**: 使用 `SemanticGraph` 找到旧 FQN 的所有 Usages。
3.  **转换**: 为每个涉及的文件生成 `SymbolRenamerTransformer`。
4.  **执行**: 调用 `TransactionManager` 应用变更。
