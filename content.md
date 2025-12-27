啊，我明白了。

你的分析是正确的。`stitcher hydrate` 命令之所以报告“未找到可供补水的新文档字符串”，是因为源代码本身就缺少这些 `[缺失]` 条目的文档字符串 (`docstrings`)。`hydrate` 的作用是将在代码中**已经写好**的文档字符串提取到 YAML 文件中，而不是凭空创造文档。

因此，唯一的解决方案是手动为所有缺失的条目编写文档，并修正那些签名不匹配的条目。这是一个比较繁琐的工作，但我会系统地完成它。

我将为 `stitcher check` 报告的每一个问题创建或更新对应的 `.stitcher.yaml` 文件条目。

## [WIP] fix: 手动为所有缺失和变更的符号添加文档

### 错误分析

`stitcher hydrate` 命令无法自动修复问题，其原因是问题的根源在于源代码本身：大量代码符号（类、方法、测试函数等）缺少文档字符串（docstrings）。`hydrate` 工具只能提取已存在的文档，无法生成新的文档。因此，自动化的路径行不通。

此外，一些函数签名已更新（`[变更]`），导致其存储的指纹失效，对应的文档也需要手动审查和更新。

### 用户需求

用户要求我作为开发者，手动审查 `stitcher check` 的输出，并为所有报告了 `[缺失]` 和 `[变更]` 的代码符号，在相应的 `.stitcher.yaml` 文件中编写或更新文档。

### 评论

这是一个必要的文档维护任务，旨在使项目的文档元数据与代码的当前状态完全同步。虽然工作量较大，但对于保证代码库的健康度和可维护性至关重要。我将为每个符号编写简洁且能反映其用途的文档。

### 目标

1.  系统性地遍历 `stitcher check` 输出中的每一个错误和警告。
2.  定位到每个问题对应的 `.stitcher.yaml` 文件。
3.  对于 `[缺失]` 的条目，根据其名称和上下文，编写新的、描述性的文档，并添加到 YAML 文件中。
4.  对于 `[变更]` 的条目，审查其当前实现，更新其在 YAML 文件中的文档以反映最新的功能和签名。
5.  确保所有修改都遵循正确的 YAML 格式。
6.  最终目标是在此计划执行后，`stitcher check` 能够成功通过。

### 基本原理

由于无法自动提取，我将采用手动编辑的方式来解决。我会使用 `patch_file` 指令来向现有的 `.stitcher.yaml` 文件中追加缺失的条目。对于那些可能不存在的 YAML 文件，我将使用 `write_file` 来创建它们。这将是一系列精确的、原子化的文件修改操作，最终将使整个项目的文档覆盖率得到极大提升并恢复同步状态。

### 标签
#intent/fix #flow/ready #priority/high #comp/docs #scope/dx #ai/brainstorm #task/domain/tooling #task/object/documentation #task/action/synchronize #task/state/continue

---

### Script

#### Acts 1: 修复 `pyneedle` 包内的文档缺失

为 `pyneedle` 核心包中缺失文档的符号添加说明。

~~~~~act
patch_file
packages/pyneedle/src/needle/loaders/json_handler.stitcher.yaml
~~~~~
~~~~~yaml.old
"JsonHandler": |-
  Standard handler for .json files.
~~~~~
~~~~~yaml.new
"JsonHandler": |-
  Standard handler for .json files.
"JsonHandler.load": |-
  Loads and parses a .json file.
"JsonHandler.match": |-
  Checks if the handler can process a given file path based on its .json extension.
~~~~~
~~~~~act
write_file
packages/pyneedle/src/needle/runtime.stitcher.yaml
~~~~~
~~~~~yaml
"nexus": |-
  The global, batteries-included Nexus instance for easy, out-of-the-box usage.
~~~~~
~~~~~act
write_file
packages/pyneedle-pointer/src/needle/pointer/__init__.stitcher.yaml
~~~~~
~~~~~yaml
"L": |-
  The global root SemanticPointer instance, used as the entry point for creating all semantic pointers.
~~~~~
~~~~~act
patch_file
packages/pyneedle-spec/src/needle/spec/protocols.stitcher.yaml
~~~~~
~~~~~yaml.old
"SemanticPointerProtocol.__truediv__": |-
  Operator '/': Joins the pointer with a string or another pointer (path-like syntax).
  Example: L.auth / "login" -> L.auth.login
~~~~~
~~~~~yaml.new
"SemanticPointerProtocol.__truediv__": |-
  Operator '/': Joins the pointer with a string or another pointer (path-like syntax).
  Example: L.auth / "login" -> L.auth.login
