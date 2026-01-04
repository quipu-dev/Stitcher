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
