简要回答
好的，我们将实现 `TransactionManager` 原型及其配套的单元测试和集成测试。

## [WIP] feat: 实现 TransactionManager 原型

### 用户需求
根据阶段一规划，需要实现 `TransactionManager`，支持 `VirtualFileSystem` 语义（记录操作但不立即执行），支持预览（diff/plan），并能执行实际的文件写入和移动操作。同时要求建立分离的单元测试和集成测试结构。

### 评论
`TransactionManager` 是重构引擎安全性的基石。通过引入 `FileSystemAdapter` 协议，我们可以轻松地在单元测试中 Mock 文件系统操作，而在集成测试中使用真实的文件系统，从而完美符合“验证意图”的测试原则。

### 目标
1.  在 `packages/stitcher-refactor/src/stitcher/refactor/engine` 中实现 `TransactionManager`。
2.  定义 `FileOp` 抽象基类及其子类 `WriteFileOp` 和 `MoveFileOp`。
3.  定义 `FileSystemAdapter` 协议以支持依赖注入。
4.  建立 `packages/stitcher-refactor/tests` 目录结构，包含 `unit` 和 `integration` 子目录。
5.  编写单元测试验证操作队列逻辑，编写集成测试验证实际文件系统副作用。

### 基本原理
-   **命令模式 (Command Pattern)**: 将每个文件操作封装为 `FileOp` 对象，使得操作可以被记录、预览、重排或取消。
-   **依赖倒置 (DIP)**: `TransactionManager` 依赖于 `FileSystemAdapter` 接口而非 `pathlib` 的具体实现，这使得我们在单元测试中可以完全解耦文件系统。
-   **测试分层**: 单元测试关注逻辑（操作是否被正确添加和排序），集成测试关注副作用（文件是否真的被创建）。

### 标签
#intent/build #flow/ready #priority/high #comp/runtime #task/domain/refactor #task/object/transaction-manager #task/action/implementation #task/state/continue

---

### Script

#### Acts 1: 创建测试目录结构
首先建立符合要求的测试目录结构。

~~~~~act
run_command
~~~~~
~~~~~bash
mkdir -p packages/stitcher-refactor/tests/unit
mkdir -p packages/stitcher-refactor/tests/integration
touch packages/stitcher-refactor/tests/__init__.py
touch packages/stitcher-refactor/tests/unit/__init__.py
touch packages/stitcher-refactor/tests/integration/__init__.py
~~~~~

#### Acts 2: 初始化 engine 包
确保 `engine` 子包有 `__init__.py`。

~~~~~act
write_file
packages/stitcher-refactor/src/stitcher/refactor/engine/__init__.py
~~~~~
~~~~~python
from .transaction import TransactionManager

__all__ = ["TransactionManager"]
~~~~~

#### Acts 3: 实现 TransactionManager
实现核心的事务管理器逻辑。我们将引入一个简单的 `FileSystemAdapter` 来解耦 IO。

~~~~~act
write_file
packages/stitcher-refactor/src/stitcher/refactor/engine/transaction.py
~~~~~
~~~~~python
import shutil
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import List, Union, Protocol, Optional


class FileSystemAdapter(Protocol):
    def write_text(self, path: Path, content: str) -> None: ...
    def move(self, src: Path, dest: Path) -> None: ...
    def exists(self, path: Path) -> bool: ...
    def read_text(self, path: Path) -> str: ...


class RealFileSystem:
    def write_text(self, path: Path, content: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def move(self, src: Path, dest: Path) -> None:
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dest))

    def exists(self, path: Path) -> bool:
        return path.exists()

    def read_text(self, path: Path) -> str:
        return path.read_text(encoding="utf-8")


@dataclass
class FileOp(ABC):
    path: Path

    @abstractmethod
    def execute(self, fs: FileSystemAdapter, root: Path) -> None: ...

    @abstractmethod
    def describe(self) -> str: ...


@dataclass
class WriteFileOp(FileOp):
    content: str

    def execute(self, fs: FileSystemAdapter, root: Path) -> None:
        fs.write_text(root / self.path, self.content)

    def describe(self) -> str:
        return f"[WRITE] {self.path}"


