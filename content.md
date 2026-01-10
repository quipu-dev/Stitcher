好的，任务 1.3 的开发与测试修复已经全部完成。现在我将生成一个 `[COMMIT]` 计划来提交这些更改。

## [COMMIT] feat(index): 实现具有四阶段增量流水线的 WorkspaceScanner

### 用户需求
完成任务 1.3：实现持久化索引的增量扫描逻辑。

### 评论
这是 Stitcher 2.0 性能架构的基石。通过四阶段流水线（Discovery -> Stat Check -> Hash Check -> Parsing），系统能够以极低的代价跳过未修改的文件，并确保索引状态与物理文件系统保持一致。

### 目标
1.  提交 `WorkspaceScanner` 及其关联的 `LanguageAdapter` 协议。
2.  提交 `IndexStore` 的扩展功能（批量查询与删除）。
3.  提交 `DatabaseManager` 的初始化优化（自动创建 `.gitignore`）。
4.  提交增强后的测试基础设施。

### 基本原理
*   **Git 感知**: 优先使用 `git ls-files` 以尊重用户的 `.gitignore` 配置。
*   **自卫机制**: 自动在 `.stitcher/index/` 创建 `*` 忽略规则，并在扫描时硬编码排除 `.stitcher` 目录，防止无限递归和索引污染。
*   **二进制安全**: 增加对 `UnicodeDecodeError` 的处理，确保扫描器在遇到非文本文件时能够安全跳过。
*   **高效同步**: 引入批量元数据加载，将 Phase 2 的文件比对从 $O(N)$ 次数据库查询优化为 $O(N)$ 次内存哈希查找。

### 标签
#intent/build #flow/ready #priority/critical 
#comp/runtime #comp/tests #concept/state #scope/core 
#ai/instruct 
#task/domain/storage #task/object/stitcher-index #task/action/implementation 
#task/state/end #task/status/completed

---

### Script

#### Acts 1: 提交扫描器核心实现及配套设施

我们将所有涉及的文件添加到 Git 暂存区并创建提交。

~~~~~act
git_add
packages/stitcher-test-utils/src/stitcher/test_utils/workspace.py
packages/stitcher-index/src/stitcher/index/db.py
packages/stitcher-index/src/stitcher/index/store.py
packages/stitcher-index/src/stitcher/index/protocols.py
packages/stitcher-index/src/stitcher/index/scanner.py
packages/stitcher-index/tests/conftest.py
packages/stitcher-index/tests/unit/test_scanner.py
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
feat(index): implement four-phase incremental scanning pipeline

Implemented the `WorkspaceScanner` which serves as the core semantic indexing engine. The scanner executes a robust four-phase pipeline:

1. Discovery: Uses `git ls-files` (falling back to OS walk) to find files, respecting `.gitignore`.
2. Stat Check: Compares mtime and size against the database cache to skip unmodified files instantly.
3. Hash Check: Uses SHA256 content hashing to detect changes that didn't affect file statistics.
4. Parsing: Extracts symbols and references via a pluggable `LanguageAdapter` interface.

Key architectural improvements:
- Added `git init` support to `WorkspaceFactory` for Git-aware integration testing.
- DatabaseManager now automatically creates a `.gitignore` in the index directory to prevent tracking binaries.
- Scanner now explicitly excludes the `.stitcher` system directory to avoid self-referencing loops.
- Improved IndexStore with batch metadata loading for O(1) in-memory lookups during scans.
- Enhanced robustness against binary files and Unicode decoding errors.
~~~~~

### 下一步建议
- **任务 1.4 (即将开始)**: 现在扫描器框架已经就绪，下一步是实现真正的 **PythonAdapter**。我们将把现有的 `stitcher-python-analysis` 逻辑封装进 `LanguageAdapter` 协议，使扫描器能够提取 Python 符号和引用。
- **任务 1.5**: 实现 `stitcher index:build` CLI 命令，让用户能从终端启动扫描。
