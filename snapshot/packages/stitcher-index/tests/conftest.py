import pytest
from stitcher.index.db import DatabaseManager
from stitcher.index.store import IndexStore


@pytest.fixture
def db_path(tmp_path):
    return tmp_path / ".stitcher" / "index" / "index.db"


@pytest.fixture
def db_manager(db_path):
    manager = DatabaseManager(db_path)
    manager.initialize()
    return manager


@pytest.fixture
def store(db_manager):
    return IndexStore(db_manager)
