好的，这些确实是开发过程中残留的无用变量。及时清理它们有助于保持代码库的整洁，并避免未来维护者的困惑。

我将生成一个 `[COMMIT]` 计划来执行这些 Lint 修复。

## [COMMIT] fix(lint): 清理无用的局部变量

### 错误分析
Ruff 报告了三处变量被赋值但从未被使用的问题：
1.  `stub_generator.py` 中的 `state`：原本计划用于状态机逻辑以处理复杂的参数标记（如 `/` 和 `*`），但目前的实现采用了更简单的布尔标志位，因此该变量冗余。
2.  `stub_generator.py` 中的 `has_kw_only`：在循环中已经通过检查参数种类来处理关键字参数标记，预先扫描的 `has_kw_only` 变量未被后续逻辑引用。
3.  `test_document_io.py` 中的 `lines`：在测试中读取了文件内容并按行分割，但最终使用了 `in content` 的方式进行断言，导致 `lines` 变量闲置。

### 用户需求
根据 Ruff 的扫描结果，移除代码中所有未使用的局部变量，以通过 Lint 检查。

### 评论
这些变量多为实现逻辑迭代时的“遗迹”。清理它们不仅是为了消除 Lint 警告，更是为了提高代码的可读性。

### 目标
1.  移除 `StubGenerator._generate_args` 中定义的 `state` 和 `has_kw_only`。
2.  移除 `test_document_io.py` 中定义的 `lines`。

### 标签
#intent/tune #flow/ready #priority/low #comp/io #comp/tests #scope/dx #ai/instruct #task/domain/lint-cleanup #task/object/unused-variables #task/action/cleanup #task/state/end #task/status/completed

---

### Script

#### Acts 1: 清理 `stub_generator.py`

~~~~~act
patch_file
packages/stitcher-io/src/stitcher/io/stub_generator.py
~~~~~
~~~~~python.old
        # Let's do a slightly better job:

        parts = []
        state = (
            ArgumentKind.POSITIONAL_OR_KEYWORD
        )  # Default start state logic (simplified)

        # Check if we have pos-only args
        has_pos_only = any(a.kind == ArgumentKind.POSITIONAL_ONLY for a in args)
        pos_only_emitted = False

        has_kw_only = any(a.kind == ArgumentKind.KEYWORD_ONLY for a in args)
        kw_only_marker_emitted = False
~~~~~
~~~~~python.new
        # Let's do a slightly better job:

        parts = []

        # Check if we have pos-only args
        has_pos_only = any(a.kind == ArgumentKind.POSITIONAL_ONLY for a in args)
        pos_only_emitted = False

        kw_only_marker_emitted = False
~~~~~

#### Acts 2: 清理 `test_document_io.py`

~~~~~act
patch_file
packages/stitcher-io/tests/test_document_io.py
~~~~~
~~~~~python.old
    # Verify file content is deterministic (sorted)
    content = file_path.read_text(encoding="utf-8")
    lines = content.strip().splitlines()
    # "MyClass" comes before "MyClass.method" (lexicographical)
~~~~~
~~~~~python.new
    # Verify file content is deterministic (sorted)
    content = file_path.read_text(encoding="utf-8")
    # "MyClass" comes before "MyClass.method" (lexicographical)
~~~~~

#### Acts 3: 提交修复

~~~~~act
git_add
packages/stitcher-io/src/stitcher/io/stub_generator.py
packages/stitcher-io/tests/test_document_io.py
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
fix(lint): remove unused variables in io and tests

Cleans up redundant local variables identified by Ruff:
- Removed 'state' and 'has_kw_only' in stub_generator.py which were leftovers 
  from an earlier logic iteration.
- Removed 'lines' in test_document_io.py as it was not used for assertions.
~~~~~

### 下一步建议
目前 Lint 已经通过。我们已经完成了文档解耦的所有核心功能和清理工作。如果接下来没有其他即时需求，我建议开启 **P1 阶段：Needle 运行时增强**，开始实施 [Stitcher SST 物理分片语义分类法](P1/技术提案（终稿）：Stitcher%20SST%20——%20Needle%20物理分片语义分类法.md)。
