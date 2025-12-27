这是一个典型的“签名变更”导致的检查失败，正好验证了我们 `SignatureManager` 的作用。在将配置模型从单一对象更改为列表的过程中，有几个函数和数据类的签名发生了变化，但它们对应的文档（`.stitcher.yaml` 文件）没有同步更新。

根据 `d3-principle-quipu-plan-template-mandatory` 规则，处理 `fix` 类型的任务时，我们通常需要先进行错误分析。由于这里是 API 签名更改导致的文档不一致，解决方案是运行 `stitcher hydrate --strip --reconcile` 来自动修复所有缺失和冲突的文档。

**但是**，在本次任务中，我们处于一个特殊的自举阶段，如果我运行 `stitcher hydrate`，它将修改我们的源代码，并可能引入新的冲突。我们现在的目标是先完成存根生成，再处理代码中的文档剥离。

我将跳过 `hydrate`，直接打补丁来更新 `*.stitcher.yaml` 文件中的签名。

## [WIP] fix(docs): 修复签名变更导致的文档不一致

### 错误分析

`stitcher check` 报告的错误全部源于上一步的架构重构：

1.  **`StitcherApp._get_files_from_config` (core.py)**: 旧签名为 `_get_files_from_config(self, config)`，在重构后，`config` 现在是 `StitcherConfig` 类型，并且它被用于多目标的遍历，导致签名哈希改变。
2.  **`load_config_from_path` (loader.py)**: 旧签名返回 `Tuple[StitcherConfig, Optional[str]]`，新签名返回 `Tuple[List[StitcherConfig], Optional[str]]`，导致签名不匹配。
3.  **`StitcherConfig` 属性缺失**: 增加了 `name`, `stub_path`, `stub_package` 属性，它们在代码中拥有 Docstring（或属性注释），但其对应的文档键（如 `StitcherConfig.name`）在 `loader.stitcher.yaml` 中缺失。
4.  **`WorkspaceFactory.with_project_name` (workspace.py)**: 这个方法是在测试套件重构时新增的，但其文档在 `workspace.stitcher.yaml` 中缺失。

解决方案是手动更新相应的 `.stitcher.yaml` 文件，以确保代码和文档之间的签名（和存在性）保持一致。

### 目标
1.  更新 `packages/stitcher-application/src/stitcher/app/core.stitcher.yaml` 中的 `_get_files_from_config` 文档。
2.  更新 `packages/stitcher-config/src/stitcher/config/loader.stitcher.yaml` 中的 `load_config_from_path` 文档，并添加所有缺失的 `StitcherConfig` 属性文档。
3.  更新 `packages/stitcher-test-utils/src/stitcher/test_utils/workspace.stitcher.yaml`，添加缺失的 `WorkspaceFactory.with_project_name` 文档。

### 基本原理
为了通过 `stitcher check`，我们必须使 `source_docs`（来自代码）与 `yaml_docs`（来自文件）保持同步。由于本次变更主要是签名级的，文档内容可能只需要微调，而缺失的属性文档则必须被添加。

### 标签
#intent/fix #flow/ready #priority/high #comp/docs #comp/config #comp/application #comp/tests #scope/core #ai/instruct #task/domain/documentation #task/object/docstring-sync #task/action/synchronize #task/state/continue

---
### Script

#### Acts 1: 修复 `stitcher-application/core.stitcher.yaml`

更新 `_get_files_from_config` 的描述。

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/core.stitcher.yaml
~~~~~
~~~~~yaml.old
"StitcherApp._derive_logical_path": |-
  Heuristic to derive the logical import path from a physical file path.
  Assumes a standard 'src/' layout.
  e.g., 'packages/pkg-a/src/foo/bar.py' -> 'foo/bar.py'
"StitcherApp._generate_stubs": |-
  Generates .pyi files from a list of ModuleDefs.
"StitcherApp._get_files_from_config": |-
  Helper to discover all source files based on config.
