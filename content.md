好的，您是对的，我之前的修复是错误的。

非常抱歉，我错误地认为 `GriffeLoader` 的构造函数接受一个 `sys_path` 参数，但实际上它的 API 并非如此，这导致了新的 `TypeError`。感谢您的指正。

问题的根源仍然是测试环境的 `sys.path` 泄漏到了我们的分析引擎中。既然不能通过构造函数参数来隔离，我们就必须采用更标准的 Python 测试方法：**在分析期间，临时、安全地修改 `sys.path`**。

我会生成一个新的计划，这次使用 `try...finally` 结构来确保 `sys.path` 只在分析代码时被修改，之后无论成功还是失败，都会被恢复原状。这才是解决这类问题的正确且健壮的方式。

## [WIP] fix(refactor): 通过临时修改 sys.path 实现测试隔离

### 错误分析

我上一次的修复尝试向 `griffe.GriffeLoader` 传递一个 `sys_path` 关键字参数，但这导致了 `TypeError`，因为该类的构造函数不支持此参数。

根本问题依然存在：`pytest` 运行器所设置的全局 `sys.path` 包含了整个开发工作区，这污染了 `griffe` 分析引擎的模块搜索路径，破坏了测试的隔离性。

### 用户需求

用户需要修复 `test_refactor_command.py` 中因 `TypeError` 导致的测试失败，并最终解决测试环境泄漏的根源问题。

### 评论

这是一个更严谨、更符合 Python 测试实践的修复方案。通过在执行关键操作时临时修改全局状态（如 `sys.path`），并在操作结束后无论如何都恢复它，我们能确保测试的可靠性和隔离性，同时不会对测试运行器的其他部分产生副作用。

### 目标

1.  定位到 `stitcher-refactor` 包中的 `SemanticGraph.load` 方法。
2.  在该方法内部，使用一个 `try...finally` 块来包裹 `self._griffe_loader.load(...)` 的调用。
3.  在 `try` 块之前，将 `sys.path` 备份并替换为仅包含当前项目搜索路径 (`self.search_paths`) 的列表。
4.  在 `finally` 块中，无论分析成功与否，都将 `sys.path` 恢复到其原始状态。

### 基本原理

Python 的 `sys.path` 是一个可变的全局列表，模块导入机制会遍历它来查找模块。在测试中，最安全的隔离方法不是去寻找特定库的配置项，而是直接控制这个列表。通过 `original = sys.path[:]` 创建一个副本，然后在 `try` 块中用一个受控的列表替换 `sys.path`，可以强制所有导入操作都发生在这个受控的环境中。`finally` 块则保证了即使 `try` 块中发生异常，`sys.path = original` 依然会被执行，从而避免了对后续测试或其他操作的污染。

### 标签

#intent/fix #flow/ready #priority/high #comp/engine #comp/tests #concept/state #ai/instruct #task/domain/testing #task/object/environment-isolation #task/action/bug-fix #task/state/continue

---

### Script

#### Acts 1: 实现安全的 sys.path 临时修改

我将修改 `graph.py` 文件，首先在文件顶部导入 `sys` 模块，然后在 `load` 方法中实现 `try...finally` 逻辑来安全地隔离 `sys.path`。

~~~~~act
patch_file
packages/stitcher-refactor/src/stitcher/refactor/engine/graph.py
~~~~~
~~~~~python.old
import libcst as cst
from libcst import helpers
from libcst.metadata import PositionProvider
~~~~~
~~~~~python.new
import sys
import libcst as cst
from libcst import helpers
from libcst.metadata import PositionProvider
~~~~~

~~~~~act
patch_file
packages/stitcher-refactor/src/stitcher/refactor/engine/graph.py
~~~~~
~~~~~python.old
    def load(self, package_name: str, submodules: bool = True) -> None:
        # 1. Load with Griffe (resolves aliases)
        module = self._griffe_loader.load(package_name, submodules=submodules)
        self._modules[package_name] = module

        # 2. Resolve aliases to ensure we have full resolution
        self._griffe_loader.resolve_aliases()

        # 3. Build Usage Registry
        self._build_registry(module)
~~~~~
~~~~~python.new
    def load(self, package_name: str, submodules: bool = True) -> None:
        # Temporarily modify sys.path to isolate griffe's discovery
        original_sys_path = sys.path[:]
        # sys.path requires strings, not Path objects
        sys.path = [str(p) for p in self.search_paths]
        try:
            # 1. Load with Griffe (resolves aliases)
            module = self._griffe_loader.load(package_name, submodules=submodules)
        finally:
            # Always restore the original sys.path
            sys.path = original_sys_path

        self._modules[package_name] = module

        # 2. Resolve aliases to ensure we have full resolution
        self._griffe_loader.resolve_aliases()

        # 3. Build Usage Registry
        self._build_registry(module)
~~~~~

### 下一步建议

这次的修复方案更加稳妥。请再次运行测试。如果测试通过，我们就可以将这些修改固化为一个 `[COMMIT]` 计划了。