@dataclass
class MoveFileOp(FileOp):
    dest: Path

    def execute(self, fs: FileSystemAdapter, root: Path) -> None:
        fs.move(root / self.path, root / self.dest)

    def describe(self) -> str:
        return f"[MOVE] {self.path} -> {self.dest}"


class TransactionManager:
    def __init__(self, root_path: Path, fs: Optional[FileSystemAdapter] = None):
        self.root_path = root_path
        self.fs = fs or RealFileSystem()
        self._ops: List[FileOp] = []

    def add_write(self, path: Union[str, Path], content: str) -> None:
        self._ops.append(WriteFileOp(Path(path), content))

    def add_move(self, src: Union[str, Path], dest: Union[str, Path]) -> None:
        self._ops.append(MoveFileOp(Path(src), Path(dest)))

    def preview(self) -> List[str]:
        return [op.describe() for op in self._ops]

    def commit(self) -> None:
        for op in self._ops:
            op.execute(self.fs, self.root_path)
        self._ops.clear()
    
    @property
    def pending_count(self) -> int:
        return len(self._ops)
~~~~~

#### Acts 4: 编写单元测试
单元测试使用 Mock 对象验证 `TransactionManager` 是否正确生成了操作队列，而不进行实际 IO。

~~~~~act
write_file
packages/stitcher-refactor/tests/unit/test_transaction.py
~~~~~
~~~~~python
from pathlib import Path
from unittest.mock import Mock
from stitcher.refactor.engine.transaction import (
    TransactionManager,
    FileSystemAdapter,
    WriteFileOp,
    MoveFileOp,
)


def test_transaction_add_ops():
    # Setup
    mock_fs = Mock(spec=FileSystemAdapter)
    tm = TransactionManager(Path("/tmp"), fs=mock_fs)

    # Execute
    tm.add_write("test.py", "print('hello')")
    tm.add_move("old.py", "new.py")

    # Verify Preview
    preview = tm.preview()
    assert len(preview) == 2
    assert preview[0] == "[WRITE] test.py"
    assert preview[1] == "[MOVE] old.py -> new.py"

    # Verify Internal State
    assert tm.pending_count == 2
    assert isinstance(tm._ops[0], WriteFileOp)
    assert isinstance(tm._ops[1], MoveFileOp)


def test_transaction_commit():
    # Setup
    mock_fs = Mock(spec=FileSystemAdapter)
    root = Path("/root")
    tm = TransactionManager(root, fs=mock_fs)

    tm.add_write("test.py", "content")
    tm.add_move("src.py", "dest.py")

    # Execute
    tm.commit()

    # Verify Intent (Mock Calls)
    # 1. Verify Write
    mock_fs.write_text.assert_called_once_with(root / "test.py", "content")
    
    # 2. Verify Move
    mock_fs.move.assert_called_once_with(root / "src.py", "root/dest.py")

    # 3. Verify Queue Cleared
    assert tm.pending_count == 0
~~~~~

#### Acts 5: 编写集成测试
集成测试使用 `tmp_path` 验证实际的文件系统副作用。

~~~~~act
write_file
packages/stitcher-refactor/tests/integration/test_transaction_fs.py
~~~~~
~~~~~python
from stitcher.refactor.engine.transaction import TransactionManager


def test_real_fs_commit(tmp_path):
    # Setup: Create a source file for moving
    src_file = tmp_path / "old.txt"
    src_file.write_text("original content", encoding="utf-8")

    # Initialize TM with real FS (default)
    tm = TransactionManager(tmp_path)

    # Plan operations
    tm.add_write("new.txt", "new content")
    tm.add_move("old.txt", "moved.txt")

    # Execute
    tm.commit()

    # Verify Side Effects
    # 1. Check Write
    new_file = tmp_path / "new.txt"
    assert new_file.exists()
    assert new_file.read_text(encoding="utf-8") == "new content"

    # 2. Check Move
    moved_file = tmp_path / "moved.txt"
    assert moved_file.exists()
    assert moved_file.read_text(encoding="utf-8") == "original content"
    assert not src_file.exists()
~~~~~

### 下一步建议
基础设施已经就绪。下一步我们应该进入核心逻辑的开发，实现 `SemanticGraph` 原型，集成 `griffe` 来构建代码的语义索引。这将使我们能够开始编写 `RenameSymbolOperation`。
