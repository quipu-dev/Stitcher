好的，我将手动为你生成这些文档更新。这不仅能消除 `check` 报告中的文档缺失错误，还能为新重构的类和方法提供高质量的说明。

对于那两个“签名变更（Signature Mismatch）”错误，虽然我可以手动更新 YAML，但为了同步底层的二进制指纹，你最终仍需执行一次 `stitcher check --update-signatures`。

## [WIP] docs: Manually update documentation for FileCheckResult and check command

### 用户需求
手动更新项目文档以匹配最近的重构，而不使用 `hydrate` 自动补水：
1.  为 `FileCheckResult` 类及其所有成员添加详细文档。
2.  更新 `StitcherApp.run_check` 的文档以包含新参数。
3.  更新 CLI 的 `check` 命令文档以包含新选项。

### 评论
手动编写这些文档而非自动补水，可以让我们在文档中加入更具解释性的上下文，这对于 `FileCheckResult` 这样作为系统“成绩单”的核心数据结构尤为重要。通过精确的 YAML 更新，我们将使 `check` 命令的输出重新变得整洁。

### 目标
1.  **新建 `packages/stitcher-application/src/stitcher/app/core.stitcher.yaml`**: 为新引入的 `dataclass` 提供全方位的定义说明。
2.  **更新 `packages/stitcher-cli/src/stitcher/cli/main.stitcher.yaml`**: 完善 `check` 命令的参数说明。

### 基本原理
我们将直接操作 YAML 资源文件。对于新引入的 `core.py` 逻辑，我们将创建一个新的配对文档文件。对于 CLI 接口，我们将使用 `patch_file` 来精确增加 `Args` 描述。

### 标签
#intent/document #flow/ready #priority/high #comp/docs #scope/dx #ai/instruct #task/domain/cli #task/object/documentation #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 为应用核心逻辑创建文档

我们将创建 `core.stitcher.yaml`，详细定义 `FileCheckResult` 的每一个字段，并更新 `run_check` 的语义描述。

~~~~~act
write_file
packages/stitcher-application/src/stitcher/app/core.stitcher.yaml
~~~~~
~~~~~yaml
FileCheckResult: |-
  Data container representing the outcome of a consistency check for a single file.
FileCheckResult.error_count: |-
  Total number of critical issues (errors) discovered in the file.
FileCheckResult.errors: |-
  A collection of errors keyed by their category (e.g., 'conflict', 'mismatch').
FileCheckResult.is_clean: |-
  Returns True if the file has no issues and no reconciliation was performed.
FileCheckResult.path: |-
  The relative path to the source file that was inspected.
FileCheckResult.reconciled: |-
  The count of signature mismatches that were automatically updated during the check.
FileCheckResult.warning_count: |-
  Total number of non-blocking issues (warnings) discovered in the file.
FileCheckResult.warnings: |-
  A collection of warnings keyed by their category (e.g., 'missing', 'untracked').
StitcherApp.run_check: |-
  Verify the structural and content consistency between source code and external YAML documentation.

  Args:
    update_signatures: If True, automatically update the signature baseline for functions that have changed.
~~~~~

#### Acts 2: 更新 CLI 命令文档

我们将更新 `main.stitcher.yaml`，为 `check` 命令增加参数说明。

~~~~~act
patch_file
packages/stitcher-cli/src/stitcher/cli/main.stitcher.yaml
~~~~~
~~~~~yaml.old
"check": |-
  Verify consistency between code and docs.
"eject": |-
~~~~~
~~~~~yaml.new
"check": |-
  Verify consistency between code and docs.

  Args:
    update_signatures: Accept and update signature changes in the stored fingerprints.
"eject": |-
~~~~~

### 下一步建议
手动文档更新完成后，执行 `stitcher check` 应该能看到一个干净的输出（或者仅剩下极少量警告）。

建议随后运行 `stitcher generate` 以确保生成的 `.pyi` 存根也包含了这些最新的详细文档，从而提升 IDE 中的智能感知体验。
