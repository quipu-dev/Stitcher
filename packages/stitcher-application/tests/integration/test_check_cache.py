from unittest.mock import MagicMock
from stitcher.test_utils import WorkspaceFactory, create_test_app


def test_check_hits_index_cache_on_second_run(tmp_path, monkeypatch):
    """
    Verifies that a second 'check' run without file changes hits the index cache
    and avoids re-parsing YAML files.
    """
    # 1. Arrange: A standard workspace
    factory = WorkspaceFactory(tmp_path)
    project_root = (
        factory.with_config({"scan_paths": ["src"]})
        .with_source("src/main.py", "def func(): pass")
        .with_docs("src/main.stitcher.yaml", {"func": "doc"})
        .build()
    )
    app = create_test_app(project_root)

    # 2. Act (First Run): Populate the index
    # We don't need to check the result, just warm up the index.
    app.run_check()

    # 3. Arrange (Spying): Patch the re-parsing method called on a cache miss.
    from stitcher.lang.sidecar.indexer import SidecarIndexerAdapter

    mock_parse = MagicMock(wraps=SidecarIndexerAdapter.parse)
    monkeypatch.setattr(
        "stitcher.lang.sidecar.indexer.SidecarIndexerAdapter.parse", mock_parse
    )

    # 4. Act (Second Run): This run should hit the cache
    app.run_check()

    # 5. Assert (Cache Hit): The re-parse method was NOT called
    mock_parse.assert_not_called()

    # 6. Act (Third Run - Cache Miss): Modify a file to invalidate the cache
    (project_root / "src/main.stitcher.yaml").write_text(
        'func: "updated doc"', encoding="utf-8"
    )
    app.run_check()

    # 7. Assert (Cache Miss): The re-parse method was called this time
    mock_parse.assert_called_once()
