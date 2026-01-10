from typing import Optional, List, Tuple
from .db import DatabaseManager
from .types import FileRecord, SymbolRecord, ReferenceRecord


class IndexStore:
    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager

    def sync_file(
        self, path: str, content_hash: str, mtime: float, size: int
    ) -> Tuple[int, bool]:
        with self.db.get_connection() as conn:
            cursor = conn.execute(
                "SELECT id, content_hash FROM files WHERE path = ?", (path,)
            )
            row = cursor.fetchone()

            if row:
                file_id = row["id"]
                old_hash = row["content_hash"]
                if old_hash != content_hash:
                    # Content changed: update metadata and mark as dirty
                    conn.execute(
                        """
                        UPDATE files 
                        SET content_hash = ?, last_mtime = ?, last_size = ?, indexing_status = 0
                        WHERE id = ?
                        """,
                        (content_hash, mtime, size, file_id),
                    )
                    return file_id, True
                else:
                    # Content same: just update stat metadata to prevent rescans
                    conn.execute(
                        """
                        UPDATE files 
                        SET last_mtime = ?, last_size = ? 
                        WHERE id = ?
                        """,
                        (mtime, size, file_id),
                    )
                    return file_id, False
            else:
                # New file
                cursor = conn.execute(
                    """
                    INSERT INTO files (path, content_hash, last_mtime, last_size, indexing_status)
                    VALUES (?, ?, ?, ?, 0)
                    """,
                    (path, content_hash, mtime, size),
                )
                return cursor.lastrowid, True

    def get_file_by_path(self, path: str) -> Optional[FileRecord]:
        with self.db.get_connection() as conn:
            row = conn.execute("SELECT * FROM files WHERE path = ?", (path,)).fetchone()
            if row:
                return FileRecord(**dict(row))
        return None

    def update_analysis(
        self,
        file_id: int,
        symbols: List[SymbolRecord],
        references: List[ReferenceRecord],
    ) -> None:
        with self.db.get_connection() as conn:
            # 1. Clear old data for this file
            conn.execute("DELETE FROM symbols WHERE file_id = ?", (file_id,))
            conn.execute(
                "DELETE FROM 'references' WHERE source_file_id = ?", (file_id,)
            )

            # 2. Insert new symbols
            if symbols:
                conn.executemany(
                    """
                    INSERT INTO symbols (
                        id, file_id, name, logical_path, kind, 
                        alias_target_id, location_start, location_end, signature_hash
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        (
                            s.id,
                            file_id,
                            s.name,
                            s.logical_path,
                            s.kind,
                            s.alias_target_id,
                            s.location_start,
                            s.location_end,
                            s.signature_hash,
                        )
                        for s in symbols
                    ],
                )

            # 3. Insert new references
            if references:
                conn.executemany(
                    """
                    INSERT INTO 'references' (
                        source_file_id, target_id, kind, 
                        location_start, location_end
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    [
                        (
                            file_id,
                            r.target_id,
                            r.kind,
                            r.location_start,
                            r.location_end,
                        )
                        for r in references
                    ],
                )

            # 4. Mark as indexed
            conn.execute(
                "UPDATE files SET indexing_status = 1 WHERE id = ?", (file_id,)
            )

    def get_symbols_by_file(self, file_id: int) -> List[SymbolRecord]:
        with self.db.get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM symbols WHERE file_id = ?", (file_id,)
            ).fetchall()
            return [SymbolRecord(**dict(row)) for row in rows]

    def get_references_by_file(self, file_id: int) -> List[ReferenceRecord]:
        with self.db.get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM 'references' WHERE source_file_id = ?", (file_id,)
            ).fetchall()
            return [ReferenceRecord(**dict(row)) for row in rows]

    def get_all_files_metadata(self) -> List[FileRecord]:
        """Fetch all file records to build an in-memory cache for the scanner."""
        with self.db.get_connection() as conn:
            rows = conn.execute(
                "SELECT id, path, content_hash, last_mtime, last_size, indexing_status FROM files"
            ).fetchall()
            return [FileRecord(**dict(row)) for row in rows]

    def delete_file(self, file_id: int) -> None:
        """Remove a file and its associated symbols/references (via cascade)."""
        with self.db.get_connection() as conn:
            conn.execute("DELETE FROM files WHERE id = ?", (file_id,))