"T_Pointer": |-
  A TypeVar used for covariant type hinting in the SemanticPointerProtocol.
~~~~~

#### Acts 2: 修复 `stitcher-application` 核心和测试的文档

为应用核心逻辑和相关测试中缺失的条目添加文档。

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/core.stitcher.yaml
~~~~~
~~~~~yaml.old
"StitcherApp.run_strip": |-
  Strips docstrings from all source files.
~~~~~
~~~~~yaml.new
"StitcherApp": |-
  The main application class that orchestrates all Stitcher operations.
"StitcherApp.run_strip": |-
  Strips docstrings from all source files.
~~~~~
~~~~~act
write_file
packages/stitcher-application/tests/test_doc_manager.stitcher.yaml
~~~~~
~~~~~yaml
"MockAdapter": |-
  A mock DocumentAdapter for testing purposes.
"MockAdapter.load": |-
  Mock load implementation.
"MockAdapter.save": |-
  Mock save implementation that captures saved data.
"sample_module_ir": |-
  Provides a sample ModuleDef IR for testing doc extraction.
"test_flatten_module_docs": |-
  Tests that the DocumentManager correctly flattens a ModuleDef IR into a dictionary.
"test_save_docs_for_module": |-
  Tests that the DocumentManager saves docs using its adapter and returns the correct path.
~~~~~

#### Acts 3: 修复 `stitcher-cli` 的文档缺失和签名变更

修正 CLI 命令实现中的文档问题，特别是 `hydrate` 命令签名的变更。

~~~~~act
patch_file
packages/stitcher-cli/src/stitcher/cli/main.stitcher.yaml
~~~~~
~~~~~yaml.old
"hydrate": |-
  Extract new docstrings from source code and merge them into .stitcher.yaml.
"init": |-
  Initialize Stitcher in the current project.
"strip": |-
  Remove docstrings from source files.
~~~~~
~~~~~yaml.new
"app": |-
  The main Typer application instance for the CLI.
"cli_renderer": |-
  The CLI-specific renderer instance used by the message bus.
"hydrate": |-
  Extract new docstrings from source code and merge them into .stitcher.yaml.

  Args:
    strip: If True, remove docstrings from source after successful hydration.
    force: If True, overwrite YAML with source docstrings on conflict.
    reconcile: If True, keep YAML docstrings on conflict.
"init": |-
  Initialize Stitcher in the current project.
"strip": |-
  Remove docstrings from source files.
~~~~~
~~~~~act
patch_file
packages/stitcher-cli/src/stitcher/cli/rendering.stitcher.yaml
~~~~~
~~~~~yaml.old
"CliRenderer": |-
  Renders messages to the command line using Typer for colored output.
~~~~~
~~~~~yaml.new
"CliRenderer": |-
  Renders messages to the command line using Typer for colored output.
"CliRenderer.render": |-
  Renders a message to the console with level-appropriate coloring.
~~~~~

#### Acts 4: 修复 `stitcher-common` 及其测试的文档

为公共模块（特别是消息总线）及其测试添加缺失的文档。

~~~~~act
write_file
packages/stitcher-common/src/stitcher/common/__init__.stitcher.yaml
~~~~~
~~~~~yaml
"bus": |-
  The global singleton MessageBus instance.
"stitcher_loader": |-
  The global singleton FileSystemLoader instance for Stitcher assets.
"stitcher_nexus": |-
  The global singleton OverlayNexus instance for Stitcher.
~~~~~
~~~~~act
patch_file
packages/stitcher-common/src/stitcher/common/messaging/bus.stitcher.yaml
~~~~~
~~~~~yaml.old
"MessageBus.render_to_string": |-
  Resolves a message to a string without sending it to the renderer.
~~~~~
~~~~~yaml.new
"MessageBus": |-
  Coordinates message resolution and rendering.
"MessageBus.__init__": |-
  Initializes the bus with a nexus instance for message lookup.
"MessageBus.error": |-
  Sends an error-level message.
"MessageBus.info": |-
  Sends an info-level message.
"MessageBus.render_to_string": |-
  Resolves a message to a string without sending it to the renderer.
"MessageBus.set_renderer": |-
  Sets the renderer responsible for displaying messages.
"MessageBus.success": |-
  Sends a success-level message.
"MessageBus.warning": |-
  Sends a warning-level message.
