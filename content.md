好的，基础设施的效能正在稳步提升。通过这次提交，我们将彻底消除“无变更”场景下的序列化税，使 `stitcher check` 的响应速度向毫秒级迈进。

## [COMMIT] refactor(perf): 实施“热点集合”重构优化

### 用户需求
将优化后的“增量重构”逻辑提交到代码库，以解决性能审计中发现的 `reformat_all` 冗余开销问题。

### 评论
这次优化直接打击了耗时最重的“盲目写”反模式。通过让 `IndexRunner` 向上层传递具体的变更路径，我们成功地将 `reformat_all` 的执行范围缩减到了真正的“受灾区”，在项目无变更的情况下，这部分开销将趋近于零。

### 目标
1.  提交 `indexer.py`、`runners/index.py` 和 `core.py` 的修改。
2.  确保 `StitcherApp` 能够识别并仅处理本次扫描中发生变化的文件。

### 基本原理
性能优化的核心在于“不做无用功”。此前 `check` 命令无论是否有变更都会尝试对所有 440 个文件进行格式化检查，这涉及昂贵的 `yaml.dump`。现在，我们利用已有的增量索引结果作为过滤器，实现了真正的按需重构。

### 标签
#intent/refine #flow/ready #task/domain/performance #task/object/reformat-tax #task/action/optimize #task/state/continue

---

### Script

#### Acts 1: 提交变更

我们将修改后的索引组件和核心应用逻辑添加到 Git 暂存区。

~~~~~act
git_add
packages/stitcher-index/src/stitcher/index/indexer.py
packages/stitcher-application/src/stitcher/app/runners/index.py
packages/stitcher-application/src/stitcher/app/core.py
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
refactor(perf): implement hot-set filtering for reformat_all

This optimization addresses the "Reformat Tax" (218ms/46% of check duration) by making the reformatting phase incremental:

1. Indexer Upgrade: `FileIndexer.index_files` and `IndexRunner.run_build` now return a set of `modified_paths` alongside the status.
2. Targeted Reformatting: `StitcherApp.run_check` now uses the indexing results to filter modules. Only modules that were actually added or updated in the current cycle (the "hot set") are passed to `reformat_all`.
3. Impact: In a "no-change" scenario, `reformat_all` overhead drops from ~218ms to near 0ms, as expensive YAML serialization is completely bypassed for stable files.
~~~~~

### 下一步建议
我们已经消灭了占比 46.8% 的 `reformat` 瓶颈。根据最新的 Profiling 结果，剩下的最大“钉子户”是 **`analyze_paths` (150ms)**。
- 其中 `IndexCheckSubjectAdapter.get_all_symbol_states` 消耗了 136ms。
- 这主要是因为它在为 440 个文件构建状态对象时，无差别地读取了对应的 `.stitcher.yaml` 和 `.json` 签名。
- **下一步目标**：我将为分析器引入“读取避障”逻辑。如果索引记录证明 `.py` 文件未脏，且对应的磁盘资产（yaml/json）的 mtime 也没有变化，我们将跳过其内容加载，直接返回缓存状态。

如果您同意，请告诉我。
