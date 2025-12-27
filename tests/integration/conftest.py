import pytest
from pathlib import Path
from stitcher.test_utils import VenvHarness


@pytest.fixture
def isolated_env(tmp_path: Path) -> VenvHarness:
    """
    Provides an isolated virtual environment harness for integration testing.
    """
    return VenvHarness(tmp_path)