好的，我们已经顺利完成了 PEP 561 存根包生成机制的实现，并修复了在此过程中发现的所有集成测试问题。现在的系统已经能够稳定地为复杂 Python 项目生成零配置、标准化的类型包。

我将生成一个 `[COMMIT]` 计划，将这些变更作为完整的逻辑单元提交到仓库。

## [COMMIT] feat: 实现基于 PEP 561 的自动化存根包生成机制

### 用户需求
根据 [RFC-001](提案：基于 PEP 561 的 Stitcher 自动化存根包生成机制 (RFC-001)) 的要求，实现“存根包 (Stub Package)”生成模式。该功能允许开发者在 `pyproject.toml` 中配置 `stub_package` 路径，使 Stitcher 自动构建并维护一个遵循 PEP 561 规范的独立类型包，从而彻底解决 Monorepo 架构中 CLI 工具链的静态解析难题。

### 评论
这是一个具有里程碑意义的特性。它不仅增强了 Stitcher 解决实际工程问题的能力，还确立了 Stitcher 作为一个生产高质量、标准兼容的类型资产的脚手架工具的地位。通过这次重构，我们也优化了 `WorkspaceFactory` 等测试工具，为未来的开发打下了更坚实的基础。

### 目标
1.  提交对 `StitcherConfig` 和配置加载逻辑的修改。
2.  提交新增的 `StubPackageManager` 服务及其在核心应用逻辑中的整合。
3.  提交新增的国际化资产（支持中英双语）。
4.  提交新增的 `stub_package` 端到端集成测试，以及针对现有测试的修复。
5.  提交对 `WorkspaceFactory` 的增强功能。

### 基本原理
我们通过在 `stitcher-application` 层级引入 `StubPackageManager` 实现了关注点分离。在生成流程中，系统能够智能地将物理源文件映射到存根包内的逻辑 `src` 布局中，并自动补充关键的 `py.typed` 标记。这一过程是全自动且幂等的，极大地提升了开发者在处理大型动态代码库时的 DX。

### 标签
#intent/build #flow/ready #priority/high #comp/application #comp/config #concept/stubs #scope/dx #ai/instruct #task/domain/stubs #task/object/pep561-package #task/action/implementation #task/state/end #task/status/completed

---

### Script

#### Acts 1: 提交存根包生成机制相关变更

我们将把所有涉及核心逻辑、配置更新、国际化资产和测试修复的文件添加到暂存区，并创建一个内容详尽的提交。

~~~~~act
git_add
packages/stitcher-config/src/stitcher/config/loader.py
packages/stitcher-config/tests/test_loader.py
packages/stitcher-common/src/stitcher/common/assets/needle/en/generate.json
packages/stitcher-common/src/stitcher/common/assets/needle/zh/generate.json
packages/stitcher-application/src/stitcher/app/services/stub_package_manager.py
packages/stitcher-application/src/stitcher/app/services/__init__.py
packages/stitcher-application/src/stitcher/app/core.py
packages/stitcher-test-utils/src/stitcher/test_utils/workspace.py
tests/integration/test_end_to_end.py
tests/integration/test_stub_package.py
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
feat: implement automated PEP 561 stub package generation

Introduces a new generation mode that automatically scaffolds and maintains a compliant Python stub package (e.g., '[project]-stubs').

Key changes:
- Extended 'StitcherConfig' with 'stub_package' configuration option.
- Implemented 'StubPackageManager' to handle directory scaffolding and 'pyproject.toml' metadata generation for the stub package.
- Updated 'StitcherApp._generate_stubs' to support outputting .pyi files into the 'src/' directory of the stub package, ensuring correct logical path mapping.
- Automatically creates 'py.typed' marker files in top-level package directories to comply with PEP 561.
- Updated config loading to extract 'project.name' for naming the stub package.
- Enhanced 'WorkspaceFactory' with 'with_project_name' and improved TOML writing support.
- Added a comprehensive end-to-end integration test for the stub package mode.

This feature allows projects with complex or dynamic layouts to provide zero-config type resolution for static analysis tools like Pyright and MyPy.
~~~~~

### 下一步建议
- **内部自举 (Dogfooding)**: 既然我们已经实现了这个强大的功能，我建议立即在 `stitcher-python` 本身中使用它。我们可以更新根目录下的 `pyproject.toml`，将 `stub_path = "typings"` 替换为 `stub_package = "packages/stitcher-stubs"`，然后运行 `stitcher generate`。
- **版本管理优化**: 目前存根包的版本硬编码为 `0.1.0`。在接下来的迭代中，我们可以让它自动同步主包的版本号。
- **README 更新**: 应该编写一个简短的指南，告诉用户如何通过 `pip install -e` 安装生成的存根包，以开启“上帝视角”的开发体验。
