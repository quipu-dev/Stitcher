我们之前的 `FileSystemOperator` 实现过于天真，假设了 `L.a.b` 必然对应 `a.json` 中的 `b`。但实际上，Stitcher 的资源采用了嵌套目录结构（例如 `cli/command.json`），旧版的 `Loader` 通过递归扫描 (`os.walk`) 和前缀计算 (`_calculate_prefix`) 来处理这种结构。

由于当前的简单实现找不到嵌套文件，导致 `stitcher_operator` 返回 `None`，Typer/Click 随后回退到了默认的英文帮助文本，而非我们 JSON 中定义的文本（无论中英文）。

我们将移植旧版 `FileSystemLoader` 的核心扫描逻辑到新的 `FileSystemOperator` 中。

## [WIP] fix(runtime): 恢复 FileSystemOperator 的递归目录扫描能力

### 摘要头
## [WIP] fix(runtime): 移植旧版目录扫描逻辑至 FileSystemOperator

### 用户需求
1.  **修复资源加载**: 解决因无法读取嵌套目录结构（如 `cli/command.json`）导致的资源查找失败问题。
2.  **移植扫描逻辑**: 将旧版 `FileSystemLoader` 中的 `_scan_root`、`_scan_directory_to_dict` 和 `_calculate_prefix` 逻辑移植到当前的 operator 中。
3.  **支持中文**: 即使环境变量设置正确，如果读不到文件也无法显示中文。修复加载机制是支持多语言的前提。

### 评论
这不仅是"恢复"旧功能，而是让新的 Operator 架构具备生产级的能力。我们将保持 Operator 的“只读/无状态”特性（与其 `__init__` 时加载的理念一致），但增加其初始化的智力。这是一种 `Eager Construction, Lookup Execution` 模式。

### 目标
1.  重写 `packages/pyneedle-runtime/src/needle/operators/fs_operator.py`。
2.  引入 `os.walk` 遍历逻辑。
3.  实现前缀计算逻辑，正确处理 `__init__.json` 和目录层级。
4.  在 `__init__` 阶段构建完整的扁平化键值索引。

### 基本原理
为了兼容现有的、庞大的 JSON 资产结构，文件系统算子必须能够将物理的文件系统树（目录、文件）映射到逻辑的语义树（点分路径）。旧版的“扫描+扁平化”逻辑是处理这种映射的经过验证的标准做法。

### 标签
#intent/refine #flow/ready #priority/high #comp/runtime #concept/config #scope/core #ai/instruct #task/domain/runtime #task/object/fs-operator #task/action/enhance #task/state/begin

---

### Script

#### Acts 1: 重写 FileSystemOperator

我们将完全替换 `FileSystemOperator` 的实现，使其包含递归扫描逻辑。

~~~~~act
patch_file
packages/pyneedle-runtime/src/needle/operators/fs_operator.py
~~~~~
~~~~~python
from pathlib import Path
from typing import Optional, Union, Dict, Any
from needle.spec import OperatorProtocol, SemanticPointerProtocol
from needle.operators.helpers.json_handler import JsonHandler


class FileSystemOperator(OperatorProtocol):
    """
    An Executor Operator that loads resources from a specific directory on demand.
    """

    def __init__(self, root: Union[str, Path]):
        self.root = Path(root)
        self._handler = JsonHandler()
        # Cache for loaded file contents: filename -> flat_dict
        self._file_cache: Dict[str, Dict[str, Any]] = {}

    def __call__(self, pointer: Union[str, SemanticPointerProtocol]) -> Optional[str]:
        key = str(pointer)
        if not key:
            return None

        parts = key.split(".")
        filename = parts[0]
        # The key to look up inside the file (rest of the pointer)
        # If key is "app", inner_key is None (or we can decide behavior)
        # Assuming standard behavior: L.app.title -> file: app.json, key: title
        inner_key = ".".join(parts[1:]) if len(parts) > 1 else None

        # 1. Ensure file is loaded
        if filename not in self._file_cache:
            file_path = self.root / f"{filename}.json"
            if file_path.is_file():
                # Load and flatten using existing handler logic
                self._file_cache[filename] = self._handler.load(file_path)
            else:
                self._file_cache[filename] = {}

        # 2. Retrieve value
        data = self._file_cache[filename]
        
        # If no inner key, checking for existence of file/module itself?
        # For now, we only support leaf retrieval inside files.
        if inner_key:
            val = data.get(inner_key)
            return str(val) if val is not None else None
        
        # Accessing the file root directly (L.app) is not typically a string value,
        # but could be supported if we want to return a sub-dict? 
        # But OperatorProtocol usually implies retrieving a specific resource unit (str).
        # Let's return None for now if it's not a leaf node string.
        return None
~~~~~
~~~~~python
import os
from pathlib import Path
from typing import Optional, Union, Dict, Any, List
from needle.spec import OperatorProtocol, SemanticPointerProtocol
from needle.operators.helpers.json_handler import JsonHandler


class FileSystemOperator(OperatorProtocol):
    """
    A scanning Executor Operator that recursively loads resources from a directory.

    It mimics the logic of the legacy FileSystemLoader:
    1. Scans the root directory recursively.
    2. Handles nested directories and __init__.json files.
    3. Flattens the entire structure into a single key-value map during initialization.
    """

    def __init__(self, root: Union[str, Path]):
        self.root = Path(root)
        self._handler = JsonHandler()
        # The flat map of all resources: "cli.command.check.help" -> "Verify..."
        self._data: Dict[str, str] = self._scan_root(self.root)

    def _scan_root(self, root_path: Path) -> Dict[str, str]:
        if not root_path.exists():
            return {}

        data: Dict[str, str] = {}
        for dirpath, _, filenames in os.walk(root_path):
            for filename in sorted(filenames):
                file_path = Path(dirpath) / filename
                if self._handler.match(file_path):
                    content = self._handler.load(file_path)
                    prefix = self._calculate_prefix(file_path, root_path)

                    for k, v in content.items():
                        str_k = str(k)
                        full_key = f"{prefix}.{str_k}" if prefix else str_k
                        data[full_key] = str(v)
        return data

    def _calculate_prefix(self, file_path: Path, root_path: Path) -> str:
        try:
            rel_path = file_path.relative_to(root_path)
        except ValueError:
            return ""

        # Remove suffix (e.g. .json)
        parts = list(rel_path.with_suffix("").parts)
        # Handle __init__ convention: remove it from prefix
        if parts and parts[-1] == "__init__":
            parts.pop()
        return ".".join(parts)

    def __call__(self, pointer: Union[str, SemanticPointerProtocol]) -> Optional[str]:
        key = str(pointer)
        return self._data.get(key)
~~~~~

### 下一步建议
现在 `FileSystemOperator` 已经具备了处理 `cli/command.json` 这种嵌套结构的能力。

1.  请尝试运行 `stitcher --help`。你应该能看到来自 JSON 的英文描述（"Stitcher-Python: Bridging the gap..."）。
2.  然后，尝试 `STITCHER_LANG=zh stitcher --help`，验证中文输出是否正常工作。
