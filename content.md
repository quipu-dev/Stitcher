简要回答
测试成功复现了崩溃，错误堆栈非常清晰：`griffe._internal.exceptions.BuiltinModuleError: src.pkg.main`。

崩溃发生在我们调用 `griffe.visit` 时。关键原因是 Griffe 在处理相对导入 `from .models import User` 时，需要确定当前模块 `src.pkg.main` 是否是一个包（package），这依赖于检查其 `filepath` 是否为 `__init__.py`。然而，我们在 `griffe.visit` 中传递了 `filepath=None`，导致 Griffe 无法确定模块性质，从而在 `is_init_module` 属性访问时抛出异常。

为了解决这个问题，我们需要在调用 `griffe.visit` 时提供正确的 `filepath` 参数。

## [WIP] fix(adapter): 为 Griffe 分配 Filepath 以解决相对导入崩溃

### 错误分析
`griffe.visit` 在处理相对导入（`from . import ...`）时，必须知道当前模块在文件系统中的位置，以判断它是包 (`__init__.py`) 还是普通模块。
我们在 `GriffePythonParser.parse` 调用中：
`griffe.visit(module_name, filepath=None, code=source_code)`
显式传递了 `filepath=None`，剥夺了 Griffe 进行相对路径计算的能力，导致其内部抛出 `BuiltinModuleError`。

### 用户需求
修复 `GriffePythonParser`，使其能够处理包含相对导入的代码而不崩溃。

### 评论
虽然我们通过 `code` 参数传递了源代码内容，但文件路径对于上下文解析（尤其是相对导入）是必不可少的。我们需要将传入 `parse` 方法的 `file_path` 参数传递给 Griffe。

### 目标
修改 `packages/stitcher-python-adapter/src/stitcher/adapter/python/griffe_parser.py`，将 `file_path` 传递给 `griffe.visit`。

### 基本原理
提供 `filepath` 使 Griffe 能够正确执行 `relative_to_absolute` 逻辑，从而解决相对导入路径。

### 标签
#intent/fix #flow/ready #priority/high #comp/runtime #concept/parser #scope/core #ai/instruct
#task/domain/engine #task/object/griffe-parser #task/action/fix #task/state/continue

---

### Script

#### Acts 1: 修复 filepath 传递

我们将修改 `parse` 方法，将 `file_path` 参数（转换为 `Path` 对象）传递给 `griffe.visit`。

~~~~~act
patch_file
packages/stitcher-python-adapter/src/stitcher/adapter/python/griffe_parser.py
~~~~~
~~~~~python.old
import ast
import griffe
from typing import List, Optional, Any
~~~~~
~~~~~python.new
import ast
from pathlib import Path
import griffe
from typing import List, Optional, Any
~~~~~

~~~~~act
patch_file
packages/stitcher-python-adapter/src/stitcher/adapter/python/griffe_parser.py
~~~~~
~~~~~python.old
        # 2. Visit with Griffe
        module_name = file_path.replace("/", ".").replace(".py", "") or "module"
        griffe_module = griffe.visit(module_name, filepath=None, code=source_code)

        # 3. Map to Stitcher IR
        return self._map_module(griffe_module, file_path)
~~~~~
~~~~~python.new
        # 2. Visit with Griffe
        module_name = file_path.replace("/", ".").replace(".py", "") or "module"
        
        # Griffe needs a Path object for filepath to correctly handle relative imports
        path_obj = Path(file_path) if file_path else None
        
        griffe_module = griffe.visit(module_name, filepath=path_obj, code=source_code)

        # 3. Map to Stitcher IR
        return self._map_module(griffe_module, file_path)
~~~~~

### 下一步建议

修复应用后，应重新运行 `test_griffe_resolves_imports` 集成测试。
**注意**：这只是解决了 `Crash` 问题。`Could not resolve alias` 的警告可能仍然存在，因为简单的 `visit` 并没有加载整个项目上下文（即它不知道 `models` 模块的具体内容）。
如果集成测试通过且没有 crash，但注解是 `List` 而不是完整的类型，那也是一种进步。如果我们要彻底解决跨文件引用解析，可能需要从 `visit`（单文件）转向 `load`（多文件/项目级），但这会显著改变架构。目前的 MVP 目标是**不崩溃**并能提取基本信息。
