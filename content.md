好的，自动处理 `import` 语句和 `typing` 补全的功能已经验证通过。现在我们将这些增强功能提交到仓库。

## [COMMIT] feat: 增强 Scanner 以支持自动 Import 收集与 Typing 智能补全

### 用户需求
解决生成的 `.pyi` 存根文件因缺失 `import` 语句（尤其是 `typing` 相关类型）而导致类型检查失败的问题。

### 评论
这是提升 `stitcher-python` 易用性的一个重要里程碑。通过自动保留源码中的 `import`（包括 `if TYPE_CHECKING:` 块内的）并根据注解内容自动补全缺失的 `typing` 声明，我们极大地减少了生成存根后手动修补的工作量，使生成的 `.pyi` 文件更加“开箱即用”。

### 目标
1.  提交 `stitcher-scanner` 中 `IRBuildingVisitor` 的更新，使其能够收集 `Import` 和 `ImportFrom` 节点。
2.  提交 `_enrich_typing_imports` 逻辑，实现基于正则的 `typing` 符号自动发现与补全。
3.  提交相关的单元测试用例。

### 基本原理
按照 `[COMMIT]` 规范，本计划仅执行 Git 暂存与提交操作。本次变更通过 LibCST 的访问者模式实现了对源码 Import 语句的零成本搬运，并利用启发式正则扫描注解，实现了对常用 `typing` 符号的智能按需补全。

### 标签
#intent/build #flow/done #priority/high 
#comp/scanner #comp/tests #concept/parser #scope/core
#ai/instruct
#task/domain/dev-tools #task/object/stub-generation #task/action/implementation #task/state/end #task/status/completed

---

### Script

#### Acts 1: 提交 Import 处理增强功能

~~~~~act
git_add
packages/stitcher-scanner/src/stitcher/scanner/parser.py
packages/stitcher-scanner/tests/test_parser_imports.py
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
feat(scanner): add automatic import collection and typing auto-injection

Enhances the scanner to preserve source code imports and ensure generated .pyi 
files are type-compliant by default.

Key changes:
- Updated IRBuildingVisitor to collect 'import' and 'from ... import ...' nodes.
- Implemented automatic flattening of imports found inside 'if TYPE_CHECKING:' blocks.
- Added '_enrich_typing_imports' logic to scan IR annotations and automatically
  inject missing 'from typing import ...' statements for used symbols (List, Optional, etc.).
- Improved 'parse_source_code' to apply these enhancements during the parsing phase.
- Added comprehensive unit tests for import preservation and smart typing injection.

This ensures that generated stubs have the necessary context for IDEs and type 
checkers without manual intervention.
~~~~~

### 下一步建议
- **生命周期管理**: 核心生成能力已基本完备。下一步可以处理支线任务三：实现 `strip` 和 `eject` 命令，完成文档解耦的完整闭环。
- **性能优化**: 考虑引入基于文件哈希或修改时间的缓存机制，以加速大型 Monorepo 项目的扫描与生成过程。