~~~~~
~~~~~act
write_file
packages/stitcher-common/tests/test_message_bus.stitcher.yaml
~~~~~
~~~~~yaml
"MockRenderer": |-
  A mock renderer that captures messages instead of printing them.
"MockRenderer.render": |-
  Captures a message for later inspection.
"test_bus_does_not_fail_without_renderer": |-
  Tests that the MessageBus operates without crashing when no renderer is set.
"test_bus_forwards_to_renderer": |-
  Tests that the bus correctly resolves a message ID and forwards the formatted string to the renderer.
"test_bus_identity_fallback": |-
  Tests that the bus falls back to the message ID itself if no template is found.
~~~~~

#### Acts 5: 修复其余工具包的文档缺失

为 `config`, `io`, `scanner`, `spec` 和 `test-utils` 包中大量缺失的文档条目进行补全。

~~~~~act
patch_file
packages/stitcher-config/src/stitcher/config/loader.stitcher.yaml
~~~~~
~~~~~yaml.old
"load_config_from_path": |-
  Finds and loads stitcher config from pyproject.toml, and discovers plugins.
~~~~~
~~~~~yaml.new
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
~~~~~act
patch_file
packages/stitcher-io/src/stitcher/io/adapters/yaml_adapter.stitcher.yaml
~~~~~
~~~~~yaml.old
"YamlAdapter": |-
  Adapter for reading and writing .yaml documentation files.
~~~~~
~~~~~yaml.new
"YamlAdapter": |-
  Adapter for reading and writing .yaml documentation files.
"YamlAdapter.load": |-
  Loads and parses a YAML document file.
"YamlAdapter.save": |-
  Saves data to a YAML document file, ensuring consistent formatting.
~~~~~
~~~~~act
patch_file
packages/stitcher-io/src/stitcher/io/stub_generator.stitcher.yaml
~~~~~
~~~~~yaml.old
"StubGenerator.generate": |-
  Generates the content of a .pyi file from a ModuleDef IR.
~~~~~
~~~~~yaml.new
"StubGenerator": |-
  Generates .pyi stub file content from a ModuleDef IR.
"StubGenerator.generate": |-
  Generates the content of a .pyi file from a ModuleDef IR.
~~~~~
~~~~~act
write_file
packages/stitcher-io/tests/test_document_io.stitcher.yaml
~~~~~
~~~~~yaml
"test_yaml_adapter_block_format_consistency": |-
  Verify that all strings (multiline or single-line) are saved
  using Literal Block Style (|-) for consistency.
"test_yaml_adapter_handles_malformed": |-
  Tests that the adapter returns an empty dict for invalid YAML files.
"test_yaml_adapter_load_non_existent": |-
  Tests that the adapter returns an empty dict for a non-existent file.
"test_yaml_adapter_round_trip": |-
  Tests that data can be saved and loaded back correctly.
~~~~~
~~~~~act
write_file
packages/stitcher-io/tests/test_generator_dunder_all.stitcher.yaml
~~~~~
~~~~~yaml
"test_generate_with_dunder_all": |-
  Tests that the generator correctly includes __all__ in the output.
~~~~~
~~~~~act
write_file
packages/stitcher-io/tests/test_stub_generator.stitcher.yaml
~~~~~
~~~~~yaml
"test_generate_simple_pyi": |-
  A golden test for the stub generator, verifying output for a comprehensive IR.
~~~~~
~~~~~act
patch_file
packages/stitcher-scanner/src/stitcher/scanner/parser.stitcher.yaml
~~~~~
~~~~~yaml.old
"parse_source_code": |-
  Parses Python source code into Stitcher IR.
~~~~~
~~~~~yaml.new
"IRBuildingVisitor": |-
  A LibCST visitor that traverses the AST and builds the Stitcher IR.
"IRBuildingVisitor.leave_ClassDef": |-
  Finalizes a ClassDef and pops it from the scope stack.
"IRBuildingVisitor.visit_AnnAssign": |-
  Visits an annotated assignment (e.g., `x: int = 1`).
"IRBuildingVisitor.visit_Assign": |-
  Visits a standard assignment (e.g., `x = 1`).
"IRBuildingVisitor.visit_ClassDef": |-
  Visits a class definition, creating a new ClassDef IR object.
"IRBuildingVisitor.visit_FunctionDef": |-
  Visits a function definition, creating a new FunctionDef IR object.
"IRBuildingVisitor.visit_Import": |-
  Visits an `import x` statement.
"IRBuildingVisitor.visit_ImportFrom": |-
  Visits a `from x import y` statement.
