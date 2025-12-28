from pathlib import Path
from stitcher.io import YamlAdapter


def test_yaml_adapter_load_non_existent(tmp_path: Path):
    adapter = YamlAdapter()
    data = adapter.load(tmp_path / "non_existent.yaml")
    assert data == {}


def test_yaml_adapter_round_trip(tmp_path: Path):
    adapter = YamlAdapter()
    file_path = tmp_path / "docs.yaml"

    input_data = {
        "MyClass": "A simple class",
        "MyClass.method": "A method with\nnewlines",
        "func": "中文测试",
    }

    # Write
    adapter.save(file_path, input_data)
    assert file_path.exists()

    # Read back
    loaded_data = adapter.load(file_path)

    assert loaded_data["MyClass"] == "A simple class"
    assert loaded_data["MyClass.method"] == "A method with\nnewlines"
    assert loaded_data["func"] == "中文测试"

    # Verify file content is deterministic (sorted)
    content = file_path.read_text(encoding="utf-8")
    # "MyClass" comes before "MyClass.method" (lexicographical)
    # But "func" comes last.
    # Let's just check raw content contains keys (which are now quoted)
    assert '"MyClass": |-' in content
    assert "  中文测试" in content


def test_yaml_adapter_handles_malformed(tmp_path: Path):
    file_path = tmp_path / "bad.yaml"
    file_path.write_text(":: :: invalid yaml", encoding="utf-8")

    adapter = YamlAdapter()
    data = adapter.load(file_path)
    # Current implementation swallows errors and returns empty dict
    assert data == {}


def test_yaml_adapter_block_format_consistency(tmp_path: Path):
    adapter = YamlAdapter()
    file_path = tmp_path / "docs.yaml"
    data = {"multi": "Line 1\nLine 2", "single": "Just one line"}

    adapter.save(file_path, data)

    content = file_path.read_text(encoding="utf-8")

    # Both should use block style with strip chomping (|-) and quoted keys
    assert '"multi": |-' in content
    assert '"single": |-' in content

    # Check indentation
    assert "  Line 1" in content
    assert "  Just one line" in content