"StitcherApp._process_plugins": |-
~~~~~
~~~~~yaml.new
"StitcherApp._derive_logical_path": |-
  Heuristic to derive the logical import path from a physical file path.
  Assumes a standard 'src/' layout.
  e.g., 'packages/pkg-a/src/foo/bar.py' -> 'foo/bar.py'
"StitcherApp._generate_stubs": |-
  Generates .pyi files from a list of ModuleDefs.
"StitcherApp._get_files_from_config": |-
  Helper to discover all source files based on a single StitcherConfig object.
"StitcherApp._process_plugins": |-
~~~~~

#### Acts 2: 修复 `stitcher-config/loader.stitcher.yaml`

添加缺失的属性文档，并更新 `load_config_from_path` 的描述以反映其返回列表的变化。

~~~~~act
patch_file
packages/stitcher-config/src/stitcher/config/loader.stitcher.yaml
~~~~~
~~~~~yaml.old
"_find_plugins": |-
  Scans the entire workspace for stitcher plugins in pyproject.toml files.
"_find_pyproject_toml": |-
  Traverse upwards to find pyproject.toml.
"StitcherConfig": |-
  Dataclass representing the [tool.stitcher] configuration.
"StitcherConfig.plugins": |-
  A dictionary of discovered plugins.
"StitcherConfig.scan_paths": |-
  A list of paths to scan for source files.
"_find_plugins": |-
  Scans the entire workspace for stitcher plugins in pyproject.toml files.
"_find_pyproject_toml": |-
  Traverse upwards to find pyproject.toml.
"load_config_from_path": |-
  Finds and loads stitcher config from pyproject.toml, and discovers plugins.
~~~~~
~~~~~yaml.new
"_find_plugins": |-
  Scans the entire workspace for stitcher plugins in pyproject.toml files.
"_find_pyproject_toml": |-
  Traverse upwards to find pyproject.toml.
"StitcherConfig": |-
  Dataclass representing the [tool.stitcher] configuration.
"StitcherConfig.name": |-
  The target name (e.g., 'stitcher-python') used for multi-target configuration. Defaults to 'default'.
"StitcherConfig.plugins": |-
  A dictionary of discovered plugins.
"StitcherConfig.scan_paths": |-
  A list of paths to scan for source files.
"StitcherConfig.stub_package": |-
  The path (relative to root) to the dedicated PEP 561 stub package directory (e.g., 'stubs').
"StitcherConfig.stub_path": |-
  The path (relative to root) where .pyi files should be generated (e.g., 'typings'). Mutually exclusive with stub_package.
"load_config_from_path": |-
  Finds and loads stitcher configuration from pyproject.toml, handling both single-target and multi-target modes. Returns a list of configurations.
~~~~~

#### Acts 3: 修复 `stitcher-test-utils/workspace.stitcher.yaml`

添加 `WorkspaceFactory.with_project_name` 的文档。

~~~~~act
patch_file
packages/stitcher-test-utils/src/stitcher/test_utils/workspace.stitcher.yaml
~~~~~
~~~~~yaml.old
"WorkspaceFactory.with_config": |-
  Adds/Updates [tool.stitcher] section in pyproject.toml.
"WorkspaceFactory.with_docs": |-
  Adds a .stitcher.yaml documentation file.
~~~~~
~~~~~yaml.new
"WorkspaceFactory.with_config": |-
  Adds/Updates [tool.stitcher] section in pyproject.toml.
"WorkspaceFactory.with_docs": |-
  Adds a .stitcher.yaml documentation file.
"WorkspaceFactory.with_project_name": |-
  Sets the [project].name in pyproject.toml.
~~~~~

### 下一步建议
我们已经手动同步了所有签名变更和缺失的属性文档。现在，应该再次运行 `stitcher check` 来验证所有错误是否已被清除。如果 `check` 通过，我们将进入下一个阶段：实际执行存根生成。
