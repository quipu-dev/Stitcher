好的，测试通过意味着我们的重构是稳健的。现在我们将这些更改作为一个逻辑单元进行提交。

## [COMMIT] refactor: 统一资产路径解析逻辑至 stitcher-common

### 用户需求
在验证重构逻辑正确无误后，将所有相关更改提交到 Git 仓库。

### 评论
这次重构成功消除了 `stitcher-application` 和 `stitcher-refactor` 之间关于文件系统布局知识的重复。通过引入 `AssetPathResolver`，我们为未来的存储架构演进（例如支持不同的 Sidecar 存储策略）打下了坚实的基础。

### 目标
1.  将所有受影响的文件添加到 Git 暂存区。
2.  创建一个描述清晰的提交记录。

### 基本原理
遵循 `d3-constraint-quipu-plan-script-rules-D3-P2` 协议，我们将文件修改与 Git 提交隔离在不同的计划中。这是一个纯粹的提交操作。

### 标签
#intent/refine #flow/ready #priority/medium #comp/common #comp/runtime #comp/refactor #scope/core #ai/instruct #task/domain/storage #task/object/asset-path-resolver #task/action/refactor #task/state/end

---

### Script

#### Acts 1: 提交更改

我们将新创建的服务文件以及受影响的管理器文件全部添加到暂存区并提交。

~~~~~act
git_add
packages/stitcher-common/src/stitcher/common/services/asset_path_resolver.py
packages/stitcher-common/src/stitcher/common/services/asset_path_resolver.stitcher.yaml
packages/stitcher-common/src/stitcher/common/services/__init__.py
packages/stitcher-application/src/stitcher/app/services/doc_manager.py
packages/stitcher-application/src/stitcher/app/services/signature_manager.py
packages/stitcher-refactor/src/stitcher/refactor/sidecar/manager.py
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
refactor: unify asset path resolution in AssetPathResolver

Introduced a centralized AssetPathResolver service in stitcher-common to manage
the mapping between source files and their corresponding sidecars (.stitcher.yaml
and .json signatures).

- Created AssetPathResolver in stitcher-common/services.
- Refactored DocumentManager and SignatureManager in stitcher-application to use the common resolver.
- Refactored SidecarManager in stitcher-refactor as a proxy to the common resolver.

This eliminates hardcoded path logic across packages and provides a single
source of truth for the project's filesystem layout.
~~~~~

### 下一步建议
- **清理与优化**: 既然 `SidecarManager` 已经变成了 `AssetPathResolver` 的简单代理，我们可以考虑在未来的重构中直接在 `stitcher-refactor` 中使用 `AssetPathResolver` 并废弃 `SidecarManager`。
- **扩展解析器**: 如果未来有新的资产类型（如性能分析数据、覆盖率报告），应优先考虑在 `AssetPathResolver` 中定义其路径映射规则。
