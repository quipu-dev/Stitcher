好的，所有的代码迁移和元数据找回工作已经完成。现在我们将这些变更打包成一个完整的逻辑单元并提交到仓库。

## [COMMIT] refactor(pyneedle): 将 nexus 包合并到 runtime 中

### 用户需求
将 `pyneedle-nexus` 包的功能合并到 `pyneedle-runtime` 中，简化项目结构，并确保所有元数据文件完整迁移。

### 评论
这次重构不仅减少了项目中的包数量，还通过合并 `OverlayOperator` 到 `runtime` 中增强了运行时的核心能力。同时，纠正了迁移过程中遗漏元数据的问题，确保了系统的语义完整性。

### 目标
1.  提交所有文件迁移和路径更新的变更。
2.  确保 `pyneedle-nexus` 包被彻底从版本控制和物理路径中移除。

### 基本原理
我们将把当前工作区中所有关于此次重构的变更（包括 Python 代码、YAML 元数据、项目配置文件）添加到暂存区，并创建一个描述详尽的 Git 提交。

### 标签
#intent/refine #flow/ready #priority/high #comp/runtime #comp/build #scope/core #ai/instruct #task/domain/architecture #task/object/package-structure #task/action/refactor #task/state/end #task/status/completed

---
### Script

#### Acts 1: 提交重构变更

我们将所有变更添加到 Git，并提交。

~~~~~act
git_add
packages/pyneedle/pyproject.toml
packages/pyneedle/src/needle/__init__.py
packages/pyneedle-runtime/pyproject.toml
packages/pyneedle-runtime/src/needle/operators/__init__.py
packages/pyneedle-runtime/src/needle/operators/overlay_operator.py
packages/pyneedle-runtime/src/needle/operators/overlay_operator.stitcher.yaml
packages/pyneedle-runtime/src/needle/runtime.py
packages/pyneedle-runtime/tests/test_overlay_operator.py
packages/pyneedle-runtime/tests/test_overlay_operator.stitcher.yaml
packages/pyneedle-runtime/tests/test_nexus.stitcher.yaml
packages/pyneedle-runtime/tests/test_pipeline_integration.py
packages/stitcher-common/src/stitcher/common/__init__.py
pyproject.toml
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
refactor(pyneedle): merge nexus package into runtime

- Relocated OverlayOperator from 'pyneedle-nexus' to 'pyneedle-runtime'.
- Updated all import references in the codebase (runtime, stitcher-common, etc.).
- Migrated all associated .stitcher.yaml metadata files to their new locations.
- Removed 'pyneedle-nexus' from dependencies in pyproject.toml and workspace configurations.
- Deleted the 'packages/pyneedle-nexus' directory.

This simplification reduces package boilerplate and increases the cohesion of the runtime's operator set.
~~~~~

### 下一步建议
重构已正式提交。建议执行 `uv sync` 来更新锁文件并确保本地环境与新的项目结构完全同步。
