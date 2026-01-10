You are absolutely correct. My apologies again. This `ImportError` is a clear and direct consequence of my incomplete cleanup. I removed the export from `stitcher-python-adapter/__init__.py`, but I failed to remove all the corresponding import statements that depended on it.

The file `stitcher-test-utils/helpers.py` is the last remaining place with this dangling import. Thank you for your diligence in running the tests and finding this final loose end.

I will now create a plan to fix it.

## [WIP] fix(tests): Remove final dangling import from test utils

### 错误分析

测试套件在收集阶段因 `ImportError` 而崩溃。根本原因是在 `packages/stitcher-test-utils/src/stitcher/test_utils/helpers.py` 文件中，依然存在一个对 `PythonStubGenerator` 的悬空导入。

在之前的修复计划中，我清除了 `stitcher-python-adapter` 中对 `PythonStubGenerator` 的导出，并修复了 `stitcher-cli` 和其他几个测试工具文件中的导入。然而，我**遗漏了** `helpers.py` 这个文件。

因此，当测试框架尝试加载依赖于 `helpers.py` 的测试模块时，Python 解释器无法从 `stitcher.adapter.python` 中找到 `PythonStubGenerator`，从而导致了致命的 `ImportError`。

### 用户需求

修复 `stitcher-test-utils/helpers.py` 中的悬空导入，使测试套件能够成功收集并运行。

### 评论

这是我们大规模重构任务中最后一块需要修补的碎片。测试套件再次扮演了至关重要的“看门人”角色，确保了没有悬空的引用被遗留在代码库中。完成这个修复后，我们的代码结构将达到完全的内部一致性。

### 目标

1.  定位 `packages/stitcher-test-utils/src/stitcher/test_utils/helpers.py` 文件。
2.  移除其中对 `PythonStubGenerator` 的无用导入语句。

### 基本原理

我们将使用一个精确的 `patch_file` 操作来清理这个最后的悬空导入。`old_str` 将会匹配包含 `PythonStubGenerator` 的整个 `from stitcher.adapter.python import (...)` 块。`new_str` 将是移除了 `PythonStubGenerator` 后的版本。这是一个简单、直接且能彻底解决问题的修复。

### 标签

#intent/fix #flow/ready #priority/critical #comp/tests #scope/dx #task/domain/architecture #task/object/stubgen-package #task/action/cleanup #task/state/continue

---

### Script

#### Acts 1: 移除 `test_utils/helpers.py` 中的悬空导入

我们将清理 `helpers.py` 中对 `PythonStubGenerator` 的无用导入。

~~~~~act
patch_file
packages/stitcher-test-utils/src/stitcher/test_utils/helpers.py
~~~~~
~~~~~python
from stitcher.adapter.python import (
    PythonParser,
    PythonTransformer,
    PythonStubGenerator,
    PythonFingerprintStrategy,
)
~~~~~
~~~~~python
from stitcher.adapter.python import (
    PythonParser,
    PythonTransformer,
    PythonFingerprintStrategy,
)
~~~~~

### 下一步建议

这个修复应该能够解决最后的 `ImportError`，让我们的测试套件完全通过。

一旦测试全部变绿，我们的 `stitcher-stubgen` 架构重构任务就真正地、彻底地完成了。届时，我强烈建议你创建一个 `[COMMIT]` 计划，将整个重构过程（从创建新包到最后的清理和所有修复）作为一个原子提交，为项目留下清晰、完整的演进历史。
