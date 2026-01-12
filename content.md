You are absolutely right. I missed a crucial step after restructuring `pump` into a sub-package. My `touch` command created an empty `__init__.py`, which fails to expose the `PumpRunner` class, leading to the `ImportError`.

I will now fix this oversight.

## [WIP] fix: Expose PumpRunner from its new sub-package

### 错误分析
The refactoring in the previous step correctly moved `pump.py` to `pump/runner.py` and created a `pump` sub-package. However, the newly created `packages/stitcher-application/src/stitcher/app/runners/pump/__init__.py` was left empty. An empty `__init__.py` does not expose any of the sub-package's internal modules or classes, causing the import statement `from .pump import PumpRunner` in `runners/__init__.py` to fail.

### 用户需求
The user needs to fix the `ImportError` caused by the incomplete package restructuring, so that `PumpRunner` can be correctly imported by the rest of the application.

### 评论
This is a straightforward fix for a common oversight when converting a module into a package. By explicitly importing the main class in the package's `__init__.py`, we define its public API and make the refactoring complete and correct.

### 目标
1.  Edit `packages/stitcher-application/src/stitcher/app/runners/pump/__init__.py`.
2.  Add `from .runner import PumpRunner` to correctly expose the class at the package level.

### 基本原理
In Python, for a symbol inside a sub-module (e.g., `runner.py`) to be accessible directly from the package level (e.g., `from .. import pump`), it must be imported into the package's `__init__.py` file. This file defines the package's namespace.

### 标签
#intent/fix #flow/ready #priority/critical #comp/runtime #scope/core #ai/instruct #task/domain/architecture #task/object/dependency-injection #task/action/bug-fix #task/state/continue

---

### Script

#### Acts 1: Expose PumpRunner in the sub-package's `__init__.py`

I will add the necessary import statement to the previously empty `__init__.py` file.

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/runners/pump/__init__.py
~~~~~
~~~~~python.old
~~~~~
~~~~~python.new
from .runner import PumpRunner

__all__ = ["PumpRunner"]
~~~~~

### 下一步建议
With this fix, the `PumpRunner` refactoring is now complete. The application should build and type-check correctly. We can now proceed with applying the same dependency injection pattern to the remaining runners or move on to **“阶段四：Refactor 引擎泛化”**.
