简要回答
你对错误的分析完全正确。失败的根源在于我试图用一个简单的 CST Visitor 去重新实现 Griffe 已经完美解决的复杂别名解析问题。这是一个典型的重复造轮子并引入 bug 的案例。

正确的做法是彻底信任 Griffe。Griffe 在 `resolve_aliases()` 之后，已经将每个 `Alias` 对象链接到了它的最终 `target`。我们只需要遍历这个已经解析完毕的图谱，就能构建出一个权威的、无需二次解析的 `UsageRegistry`。

我将重写 `SemanticGraph` 的注册表构建逻辑，抛弃手动 CST 扫描，改为直接消费 Griffe 的解析结果。

## [WIP] fix(refactor): 重构 UsageRegistry 构建逻辑以完全依赖 Griffe 解析

### 错误分析
-   **现象**: `test_rename_transformer_advanced` 中的两个测试用例均断言失败，只检测到了定义文件的变更，而错过了引用文件的变更。
-   **原因**: `_UsageVisitor` 的实现过于简单，它仅基于顶层 `local_symbols` 进行查找，无法处理 `a.b.c` 这样的属性链访问，也无法处理 `from ... import a as b` 中的原始名称 `a`。
-   **根本原因**: 我们没有充分利用 Griffe 的能力。在 `resolve_aliases()` 之后，Griffe 已经构建了一个完整的引用图。我们应该直接查询这个图，而不是用一个不完整的 CST Visitor 去重复解析。

### 用户需求
修复 `SemanticGraph` 使其能正确识别通过属性访问（`Attribute`）和导入别名（`ImportAlias`）的符号引用。

### 评论
这是一个重要的架构修正。它将 `SemanticGraph` 的职责从“半分析半组装”调整为纯粹的“组装”。`SemanticGraph` 的任务是**翻译** Griffe 的富语义模型到 Stitcher 自己的 `UsageLocation` 模型，而不是**重新实现** Griffe 的分析逻辑。这使得我们的代码更简洁、更可靠，并能更好地利用 Griffe 未来的改进。

### 目标
1.  重构 `packages/stitcher-refactor/src/stitcher/refactor/engine/graph.py`。
2.  移除 `_UsageVisitor` 和所有基于手动 CST 扫描的逻辑。
3.  在 `_build_registry` 中，实现一个新的遍历器，它能：
    *   递归地访问 Griffe Module 和 Class 的所有成员。
    *   当遇到一个 `Alias` 时，跟随它的 `target` 链接找到最终定义的 FQN。
    *   将 `Alias` 自身的位置信息（`lineno`, `col_offset`）注册为 `target` FQN 的一个 `UsageLocation`。
    *   将定义本身也注册为一个 `UsageLocation`。

### 基本原理
-   **消费而非生产**: 新的 `_build_registry` 不再尝试*生产*语义信息，而是纯粹地*消费* Griffe 已经提供的权威语义信息。
-   **Alias as Bridge**: Griffe 的 `Alias` 对象是连接“引用点”和“定义点”的桥梁。我们只需遍历这些桥梁，就能构建出完整的引用图。

### 标签
#intent/refine #flow/ready #priority/high #comp/runtime #task/domain/refactor #task/object/usage-registry #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 重构 graph.py 以直接使用 Griffe Alias
我们将彻底重写 `_build_registry` 方法。

~~~~~act
write_file
packages/stitcher-refactor/src/stitcher/refactor/engine/graph.py
~~~~~
~~~~~python
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Optional, DefaultDict
from collections import defaultdict
import griffe


@dataclass(unsafe_hash=True)
class UsageLocation:
    """
    Represents a specific usage of a symbol in the codebase.
    """
    file_path: Path = field(hash=True)
    lineno: int = field(hash=True)
    col_offset: int = field(hash=True)
    end_lineno: int = field(hash=True)
    end_col_offset: int = field(hash=True)


@dataclass
class SymbolNode:
    fqn: str
    kind: str
    path: Path


class UsageRegistry:
    def __init__(self):
        self._index: DefaultDict[str, set[UsageLocation]] = defaultdict(set)

    def register(self, target_fqn: str, location: UsageLocation):
        self._index[target_fqn].add(location)

    def get_usages(self, target_fqn: str) -> List[UsageLocation]:
        return sorted(list(self._index.get(target_fqn, set())), key=lambda loc: (loc.file_path, loc.lineno, loc.col_offset))


class SemanticGraph:
    def __init__(self, root_path: Path):
        self.root_path = root_path
        self._griffe_loader = griffe.GriffeLoader(search_paths=[str(self.root_path)])
        self._modules: Dict[str, griffe.Module] = {}
        self.registry = UsageRegistry()

    def load(self, package_name: str, submodules: bool = True) -> None:
        module = self._griffe_loader.load(package_name, submodules=submodules)
        self._modules[package_name] = module
        self._griffe_loader.resolve_aliases()
        self._build_registry()

    def _build_registry(self):
        """
        Builds the usage registry by traversing Griffe's fully resolved object tree.
        """
        self.registry = UsageRegistry() # Reset registry
        
        for module in self._griffe_loader.modules_collection.values():
            for obj in module.iterate(aliases=True):
                location = None
                if obj.filepath and obj.lineno:
                    # Griffe's end_lineno/col can be None, provide fallbacks
                    end_lineno = obj.end_lineno or obj.lineno
                    end_col_offset = obj.end_col_offset or (obj.col_offset + len(obj.name))

                    location = UsageLocation(
                        file_path=obj.filepath,
                        lineno=obj.lineno,
                        col_offset=obj.col_offset,
                        end_lineno=end_lineno,
                        end_col_offset=end_col_offset,
                    )

                if location:
                    target_fqn = ""
                    if obj.is_alias:
                        try:
                            # Follow the alias to its final target
                            target_obj = obj.target
                            if target_obj:
                                target_fqn = target_obj.path
                        except griffe.AliasResolutionError:
                            # If resolution failed, we can't register it
                            continue
                    else:
                        # It's a definition, it refers to itself
                        target_fqn = obj.path

                    if target_fqn:
                        self.registry.register(target_fqn, location)


    def get_module(self, package_name: str) -> Optional[griffe.Module]:
        return self._modules.get(package_name)

    def iter_members(self, package_name: str) -> List[SymbolNode]:
        module = self.get_module(package_name)
        if not module: return []
        nodes = []
        # Simplified iterator for now
        for obj in module.iterate():
            if not obj.is_alias:
                nodes.append(SymbolNode(
                    fqn=obj.path,
                    kind=obj.kind.value,
                    path=obj.filepath
                ))
        return nodes
~~~~~

### 下一步建议
这次重构是根本性的。它用一个更可靠、更简洁的实现取代了之前脆弱的 CST 扫描逻辑。

现在，我们应该重新运行 `test_rename_transformer_advanced.py`。如果这次重构是正确的，之前失败的测试现在应该会通过，因为 `SemanticGraph` 将能够正确地识别出 `Attribute` 和 `ImportAlias` 中的引用位置。

测试通过后，我们将最终确认 `RenameSymbolOperation` 的健壮性，并可以自信地进入 `MoveFileOperation` 的实现阶段。
