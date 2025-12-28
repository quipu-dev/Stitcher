from pathlib import Path
from needle.loaders import FileSystemLoader


def test_fs_loader_synthesizes_fqn_from_path(tmp_path: Path):
    """
    Verifies that FileSystemLoader correctly synthesizes FQN prefixes
    based on the file path relative to the domain root.

    Structure:
    root/
      needle/
        en/
          cli/
            command.json  -> {"check": "Check..."} -> cli.command.check
          check/
            file.json     -> {"fail": "Fail..."}   -> check.file.fail
          __init__.json   -> {"app": "Stitcher"}   -> app
    """
    # 1. Arrange
    needle_root = tmp_path / "needle" / "en"
    needle_root.mkdir(parents=True)

    # Create cli/command.json
    (needle_root / "cli").mkdir()
    (needle_root / "cli" / "command.json").write_text(
        '{"check": "Check command"}', encoding="utf-8"
    )

    # Create check/file.json
    (needle_root / "check").mkdir()
    (needle_root / "check" / "file.json").write_text(
        '{"fail": "Check failed"}', encoding="utf-8"
    )

    # Create __init__.json (Root level)
    (needle_root / "__init__.json").write_text(
        '{"app": "Stitcher App"}', encoding="utf-8"
    )

    # 2. Act
    loader = FileSystemLoader(root=tmp_path)
    # Force load 'en' domain
    data = loader.load("en")

    # 3. Assert
    # Case A: Nested file
    assert "cli.command.check" in data
    assert data["cli.command.check"] == "Check command"

    # Case B: Another nested file
    assert "check.file.fail" in data
    assert data["check.file.fail"] == "Check failed"

    # Case C: __init__.json (Should NOT have __init__ prefix)
    assert "app" in data
    assert data["app"] == "Stitcher App"
    # Should NOT be "__init__.app"
    assert "__init__.app" not in data
