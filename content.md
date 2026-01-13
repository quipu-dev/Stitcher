Excellent. We are now moving to the second step of the roadmap: extending the data access layer to support efficient, batch-oriented data fetching for the graph builder.

Your plan correctly identifies the need for bulk data access. To build on that, and in adherence to the principle of **Ontological Correctness**, I'll refine the proposal slightly. Instead of returning a list of heavy `ReferenceRecord` objects, I will introduce a new, lighter data model called `DependencyEdge`. This model will represent the exact information the graph builder needs—the relationship between two files—making the interface more precise and the data transfer more efficient.

This approach avoids loading unnecessary details and provides a clean, purpose-built contract for the analysis layer.

Here is the plan to implement this refined data access interface.

## [WIP] feat: Extend index protocol for bulk graph data retrieval

### 用户需求

To efficiently build a project-wide dependency graph, the analysis engine needs to fetch all dependency relationships from the `index.db` in a single, efficient query. This requires extending the `IndexStoreProtocol` and its implementation to provide methods for bulk data retrieval.

### 评论

This is a critical step that bridges the gap between our persistent index (on-disk) and the upcoming in-memory graph model. By introducing a dedicated `DependencyEdge` data transfer object and implementing an efficient, JOIN-based SQL query, we ensure that the graph construction process is both fast and scalable. This change moves Stitcher's capabilities from single-file analysis to true project-wide architectural reasoning.

### 目标

1.  Define a new, lightweight `DependencyEdge` data model in `stitcher-spec` to represent a single import dependency.
2.  Update the `IndexStoreProtocol` in `stitcher-spec` to include new methods for fetching all file records and all dependency edges.
3.  Implement these new methods in the `IndexStore` class in `stitcher-index`, using efficient, bulk SQL queries.

### 基本原理

1.  **Model Definition**: A new `DependencyEdge` dataclass will be added to `stitcher.spec.index`. This creates a clear, self-describing contract for dependency data.
2.  **Protocol Update**: The `IndexStoreProtocol` will be modified via `patch_file` to rename the existing `get_all_files_metadata` to `get_all_files` for clarity and to add the new `get_all_dependency_edges` method.
3.  **Implementation**: The `IndexStore` class will be updated to match the new protocol. The `get_all_dependency_edges` method will execute a single SQL query that JOINs the `references` and `files` tables to retrieve all necessary data in one pass, which is significantly more performant than iterating file by file.

### 标签

#intent/build #flow/ready #priority/high #comp/spec #comp/index #concept/graph #concept/data-access #scope/api #scope/core #ai/refine #task/domain/analysis #task/object/graph-infra #task/action/implementation #task/state/continue

---

### Script

#### Acts 1: Define `DependencyEdge` model in `stitcher-spec`

We will first introduce the new `DependencyEdge` dataclass, which will serve as the data transfer object for dependency information.

~~~~~act
patch_file
packages/stitcher-spec/src/stitcher/spec/index.py
~~~~~
~~~~~python.old
    target_id: Optional[str] = None
    source_file_id: Optional[int] = None
    id: Optional[int] = None
~~~~~
~~~~~python.new
    target_id: Optional[str] = None
    source_file_id: Optional[int] = None
    id: Optional[int] = None


@dataclass
class DependencyEdge:
    source_path: str
    target_fqn: str
    kind: str
    lineno: int
~~~~~

#### Acts 2: Update `IndexStoreProtocol` in `stitcher-spec`

Next, we update the protocol to reflect the new bulk data-fetching capabilities.

~~~~~act
patch_file
packages/stitcher-spec/src/stitcher/spec/storage.py
~~~~~
~~~~~python.old
from typing import Protocol, List, Optional, Tuple

from .index import FileRecord, SymbolRecord, ReferenceRecord


