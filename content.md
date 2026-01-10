## [WIP] fix: 修复 Scanner 测试中的文件发现问题

### 错误分析

测试失败是因为 `WorkspaceScanner` 意外地扫描到了测试运行时生成的 `index.db` 文件。

1.  **路径问题**: 在 `conftest.py` 中，`db_path` 被设置为 `tmp_path / "index.db"`（即项目根目录）。
2.  **发现逻辑**: `WorkspaceScanner` 使用 `git ls-files --others`，这会列出所有未被 git 追踪的文件，包括这个新生成的 `index.db`。
3.  **结果偏差**: 因此，所有测试的 `added` 计数都比预期多 1（即 `index.db`）。

### 用户需求

1.  将数据库路径移动到符合架构设计的 `.stitcher/index/index.db`。
2.  在 `WorkspaceScanner` 中增加硬编码过滤，确保永远不会扫描 `.stitcher/` 目录，防止自引用循环。

### 评论

这是一个典型的测试环境与真实环境差异导致的问题，但也暴露了 Scanner 缺乏自我保护机制（防止扫描自身数据）的缺陷。

### 目标

1.  修改 `packages/stitcher-index/tests/conftest.py`，调整 DB 路径。
2.  修改 `packages/stitcher-index/src/stitcher/index/scanner.py`，在发现阶段过滤 `.stitcher` 目录。

### 基本原理

*   **架构一致性**: 生产环境中 DB 位于 `.stitcher/index/`。
*   **防御性编程**: Scanner 应显式忽略系统目录。

### 标签

#intent/fix #flow/ready #priority/high #comp/runtime #concept/state #scope/core #ai/instruct #task/domain/storage #task/object/stitcher-index #task/action/bug-fix #task/state/continue

---

### Script

#### Acts 1: 修正测试配置 (conftest.py)

将数据库路径移至 `.stitcher/index/index.db`。

~~~~~act
patch_file
packages/stitcher-index/tests/conftest.py
~~~~~
~~~~~python.old
@pytest.fixture
def db_path(tmp_path):
    return tmp_path / "index.db"
~~~~~
~~~~~python.new
@pytest.fixture
def db_path(tmp_path):
    return tmp_path / ".stitcher" / "index" / "index.db"
~~~~~

#### Acts 2: 增强扫描器过滤逻辑 (scanner.py)

在 `_discover_files` 中添加对 `.stitcher/` 的过滤。

~~~~~act
patch_file
packages/stitcher-index/src/stitcher/index/scanner.py
~~~~~
~~~~~python.old
                paths.add(rel_path)
        return paths

    def _process_file_content(self, file_id: int, abs_path: Path, content_bytes: bytes):
~~~~~
~~~~~python.new
                paths.add(rel_path)
        
        # Global Filter: Exclude .stitcher directory
        final_paths = {
            p for p in paths 
            if not p.startswith(".stitcher/") and p != ".stitcher"
        }
        return final_paths

    def _process_file_content(self, file_id: int, abs_path: Path, content_bytes: bytes):
~~~~~

### 下一步建议

运行测试以验证修复。如果通过，则继续执行任务 1.4（实现 PythonAdapter）。
