import sqlite3
import logging
from pathlib import Path
from typing import Generator
from contextlib import contextmanager

try:
    from importlib.resources import files
except ImportError:
    # For Python < 3.9 compatibility if needed, though project requires >=3.10
    from importlib_resources import files  # type: ignore

log = logging.getLogger(__name__)


class DatabaseManager:
    def __init__(self, db_path: Path):
        self.db_path = db_path

    def _get_raw_connection(self) -> sqlite3.Connection:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.db_path))

        # Performance & Integrity optimizations
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA synchronous = NORMAL;")
        conn.execute("PRAGMA foreign_keys = ON;")

        # Return rows as sqlite3.Row for dict-like access
        conn.row_factory = sqlite3.Row
        return conn

    def initialize(self) -> None:
        """Loads schema.sql and initializes the database tables."""
        schema_path = files("stitcher.index").joinpath("schema.sql")
        schema_sql = schema_path.read_text(encoding="utf-8")

        with self.get_connection() as conn:
            conn.executescript(schema_sql)
            log.debug(f"Initialized database at {self.db_path}")

    @contextmanager
    def get_connection(self) -> Generator[sqlite3.Connection, None, None]:
        """
        Yields a managed connection.
        Commits on success, rolls back on exception.
        Closes connection at the end.
        """
        conn = self._get_raw_connection()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