"_collect_annotations": |-
  Recursively collects all type annotation strings from the module IR.
"_enrich_typing_imports": |-
  Scans used annotations and module structure, then injects necessary
  'typing' imports.
"_has_unannotated_attributes": |-
  Check if any attribute in the module IR lacks an annotation.
"parse_source_code": |-
  Parses Python source code into Stitcher IR.
~~~~~
~~~~~act
patch_file
packages/stitcher-scanner/src/stitcher/scanner/transformer.stitcher.yaml
~~~~~
~~~~~yaml.old
"strip_docstrings": |-
  Removes all docstrings from the source code.
~~~~~
~~~~~yaml.new
"HasBody": |-
  Type alias for CST nodes that have a 'body' attribute.
"InjectorTransformer": |-
  A LibCST transformer to inject docstrings into a source code AST.
"InjectorTransformer._create_docstring_node": |-
  Creates a properly quoted docstring node.
"InjectorTransformer.leave_ClassDef": |-
  Injects a class docstring upon leaving the node.
"InjectorTransformer.leave_FunctionDef": |-
  Injects a function docstring upon leaving the node.
"InjectorTransformer.leave_IndentedBlock": |-
  Pops an indentation level from the stack.
"InjectorTransformer.leave_Module": |-
  Injects a module docstring upon leaving the module node.
"InjectorTransformer.visit_ClassDef": |-
  Pushes the class name onto the scope stack.
"InjectorTransformer.visit_FunctionDef": |-
  Pushes the function name onto the scope stack.
"InjectorTransformer.visit_IndentedBlock": |-
  Pushes an indentation level onto the stack.
"StripperTransformer": |-
  A LibCST transformer to remove docstrings from a source code AST.
"StripperTransformer._is_docstring": |-
  Check if a statement is a standalone string expression (docstring).
"StripperTransformer._process_body": |-
  Removes docstring from body. If body becomes empty, inserts 'pass'.
"StripperTransformer.leave_ClassDef": |-
  Applies body processing to a class definition.
"StripperTransformer.leave_FunctionDef": |-
  Applies body processing to a function definition.
"StripperTransformer.leave_Module": |-
  Applies body processing to a module.
"inject_docstrings": |-
  Injects docstrings from the dictionary into the source code.
"strip_docstrings": |-
  Removes all docstrings from the source code.
~~~~~
~~~~~act
write_file
packages/stitcher-scanner/tests/test_parser_basic.stitcher.yaml
~~~~~
~~~~~yaml
"test_parse_simple_class_with_method": |-
  Tests parsing of a basic class with a method.
"test_parse_simple_function": |-
  Tests parsing of a basic function with arguments and a docstring.
~~~~~
~~~~~act
write_file
packages/stitcher-scanner/tests/test_parser_dunder_all.stitcher.yaml
~~~~~
~~~~~yaml
"test_parse_dunder_all_annotated": |-
  Tests parsing of an annotated `__all__` variable.
"test_parse_dunder_all_complex": |-
  Tests parsing of a complex `__all__` expression.
"test_parse_dunder_all_simple": |-
  Tests parsing of a simple list-based `__all__` variable.
~~~~~
~~~~~act
write_file
packages/stitcher-scanner/tests/test_parser_imports.stitcher.yaml
~~~~~
~~~~~yaml
"test_collect_top_level_imports": |-
  Tests that the parser correctly collects top-level import statements.
"test_detect_typing_in_attributes_and_returns": |-
  Tests that the parser's enrichment logic detects types in various locations.
~~~~~
~~~~~act
write_file
packages/stitcher-scanner/tests/test_transformer.stitcher.yaml
~~~~~
~~~~~yaml
"test_inject_docstrings_basic": |-
  Tests basic injection of a docstring into a function.
"test_inject_docstrings_replacement": |-
  Tests that an existing docstring is correctly replaced.
"test_inject_multiline_handling": |-
  Tests that multi-line docstrings are injected with correct indentation.
"test_inject_nested_fqn": |-
  Tests injection for nested symbols like methods within a class.
"test_strip_class_and_module_docs": |-
  Tests stripping from module, class, and method scopes simultaneously.
"test_strip_docstrings_basic": |-
  Tests basic stripping of a docstring from a function.
~~~~~
~~~~~act
patch_file
packages/stitcher-spec/src/stitcher/spec/models.stitcher.yaml
~~~~~
~~~~~yaml.old
"ModuleDef": |-
  Represents a parsed Python module (a single .py file).
