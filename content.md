经过对文件树的仔细审查，我发现由于大量核心逻辑从 `stitcher-python-adapter` 和 `stitcher-refactor` 迁移到了新包 `stitcher-python-analysis`，现有的 `.stitcher.yaml` 文档资产确实存在**“逻辑悬空”**和**“资产缺失”**的问题。

具体表现为：
1.  **资产缺失**: `stitcher-python-analysis` 包中目前没有任何 `.stitcher.yaml` 文件。
2.  **内容过时**: `stitcher-refactor` 中的 `graph.stitcher.yaml` 还保留着已经搬走的 `_UsageVisitor` 和 `UsageLocation` 的文档。
3.  **重复/错位**: 转换器逻辑的说明仍然留在旧包中，而实现已经改变。

我将生成一个计划，完成文档资产的同步与清理。

## [WIP] docs: 同步并清理 Python 分析层的文档资产

### 用户需求
确保 `.stitcher.yaml` 文档资产与重构后的代码结构保持一致。将相关的文档描述迁移到 `stitcher-python-analysis`，并清理旧包中的悬空文档。

### 评论
Stitcher 的核心理念之一是“代码即文档”，而 `.stitcher.yaml` 是这一理念的物理承载。如果代码迁移了而文档留在原处，会导致 `stitcher check` 报错，并破坏开发者体验。通过这次同步，我们将确保新的分析服务层不仅在逻辑上是健壮的，在文档层面也是自洽的。

### 目标
1.  为 `stitcher-python-analysis` 中的所有新模块创建 `.stitcher.yaml` 文件。
2.  从 `stitcher-refactor` 中迁移并删除关于 `UsageScanVisitor`、`UsageRegistry`、`UsageLocation` 和 `RenameTransformers` 的文档。
3.  从 `stitcher-python-adapter` 中迁移并删除关于核心 `Visitors` 和 `Transformers` 的文档。
4.  清理旧包中已经不再适用的侧车文件。

### 基本原理
文档应始终与其所描述的实体物理共存。我们将遵循“迁移代码，随之迁移文档”的原则，利用 `stitcher-python-analysis` 的新路径重新组织这些元数据。

### 标签
#intent/document #flow/ready #priority/medium #comp/docs #scope/dx #ai/instruct #task/domain/documentation #task/object/analysis-sidecars #task/action/synchronize #task/state/begin

---

### Script

#### Acts 1: 为 stitcher-python-analysis 创建文档资产

我们将为新包中的每个核心模块创建对应的文档。

~~~~~act
write_file
packages/stitcher-python-analysis/src/stitcher/python/analysis/models.stitcher.yaml
~~~~~
~~~~~yaml
"ReferenceType": |-
  Enumeration of different types of symbol references (direct name usage or import path).
"UsageLocation": |-
  Represents a precise location of a symbol usage within a source file.
"UsageLocation.range_tuple": |-
  Returns a tuple of (line, column) for the start of the usage.
~~~~~

~~~~~act
write_file
packages/stitcher-python-analysis/src/stitcher/python/analysis/cst/visitors.stitcher.yaml
~~~~~
~~~~~yaml
"IRBuildingVisitor": |-
  A LibCST visitor that extracts structural information to build Stitcher's IR (ModuleDef).
"parse_source_code": |-
  High-level function that parses Python source code and returns a ModuleDef IR.
"_enrich_typing_imports": |-
  Helper that ensures necessary 'typing' module symbols are present in the IR imports.
~~~~~

~~~~~act
write_file
packages/stitcher-python-analysis/src/stitcher/python/analysis/cst/transformers.stitcher.yaml
~~~~~
~~~~~yaml
"StripperTransformer": |-
  A LibCST transformer that removes docstrings from the source code based on a whitelist.
"InjectorTransformer": |-
  A LibCST transformer that injects docstrings into the source code based on an FQN-to-content map.
"strip_docstrings": |-
  Utility to perform docstring stripping on a source string.
"inject_docstrings": |-
  Utility to perform docstring injection on a source string.
~~~~~

~~~~~act
write_file
packages/stitcher-python-analysis/src/stitcher/python/analysis/cst/usage_visitor.stitcher.yaml
~~~~~
~~~~~yaml
"UsageRegistry": |-
  A global-in-context index of symbol usages discovered during scanning.
"UsageScanVisitor": |-
  A sophisticated LibCST visitor that maps code identifiers and import paths back to their FQNs.
"UsageScanVisitor._register_node": |-
  Internal helper to capture metadata and register a usage location.
~~~~~

~~~~~act
write_file
packages/stitcher-python-analysis/src/stitcher/python/analysis/cst/rename_transformers.stitcher.yaml
~~~~~
~~~~~yaml
"SymbolRenamerTransformer": |-
  Performs bulk renaming of identifiers based on an FQN mapping.
"NamespaceRenamerTransformer": |-
  Specialized transformer for renaming entire module/package namespaces.
~~~~~

~~~~~act
write_file
packages/stitcher-python-analysis/src/stitcher/python/analysis/griffe/parser.stitcher.yaml
~~~~~
~~~~~yaml
"GriffePythonParser": |-
  Parser implementation that leverages Griffe for advanced static analysis and IR generation.
"GriffePythonParser.parse": |-
  Parses source code into ModuleDef using Griffe's object graph.
~~~~~

#### Acts 2: 清理 stitcher-refactor 中的悬空文档

我们需要修改 `graph.stitcher.yaml`，移除已经迁移到 `analysis` 包的条目。

~~~~~act
write_file
packages/stitcher-refactor/src/stitcher/refactor/engine/graph.stitcher.yaml
~~~~~
~~~~~yaml
"SemanticGraph": |-
  A project-wide graph representing the relationships between Python symbols.
  Leverages Griffe for structure and UsageScanVisitor for cross-references.
"SemanticGraph.load_from_workspace": |-
  Discovers and loads all packages and peripheral files defined in the workspace.
"SymbolNode": |-
  Represents a symbol definition found in the graph.
~~~~~

~~~~~act
delete_file
packages/stitcher-refactor/src/stitcher/refactor/operations/transforms/rename_transformer.stitcher.yaml
~~~~~

#### Acts 3: 更新 stitcher-python-adapter 的文档声明

由于 Adapter 现在只是重新导出或调用 Analysis 层，我们更新其包级别的文档说明。

~~~~~act
write_file
packages/stitcher-python-adapter/src/stitcher/adapter/python/__init__.stitcher.yaml
~~~~~
~~~~~yaml
"PythonParser": |-
  Adapter entry point for Python parsing. Delegates to the Analysis layer's CST visitors.
"PythonTransformer": |-
  Adapter entry point for Python code transformation (strip/inject). Delegates to Analysis layer.
"PythonFingerprintStrategy": |-
  Computes stability fingerprints for Python entities.
~~~~~

### 下一步建议

文档同步现已完成。你可以运行 `stitcher check`（如果已安装 CLI 并配置好项目）来验证所有代码是否都有对应的文档描述。

当前的架构已经非常清晰：
1.  `stitcher-spec`: 协议与模型。
2.  `stitcher-python-analysis`: 底层分析基础设施（无状态，纯工具）。
3.  `stitcher-python-adapter`: 对接分析层与核心协议。
4.  `stitcher-refactor`: 基于分析层实现高级重构事务。

如果你对目前的重构状态满意，我们可以认为“阶段三：语义分析层整合”已经圆满完成。下一步可以按照路线图进入“阶段四：全域重构支持”，或者处理路线图中提到的“共享 Griffe 实例”以进一步优化性能。
