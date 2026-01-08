太棒了。通过将存根生成重构为“骨架生成 + CST 注入”的两阶段模式，我们彻底解决了困扰系统的缩进和空行格式化问题，同时也极大地增强了架构的健壮性。

我将生成一个 `[COMMIT]` 计划，将这些关键变更正式提交到代码库。

## [COMMIT] refactor: 重构存根生成为两阶段模式并修复文档格式

### 用户需求
完成存根生成逻辑的架构重构，使其采用“骨架生成 -> 文档渲染 -> CST 注入”的模式，并解决生成的文档字符串中空行带有冗余缩进空格的问题。

### 评论
这次重构是架构上的重要进步。我们不再依赖脆弱的字符串拼接逻辑，而是利用 LibCST 的形式化能力来保证生成的 `.pyi` 文件的语法和排版准确性。这符合 HFEA 中“正规军”工程标准的要求。

### 目标
1.  提交 `GenerateRunner`、`StitcherApp` 和 `StubGenerator` 的重构代码。
2.  提交 `GoogleDocstringRenderer` 关于语义缩进的修复。
3.  提交 `format_docstring` 关于空行空格消除的修复。

### 基本原理
通过解耦结构的生成与内容的填充，我们成功地将复杂的缩进逻辑委托给了 LibCST 处理器。这种分层处理不仅解决了当前的格式化 bug，也使得 `GenerateRunner` 能够更灵活地适配不同的文档渲染风格，甚至在未来支持用户自定义的存根生成器。

### 标签
#intent/refine #flow/ready #priority/high #comp/runtime #comp/common #comp/adapter #concept/codegen #scope/core #ai/delegate #task/domain/testing #task/object/docstring-generation #task/action/refactor #task/state/end #task/status/completed

---

### Script

#### Acts 1: 提交重构与修复变更

我们将所有涉及此次架构升级和 Bug 修复的文件添加到 Git 暂存区并提交。

~~~~~act
git_add
packages/stitcher-application/src/stitcher/app/runners/generate.py
packages/stitcher-application/src/stitcher/app/core.py
packages/stitcher-python-adapter/src/stitcher/adapter/python/internal/stub_generator.py
packages/stitcher-python-adapter/src/stitcher/adapter/python/generator.py
packages/stitcher-python-adapter/src/stitcher/adapter/python/docstring/renderers.py
packages/stitcher-common/src/stitcher/common/formatting.py
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
refactor: implement two-phase stub generation and fix docstring formatting

This commit implements a major architectural refactoring of the .pyi stub generation process, shifting from a fragile string-concatenation approach to a robust two-phase strategy:

1. Skeleton Generation: The StubGenerator now produces a clean, document-free Python skeleton (e.g., 'def foo(): ...').
2. CST Injection: The GenerateRunner coordinates the rendering of docstrings via the Renderer and uses LibCST (via Transformer.inject) to insert them into the skeleton.

This change ensures that all indentation, block structures, and line breaks are handled by a formal syntax model, eliminating a whole category of formatting bugs.

Additionally:
- Fixed 'format_docstring' to prevent injecting trailing whitespace on empty lines within docstrings.
- Updated 'GoogleDocstringRenderer' to provide correct 4-space semantic indentation for Args/Returns sections.
- Updated 'GenerateRunner' and 'StitcherApp' to coordinate the new workflow.

Verified by integration tests for Google-style docstring generation.
~~~~~

### 下一步建议

- **基准测试**: 既然引入了 LibCST 后处理，建议在包含大量函数的大型模块上测试生成速度，确认性能损耗在可接受范围内。
- **扩展存根支持**: 可以尝试使用第三方工具（如 mypy 的 `stubgen`）生成的存根作为输入，验证我们的 `GenerateRunner` 注入逻辑的通用性。
- **文档更新**: 既然架构发生了重大变化，建议更新项目内部的技术设计文档，明确说明存根生成的两阶段流程。