~~~~~
~~~~~yaml.new
"Argument": |-
  Represents a function or method argument.
"Argument.annotation": |-
  The type annotation of the argument.
"Argument.default": |-
  The string representation of the argument's default value.
"Argument.kind": |-
  The kind of argument (e.g., positional, keyword-only).
"Argument.name": |-
  The name of the argument.
"ArgumentKind": |-
  Corresponds to inspect._ParameterKind.
"ArgumentKind.KEYWORD_ONLY": |-
  A keyword-only argument.
"ArgumentKind.POSITIONAL_ONLY": |-
  A positional-only argument.
"ArgumentKind.POSITIONAL_OR_KEYWORD": |-
  A standard positional or keyword argument.
"ArgumentKind.VAR_KEYWORD": |-
  A variable keyword argument (**kwargs).
"ArgumentKind.VAR_POSITIONAL": |-
  A variable positional argument (*args).
"Attribute": |-
  Represents a module-level or class-level variable.
"Attribute.annotation": |-
  The type annotation of the attribute.
"Attribute.docstring": |-
  The docstring associated with the attribute (e.g., via a comment).
"Attribute.name": |-
  The name of the attribute.
"Attribute.value": |-
  The string representation of the attribute's value.
"ClassDef": |-
  Represents a class definition.
"ClassDef.attributes": |-
  A list of attributes defined in the class.
"ClassDef.bases": |-
  A list of base classes.
"ClassDef.decorators": |-
  A list of decorators applied to the class.
"ClassDef.docstring": |-
  The docstring of the class.
"ClassDef.methods": |-
  A list of methods defined in the class.
"ClassDef.name": |-
  The name of the class.
"FunctionDef": |-
  Represents a function or method definition.
"FunctionDef.args": |-
  A list of arguments for the function.
"FunctionDef.compute_fingerprint": |-
  Computes a stable hash of the function signature (excluding docstring).
  Includes: name, args (name, kind, annotation, default), return annotation,
  async status, and static/class flags.
"FunctionDef.decorators": |-
  A list of decorators applied to the function.
"FunctionDef.docstring": |-
  The docstring of the function.
"FunctionDef.is_async": |-
  Flag indicating if the function is async.
"FunctionDef.is_class": |-
  Flag indicating if the function is a classmethod.
"FunctionDef.is_static": |-
  Flag indicating if the function is a staticmethod.
"FunctionDef.name": |-
  The name of the function.
"FunctionDef.return_annotation": |-
  The return type annotation of the function.
"ModuleDef": |-
  Represents a parsed Python module (a single .py file).
"ModuleDef.attributes": |-
  A list of attributes defined at the module level.
"ModuleDef.classes": |-
  A list of classes defined in the module.
"ModuleDef.docstring": |-
  The docstring of the module.
"ModuleDef.dunder_all": |-
  The string representation of the __all__ variable.
"ModuleDef.file_path": |-
  The relative path to the module file.
"ModuleDef.functions": |-
  A list of functions defined at the module level.
"ModuleDef.imports": |-
  A list of import statements found in the module.
~~~~~
~~~~~act
patch_file
packages/stitcher-test-utils/src/stitcher/test_utils/bus.stitcher.yaml
~~~~~
~~~~~yaml.old
"SpyRenderer": |-
  A renderer that captures structured message data.
~~~~~
~~~~~yaml.new
"PatchedMessageBus": |-
  An override of MessageBus to intercept calls before rendering.
"SpyBus": |-
  A test utility to spy on messages sent via the global bus.
"SpyBus.assert_id_called": |-
  Asserts that a message with the given ID was sent.
"SpyBus.get_messages": |-
  Returns all messages captured by the spy.
"SpyBus.patch": |-
  A context manager that patches a target module's `bus` instance
  with this spy instance.
"SpyRenderer": |-
  A renderer that captures structured message data.
"SpyRenderer.record": |-
  Records a semantic message call.
"SpyRenderer.render": |-
  Mock render implementation.
~~~~~

### 下一步建议

我已经为所有报告的问题生成了修复方案。在执行此计划后，所有的 `.stitcher.yaml` 文件都应得到更新。

1.  **验证**: 强烈建议您在执行此计划后，立即再次运行 `stitcher check` 命令。预期结果是它将不再报告任何错误或警告，并以成功的状态退出。
2.  **提交**: 一旦验证通过，您可以创建一个新的 `[COMMIT]` 计划，将所有修改过的 `.stitcher.yaml` 文件提交到版本控制中，以完成这次大规模的文档同步工作。
