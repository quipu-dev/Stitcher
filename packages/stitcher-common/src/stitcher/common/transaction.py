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
    def rmtree(self, path: Path) -> None: ...
    def remove(self, path: Path) -> None: ...


class RealFileSystem:
    def write_text(self, path: Path, content: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def move(self, src: Path, dest: Path) -> None:
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dest))

    def exists(self, path: Path) -> bool:
        return path.exists()

    def rmtree(self, path: Path) -> None:
        if path.exists():
            shutil.rmtree(path)

    def remove(self, path: Path) -> None:
        if path.exists():
            path.unlink()

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


@dataclass
class DeleteFileOp(FileOp):
    def execute(self, fs: FileSystemAdapter, root: Path) -> None:
        fs.remove(root / self.path)

    def describe(self) -> str:
        return f"[DELETE] {self.path}"


@dataclass
class DeleteDirectoryOp(FileOp):
    def execute(self, fs: FileSystemAdapter, root: Path) -> None:
        fs.rmtree(root / self.path)

    def describe(self) -> str:
        return f"[DELETE_DIR] {self.path}"


class TransactionManager:
    def __init__(self, root_path: Path, fs: Optional[FileSystemAdapter] = None):
        self.root_path = root_path
        self.fs = fs or RealFileSystem()
        self._ops: List[FileOp] = []

    def add_write(self, path: Union[str, Path], content: str) -> None:
        self._ops.append(WriteFileOp(Path(path), content))

    def add_move(self, src: Union[str, Path], dest: Union[str, Path]) -> None:
        self._ops.append(MoveFileOp(Path(src), Path(dest)))

    def add_delete_file(self, path: Union[str, Path]) -> None:
        self._ops.append(DeleteFileOp(Path(path)))

    def add_delete_dir(self, path: Union[str, Path]) -> None:
        self._ops.append(DeleteDirectoryOp(Path(path)))

    def preview(self) -> List[str]:
        # Preview should also show rebased operations to be accurate
        rebased = self._rebase_ops(self._ops)
        return [op.describe() for op in rebased]

    def commit(self) -> None:
        rebased_ops = self._rebase_ops(self._ops)
        for op in rebased_ops:
            op.execute(self.fs, self.root_path)
        self._ops.clear()

    def _rebase_ops(self, ops: List[FileOp]) -> List[FileOp]:
        rebased_ops = []
        # Map current_location -> known_location
        # But wait, we need to track the location of specific logical files.
        # Simple approach: Trace forward.

        # Mapping from original_path (or transient path) to current_effective_path
        # No, that's not right.
        # We need to map: "If an op refers to path P, change it to P'"

        path_map = {}

        for op in ops:
            # 1. Resolve current path based on history
            # We copy the op to avoid mutating the original input list objects if reused
            # (Though dataclasses are mutable, let's be safe)
            import copy

            new_op = copy.copy(op)

            if new_op.path in path_map:
                new_op.path = path_map[new_op.path]

            # 2. Update map if this is a Move
            if isinstance(new_op, MoveFileOp):
                # Now, anything pointing to new_op.path should now point to new_op.dest
                # AND anything that mapped to new_op.path should now map to new_op.dest

                # Direct mapping:
                # If subsequent op targets 'src', it should target 'dest'
                src = new_op.path
                dest = new_op.dest

                # Update forward lookup
                path_map[src] = dest

                # Update existing transitive mappings
                # e.g. A->B, now B->C. We need A->C.
                for k, v in path_map.items():
                    if v == src:
                        path_map[k] = dest

            rebased_ops.append(new_op)

        return rebased_ops

    @property
    def pending_count(self) -> int:
        return len(self._ops)
