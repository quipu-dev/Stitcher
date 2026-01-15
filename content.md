简要回答
好的，我将修复 `SidecarIndexerAdapter` 中的路径处理逻辑。

## [WIP] fix: 修复 SidecarIndexerAdapter 绝对路径处理导致索引失败的问题

### 错误分析
`test_init_sidecar_idempotency.py` 测试失败的根源在于 `stitcher.lock` 文件未被更新。进一步溯源发现，`DocumentManager` 未能加载 Sidecar 文件中的文档，导致 `PumpExecutor` 无法获取到文档内容来更新 Lock 文件。
`DocumentManager` 依赖索引系统加载文档。虽然 `Workspace` 正确发现了 Sidecar 文件，但 `FileIndexer` 向 `SidecarIndexerAdapter.parse` 传递的是**绝对路径**。
`SidecarIndexerAdapter` 直接使用该路径调用 `path_to_logical_fqn`。由于该函数期望项目相对路径，传入绝对路径会导致解析失败（抛出异常或返回空），进而导致该文件未能成功索引符号。

### 用户需求
修复 `test_init_sidecar_idempotency` 测试失败。

### 评论
这是一个典型的集成层 Bug，组件间对路径格式（绝对 vs 相对）的假设不一致导致了静默失败（`FileIndexer` 捕获并忽略了异常）。

### 目标
1.  修改 `SidecarIndexerAdapter.parse` 方法。
2.  在处理路径前，先将其转换为相对于 `root_path` 的相对路径。
3.  确保 `path_to_logical_fqn` 和 `generate_symbol_uri` 使用的是相对路径。

### 基本原理
Stitcher 的索引和 URI 系统设计为基于工作区相对路径。适配器层有责任将物理层（可能为绝对路径）的输入规范化为逻辑层（相对路径）所需的格式。

### 标签
#intent/fix #flow/ready #priority/high #comp/index #scope/core #ai/instruct #task/domain/indexing #task/object/sidecar-adapter #task/action/bugfix #task/state/end

---

### Script

#### Acts 1: 修复 SidecarIndexerAdapter 路径规范化

~~~~~act
patch_file
packages/stitcher-lang-sidecar/src/stitcher/lang/sidecar/indexer.py
~~~~~
~~~~~python.old
        # 2. Determine paths
        # file_path passed here is relative to project root (physical path)
        # We need to determine the companion Python file path for references
        py_name = file_path.name.replace(".stitcher.yaml", ".py")
        py_path_rel = file_path.with_name(py_name)

        # Pre-calculate logical module FQN for linking
        logical_module_fqn = path_to_logical_fqn(py_path_rel.as_posix())

        # 3. Parse references with location info using the helper
        loc_map = {
            frag: (line, col) for frag, line, col in parse_doc_references(content)
        }

        for fragment, value in data.items():
            # Skip if it's not a valid key
            if not isinstance(fragment, str):
                continue

            # --- Build Symbol ---
            suri = self.uri_generator.generate_symbol_uri(str(file_path), fragment)
            lineno, col_offset = loc_map.get(fragment, (0, 0))
~~~~~
~~~~~python.new
        # 2. Determine paths
        # file_path passed here might be absolute (from FileIndexer), ensure relative
        if file_path.is_absolute():
            try:
                rel_path = file_path.relative_to(self.root_path)
            except ValueError:
                # Fallback if path is outside root (unlikely given discovery logic)
                rel_path = file_path
        else:
            rel_path = file_path

        py_name = rel_path.name.replace(".stitcher.yaml", ".py")
        py_path_rel = rel_path.with_name(py_name)

        # Pre-calculate logical module FQN for linking
        logical_module_fqn = path_to_logical_fqn(py_path_rel.as_posix())

        # 3. Parse references with location info using the helper
        loc_map = {
            frag: (line, col) for frag, line, col in parse_doc_references(content)
        }

        for fragment, value in data.items():
            # Skip if it's not a valid key
            if not isinstance(fragment, str):
                continue

            # --- Build Symbol ---
            suri = self.uri_generator.generate_symbol_uri(str(rel_path), fragment)
            lineno, col_offset = loc_map.get(fragment, (0, 0))
~~~~~

### 下一步建议
运行测试验证修复。此修改应能解决 Sidecar 文件无法被正确索引的问题，从而使 `DocumentManager` 能够加载文档，最终使 `PumpExecutor` 正确更新 Lock 文件。
