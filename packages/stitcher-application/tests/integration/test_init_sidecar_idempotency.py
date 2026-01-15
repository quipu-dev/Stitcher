from stitcher.test_utils import (
    create_test_app,
    SpyBus,
    WorkspaceFactory,
    get_stored_hashes,
)
from needle.pointer import L


def test_init_respects_existing_sidecar_baseline(tmp_path, monkeypatch):
    """
    验证 init 不会破坏已存在的 Sidecar 基线。
    场景：
    - 源码中函数 f 的 doc 为 "Source Doc"
    - Sidecar 文件中 f 的内容为 "Sidecar Doc"
    - 执行 init 后，lock 文件中的基线哈希应当对应 "Sidecar Doc"
    """
    factory = WorkspaceFactory(tmp_path)
    # 准备环境
    project_root = (
        factory.with_config({"scan_paths": ["src"]})
        .with_source("src/lib.py", 'def f():\n    """Source Doc"""\n    pass')
        .with_docs("src/lib.stitcher.yaml", {"f": "Sidecar Doc"})
        .build()
    )

    app = create_test_app(root_path=project_root)
    spy_bus = SpyBus()

    # 执行 init (现在等于 pump --reconcile)
    with spy_bus.patch(monkeypatch):
        app.run_init()

    # 获取 Lock 文件中记录的哈希
    hashes = get_stored_hashes(project_root, "src/lib.py")
    stored_yaml_hash = hashes.get("f", {}).get("baseline_yaml_content_hash")

    # 计算预期哈希（Sidecar 的内容）
    doc_manager = app.doc_manager
    ir = doc_manager.serializer.from_view_data("Sidecar Doc")
    expected_hash = doc_manager.compute_ir_hash(ir)

    # 验证 pump --reconcile 正确保留了 Sidecar 内容作为基线
    assert stored_yaml_hash == expected_hash, (
        f"Expected baseline to match Sidecar Doc ({expected_hash}), but got {stored_yaml_hash}"
    )

    # 验证输出消息（应该包含 Reconciled 信息）
    spy_bus.assert_id_called(L.pump.info.reconciled, level="info")


def test_index_stats_should_distinguish_sidecars(tmp_path, monkeypatch):
    """
    验证索引统计信息应当区分 Sidecar 文件。
    """
    factory = WorkspaceFactory(tmp_path)
    project_root = (
        factory.with_config({"scan_paths": ["src"]})
        .with_source("src/lib.py", 'def f():\n    """Doc"""\n    pass')
        .with_docs("src/lib.stitcher.yaml", {"f": "Doc"})
        .build()
    )

    app = create_test_app(root_path=project_root)
    spy_bus = SpyBus()

    with spy_bus.patch(monkeypatch):
        app.run_index_build()

    # 验证消息中是否包含 sidecars 统计字段
    messages = spy_bus.get_messages()
    index_complete_msg = next(
        m for m in messages if m["id"] == str(L.index.run.complete)
    )

    assert "sidecars" in index_complete_msg["params"], (
        "Index summary should include sidecar count"
    )
    assert index_complete_msg["params"]["sidecars"] == 1
