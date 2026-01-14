这是关于将 Sidecar 提升为索引一等公民的重构计划的最后一步。

## [WIP] fix: 将 Sidecar 适配器注册到 .yaml 后缀以确保正确索引

### 用户需求
确保 `IndexRunner` 能够正确识别并索引 `.stitcher.yaml` 文件。由于 `pathlib` 的后缀处理机制，直接注册 `.stitcher.yaml` 会导致 `FileIndexer` 无法匹配到文件（因为它看到的后缀是 `.yaml`），从而导致 Sidecar 文件被跳过，无法进入索引。

### 评论
这是一个关键的配置修正。虽然我们创建了专门的 `SidecarIndexerAdapter`，但如果它没有被正确地钩挂到文件索引流程中，整个架构升级就无法生效。将适配器注册到 `.yaml` 后缀，并依赖适配器内部的逻辑来过滤非 Sidecar 文件，是目前最稳妥的集成方式。

### 目标
1.  修改 `StitcherApp` 的初始化逻辑，将 `SidecarIndexerAdapter` 注册到 `.yaml` 扩展名，而不是 `.stitcher.yaml`。

### 基本原理
`FileIndexer` 使用 `path.suffix` 来查找适配器。对于 `module.stitcher.yaml`，其 suffix 是 `.yaml`。因此，必须将适配器注册为 `.yaml` 处理程序。适配器内部已经包含了 `if not file_path.name.endswith(".stitcher.yaml"): return` 的守卫逻辑，因此这不会导致处理错误的 YAML 文件。

### 标签
#intent/fix #flow/ready #priority/high #comp/application #comp/indexer #concept/config #scope/core #ai/instruct #task/domain/indexing #task/object/adapter #task/action/register #task/state/end

---

### Script

#### Acts 1: Correct Adapter Registration in StitcherApp
I will modify `packages/stitcher-application/src/stitcher/app/core.py` to register the adapter with the correct file extension key.

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/core.py
~~~~~
~~~~~python.old
        # Sidecar Adapter (NEW)
        sidecar_uri_generator = SidecarURIGenerator()
        sidecar_adapter = SidecarIndexerAdapter(root_path, sidecar_uri_generator)
        self.file_indexer.register_adapter(".stitcher.yaml", sidecar_adapter)

        # 4. Runners (Command Handlers)
~~~~~
~~~~~python.new
        # Sidecar Adapter (NEW)
        sidecar_uri_generator = SidecarURIGenerator()
        sidecar_adapter = SidecarIndexerAdapter(root_path, sidecar_uri_generator)
        # Register for .yaml because FileIndexer uses path.suffix.
        # The adapter itself filters for .stitcher.yaml files.
        self.file_indexer.register_adapter(".yaml", sidecar_adapter)

        # 4. Runners (Command Handlers)
~~~~~

### 下一步建议
至此，架构重构的“连线”工作已全部完成：
1.  **Index**: Sidecar 文件被索引器识别（通过 `.yaml` 后缀）。
2.  **Adapter**: `SidecarIndexerAdapter` 解析文件并存入 DB。
3.  **Consumption**: `DocumentManager` 优先从 DB 读取文档数据。
4.  **Application**: `CheckRunner` 等组件通过 `DocumentManager` 间接受益于索引加速。

建议运行完整的测试套件（特别是集成测试），验证整个流程是否通畅，以及是否有性能回归。
