根据 **Stitcher 架构重构路线图** 的阶段二收尾工作，我将使用 `sed` 批量修复代码库中遗留的导入路径，确保所有引用都指向新的 `stitcher-lang-python` 包。

## [WIP] refactor: 批量修复遗留的 Python 适配器导入路径

### 错误分析
由于物理包 `stitcher-python-adapter` 已废弃且代码已迁移至 `stitcher-lang-python`，源代码和测试代码中仍存在大量指向旧命名空间 `stitcher.adapter.python` 的引用。这会导致导入错误或类型解析失败。

### 用户需求
使用 `sed` 工具将所有 `stitcher.adapter.python` 的导入路径更新为 `stitcher.lang.python`。对于 docstring 相关的导入，需指向 `stitcher.lang.python.docstring` 以匹配新的导出结构。

### 评论
这是一项必要的清理工作，确保了重构后的系统在 API 层面的连贯性。通过流式编辑，我们可以快速处理跨包的大量引用。

### 目标
1. 全局替换 `stitcher.adapter.python` 为 `stitcher.lang.python`。
2. 针对特定文件（如 `doc_manager.py` 和相关的测试），确保 docstring 组件从正确的子包中导入。

### 基本原理
直接使用 `sed` 进行流式编辑是最快捷的方法。我们将分两步走：先全局重定向到 `stitcher.lang.python`，然后针对那些未在 `lang.python` 顶级 `__init__.py` 中导出的 docstring 组件进行路径细化。

### 标签
#intent/refine #flow/ready #priority/high
#comp/build #scope/dx
#ai/instruct
#task/domain/language-support
#task/object/stitcher-lang-python
#task/action/cleanup
#task/state/end #task/status/completed

---

### Script

#### Acts 1: 使用 sed 批量更新导入路径

我们将执行一系列 `sed` 命令来修复这些引用。

~~~~~act
run_command
~~~~~
~~~~~
# 1. 全局替换基础路径
grep -rl "stitcher.adapter.python" packages/ | xargs sed -i 's/stitcher.adapter.python/stitcher.lang.python/g'

# 2. 针对 docstring 相关的导出进行路径细化（因为顶级 __init__.py 没导出它们）
sed -i 's/from stitcher.lang.python import get_docstring_codec, get_docstring_serializer/from stitcher.lang.python.docstring import get_docstring_codec, get_docstring_serializer/' packages/stitcher-application/tests/unit/test_doc_manager_strategies.py
sed -i 's/from stitcher.lang.python import RawDocstringParser, RawSerializer/from stitcher.lang.python.docstring import RawDocstringParser, RawSerializer/' packages/stitcher-application/src/stitcher/app/services/doc_manager.py
~~~~~

### 下一步建议
1. **运行校验**：执行 `pytest` 确保所有导入路径均已正确解析且系统功能正常。
2. **代码审查**：检查是否有由于多行导入（括号形式）导致 `sed` 替换不完全的情况，必要时手动微调。
3. **进入阶段三**：此次清理后，阶段二正式结束。下一步将开始 **阶段三：核心服务抽象化**，定义 `IndexStoreProtocol` 等接口。
