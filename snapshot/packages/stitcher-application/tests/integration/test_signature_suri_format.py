import json
from stitcher.test_utils import WorkspaceFactory, create_test_app
from stitcher.app.services import SignatureManager


def test_signature_files_use_suri_as_keys(tmp_path):
    """
    物理层验证：确保磁盘上的 .json 签名文件使用 SURI 格式作为键。
    格式要求: py://<rel_path>#<fragment>
    """
    # 1. Arrange: 创建一个具有代表性的项目布局
    factory = WorkspaceFactory(tmp_path)
    rel_source_path = "src/pkg/main.py"
    project_root = (
        factory.with_config({"scan_paths": ["src"]})
        .with_source(
            rel_source_path,
            """
def top_level_func():
    pass

class MyClass:
    def method_a(self):
        pass
            """,
        )
        .build()
    )

    app = create_test_app(project_root)

    # 2. Act: 运行初始化以产生签名文件
    app.run_init()

    # 3. Assert: 检查磁盘上的物理文件内容
    # 路径应该是: .stitcher/signatures/src/pkg/main.json
    sig_file_path = (
        project_root / ".stitcher" / "signatures" / "src" / "pkg" / "main.json"
    )
    assert sig_file_path.exists(), f"Signature file not found at {sig_file_path}"

    with sig_file_path.open("r", encoding="utf-8") as f:
        raw_data = json.load(f)

    # 我们期望的 SURI 键
    expected_suris = {
        f"py://{rel_source_path}#top_level_func",
        f"py://{rel_source_path}#MyClass",
        f"py://{rel_source_path}#MyClass.method_a",
    }

    actual_keys = set(raw_data.keys())

    # 验证是否所有键都符合 SURI 规范
    for key in actual_keys:
        assert key.startswith("py://"), (
            f"Key '{key}' does not start with 'py://' protocol prefix"
        )
        assert "#" in key, f"Key '{key}' is missing the fragment separator '#'"
        assert rel_source_path in key, (
            f"Key '{key}' does not contain the correct physical path"
        )

    # 验证关键符号是否存在
    for expected in expected_suris:
        assert expected in actual_keys, (
            f"Expected SURI key '{expected}' not found in JSON"
        )

    # 4. Assert: 验证逻辑层加载是否依然返回短键（以保证兼容性）
    manager = SignatureManager(project_root)
    loaded_hashes = manager.load_composite_hashes(rel_source_path)

    # 加载后的键应该是短键 (fragment)
    expected_short_keys = {"top_level_func", "MyClass", "MyClass.method_a"}
    assert set(loaded_hashes.keys()) == expected_short_keys

    for k in expected_short_keys:
        # 确保数据内容也正确加载了
        assert "baseline_code_structure_hash" in loaded_hashes[k]