class IndexStoreProtocol(Protocol):
    # --- Read Operations ---
    def get_symbols_by_file_path(self, file_path: str) -> List[SymbolRecord]: ...

    def find_symbol_by_fqn(
        self, target_fqn: str
    ) -> Optional[Tuple[SymbolRecord, str]]: ...

    def find_references(
        self, target_fqn: str, target_id: Optional[str] = None
    ) -> List[Tuple[ReferenceRecord, str]]: ...

    def get_all_files_metadata(self) -> List[FileRecord]: ...

    # --- Write/Sync Operations ---
    def sync_file(
~~~~~
~~~~~python.new
from typing import Protocol, List, Optional, Tuple

from .index import FileRecord, SymbolRecord, ReferenceRecord, DependencyEdge


class IndexStoreProtocol(Protocol):
    # --- Read Operations ---
    def get_symbols_by_file_path(self, file_path: str) -> List[SymbolRecord]: ...

    def find_symbol_by_fqn(
        self, target_fqn: str
    ) -> Optional[Tuple[SymbolRecord, str]]: ...

    def find_references(
        self, target_fqn: str, target_id: Optional[str] = None
    ) -> List[Tuple[ReferenceRecord, str]]: ...

    def get_all_files(self) -> List[FileRecord]: ...

    def get_all_dependency_edges(self) -> List[DependencyEdge]: ...

    # --- Write/Sync Operations ---
    def sync_file(
~~~~~

#### Acts 3: Implement new methods in `IndexStore`

Finally, we implement the updated protocol in the `IndexStore` class.

~~~~~act
patch_file
packages/stitcher-index/src/stitcher/index/store.py
~~~~~
~~~~~python.old
from typing import Optional, List, Tuple
from .db import DatabaseManager
from .linker import Linker
from stitcher.spec.index import FileRecord, SymbolRecord, ReferenceRecord


class IndexStore:
~~~~~
~~~~~python.new
from typing import Optional, List, Tuple
from .db import DatabaseManager
from .linker import Linker
from stitcher.spec.index import FileRecord, SymbolRecord, ReferenceRecord, DependencyEdge


class IndexStore:
~~~~~

~~~~~act
patch_file
packages/stitcher-index/src/stitcher/index/store.py
~~~~~
~~~~~python.old
            return [ReferenceRecord(**dict(row)) for row in rows]

    def get_all_files_metadata(self) -> List[FileRecord]:
        with self.db.get_connection() as conn:
            rows = conn.execute(
                "SELECT id, path, content_hash, last_mtime, last_size, indexing_status FROM files"
            ).fetchall()
            return [FileRecord(**dict(row)) for row in rows]

    def delete_file(self, file_id: int) -> None:
        with self.db.get_connection() as conn:
            conn.execute("DELETE FROM files WHERE id = ?", (file_id,))
~~~~~
~~~~~python.new
            return [ReferenceRecord(**dict(row)) for row in rows]

    def get_all_files(self) -> List[FileRecord]:
        with self.db.get_connection() as conn:
            rows = conn.execute(
                "SELECT id, path, content_hash, last_mtime, last_size, indexing_status FROM files"
            ).fetchall()
            return [FileRecord(**dict(row)) for row in rows]

    def get_all_dependency_edges(self) -> List[DependencyEdge]:
        with self.db.get_connection() as conn:
            rows = conn.execute(
                """
                SELECT
                    source_file.path AS source_path,
                    r.target_fqn,
                    r.kind,
                    r.lineno
                FROM "references" r
                JOIN files source_file ON r.source_file_id = source_file.id
                WHERE r.target_fqn IS NOT NULL
                """
            ).fetchall()
            return [DependencyEdge(**dict(row)) for row in rows]

    def delete_file(self, file_id: int) -> None:
        with self.db.get_connection() as conn:
            conn.execute("DELETE FROM files WHERE id = ?", (file_id,))
~~~~~

### 下一步建议

我们已经成功地为数据层添加了高效的批量查询接口。现在，数据已经准备好被消费。

下一步是**实现图构建器 (Implement Graph Builder)**。我将创建一个 `GraphBuilder` 类，它会使用我们刚刚定义的 `get_all_files` 和 `get_all_dependency_edges` 方法来消费数据，并构建一个 `networkx.DiGraph` 内存图。如果你同意，我将开始制定这个计划。
