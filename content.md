好的，我们已经成功实现了 PythonAdapter 的基本引用提取能力，并修复了 `UsageScanVisitor` 中的重复计数问题。现在我们将这些更改作为一个完整的逻辑单元提交。

## [COMMIT] feat: 实现 PythonAdapter 的基本引用提取能力

### 用户需求
解决技术债务 1.2 "残缺的引用分析 (Incomplete Reference Analysis)"。需要使 `PythonAdapter` 能够提取代码中的符号使用和导入关系。

### 评论
这是构建项目语义图谱的关键一步。通过集成 LibCST 访问器，我们现在可以物理地捕获符号间的连接关系。虽然目前的 SURI 生成是推测性的，但这为后续的精确解析（Debt 1.3）打下了坚实的基础。

### 目标
1.  提交 `PythonAdapter` 中集成 `UsageScanVisitor` 的实现。
2.  提交 `UsageScanVisitor` 中关于动态导入解析和防止重复计数的修复。
3.  包含新增的单元测试用例。

### 基本原理
我们将 `index_adapter.py` 改造为双通解析模式，并在 `usage_visitor.py` 中实现了状态化的符号表维护，确保了引用提取的准确性。

### 标签
#intent/build #flow/ready #priority/medium 
#comp/runtime #comp/tests #concept/history 
#ai/instruct 
#task/domain/indexing #task/object/python-adapter #task/action/reference-analysis 
#task/state/end #task/status/completed

---

### Script

#### Acts 1: 提交引用分析功能实现

我们将相关实现文件和测试文件添加到暂存区并创建提交。

~~~~~act
git_add
packages/stitcher-python-adapter/src/stitcher/adapter/python/index_adapter.py
packages/stitcher-python-analysis/src/stitcher/python/analysis/cst/usage_visitor.py
packages/stitcher-python-adapter/tests/unit/test_index_adapter_references.py
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
feat(adapter): implement basic reference extraction in PythonAdapter

- Integrated 'UsageScanVisitor' into PythonAdapter's indexing pipeline.
- Implemented heuristic-based SURI generation for external and local references.
- Enhanced 'UsageScanVisitor' to dynamically resolve and track imported symbols (aliases, absolute/relative imports).
- Fixed a bug in 'UsageScanVisitor' causing double-registration of symbols in import statements.
- Added unit tests verifying reference extraction for both imports and usages.

This resolves technical debt 1.2 "Incomplete Reference Analysis" by enabling the extraction of semantic edges (usages/imports) alongside symbol definitions.
~~~~~

### 下一步建议
- **解决 Debt 1.1 (符号位置)**: 目前符号和引用的位置信息尚不精确。应增强 `ModuleDef` 以携带 LibCST/Griffe 提供的字节偏移量，从而支持 IDE 的跳转功能。
- **解决 Debt 1.3 (别名解析)**: 当前 SURI 生成是推测性的。需要引入 SourceMap 机制，结合 `__init__.py` 的导出逻辑，实现精确的跨文件引用链接。
