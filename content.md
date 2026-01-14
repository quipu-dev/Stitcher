Excellent catch. The test failure is not just a bug, but a crucial piece of architectural feedback.

You are absolutely right to start the optimization now. My analysis is as follows:

**Error Analysis**:

The test `test_check_hits_index_cache_on_second_run` failed because our spy was placed on the wrong component. We were monitoring `SidecarAdapter.load_doc_irs`, which is part of the **old, direct file-reading data path**. However, the `check` command's performance path now relies on the **new, indexed data path**.

Here's the new data flow when a file is modified:
1.  `FileIndexer` detects the change in `main.stitcher.yaml` (cache miss).
2.  It invokes the registered adapter for `.yaml` files, which is now our `SidecarIndexerAdapter`.
3.  `SidecarIndexerAdapter.parse()` is called. **This is the method that reads the file content to update the database index.**
4.  The index is updated with the new content.
5.  Later, when the analysis rules run, `DocumentManager` reads the fresh data directly from the now-updated index, *without ever needing to call `SidecarAdapter.load_doc_irs`*.

Our test correctly proved the cache **hit** (`assert_not_called`) because the old I/O path was indeed bypassed. But it failed to prove the cache **miss**, because we were listening on a now-abandoned road.

The solution is to move our spy to the correct chokepoint in the new architecture: `SidecarIndexerAdapter.parse`.

I will now generate a plan to fix the test and then proceed with the originally planned optimization of `DocumentManager`.

## [WIP] fix(test): Correct spy target to validate indexer cache miss

### 错误分析

测试 `test_check_cache.py` 失败的根源在于 `monkeypatch` 监视了错误的函数。我们监视了 `SidecarAdapter.load_doc_irs`，这是一个在旧的、直接读取文件工作流中使用的函数。

然而，在我们新的、基于索引的架构中，当 `check` 命令运行时，数据流已经改变：
1.  `FileIndexer` 检测到文件变更（缓存未命中）。
2.  `FileIndexer` 调用 `SidecarIndexerAdapter.parse()` 来读取文件内容并更新数据库索引。
3.  分析引擎从已更新的数据库索引中读取数据。

`SidecarAdapter.load_doc_irs` 在这个流程中从未被调用。因此，我们的测试正确地验证了缓存命中（`assert_not_called`），但错误地报告了缓存未命中时的失败，因为它在监听一个已被弃用的数据路径。正确的做法是监视 `SidecarIndexerAdapter.parse()`。

### 用户需求

修复 `test_check_cache.py` 测试，使其能够正确验证在 Sidecar 文件被修改后，增量索引器会重新解析该文件（即缓存失效）。

### 评论

这个测试失败是一个积极的信号，它证明了我们的架构重构正在将数据读取的路径从慢速 I/O 转移到快速的索引查询。修复这个测试将为我们新的、高性能的索引机制提供一个坚实的质量保证，确保其缓存失效逻辑是正确和可靠的。

### 目标

1.  修改 `packages/stitcher-application/tests/integration/test_check_cache.py`。
2.  将 `monkeypatch` 的目标从 `stitcher.lang.sidecar.adapter.SidecarAdapter.load_doc_irs` 更改为 `stitcher.lang.sidecar.indexer.SidecarIndexerAdapter.parse`。

### 基本原理

在新的架构中，`FileIndexer` 是缓存状态的管理者。当它检测到文件变化时，它会调用特定语言的 `IndexerAdapter` 的 `parse` 方法来重新处理文件内容并更新数据库。因此，`SidecarIndexerAdapter.parse` 是验证缓存失效（cache miss）时文件被重新处理的唯一、正确的观察点。

### 标签

#intent/fix #intent/tooling #flow/ready #priority/high #comp/tests #concept/state #scope/dx #ai/instruct #task/domain/testing #task/object/cache-validation #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 修正测试用例的监视目标

我们将修改测试文件，使其监视正确的函数 `SidecarIndexerAdapter.parse`。

~~~~~act
patch_file
packages/stitcher-application/tests/integration/test_check_cache.py
~~~~~
~~~~~python.old
    # 3. Arrange (Spying): Patch the expensive IO/parsing method
    # This method is downstream of the indexer and should only be called on a cache miss.
    from stitcher.lang.sidecar.adapter import SidecarAdapter

    mock_load_irs = MagicMock(wraps=SidecarAdapter.load_doc_irs)
    monkeypatch.setattr(
        "stitcher.lang.sidecar.adapter.SidecarAdapter.load_doc_irs", mock_load_irs
    )

    # 4. Act (Second Run): This run should hit the cache
    app.run_check()

    # 5. Assert (Cache Hit): The expensive method was NOT called
    mock_load_irs.assert_not_called()

    # 6. Act (Third Run - Cache Miss): Modify a file to invalidate the cache
    (project_root / "src/main.stitcher.yaml").write_text(
        'func: "updated doc"', encoding="utf-8"
    )
    app.run_check()

    # 7. Assert (Cache Miss): The expensive method was called this time
    mock_load_irs.assert_called_once()
~~~~~
~~~~~python.new
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
~~~~~

### 下一步建议

测试已经修复并能够正确验证我们的新架构。现在，我们将执行计划的核心部分：**修改 `DocumentManager`**，使其在 `check` 流程中完全依赖 `IndexStore` 来读取文档数据，从而彻底消除 YAML 解析的性能瓶颈。

如果你同意，我将生成相应的计划。
