Of course. Based on our refined analysis, we will now execute the plan to eliminate the true architectural redundancy, thereby strengthening the decoupling between the `analysis` and `adapter` packages.

This action is a direct application of the **Architecture Incorruptibility** principle: any identified architectural smell must be eradicated. A component from a lower-level, pure library (`analysis`) should not implement a protocol from a higher-level, application-specific one (`spec`). By moving the implementation to the `adapter` package, we restore the correct flow of dependencies.

## [WIP] refactor: Relocate GriffePythonParser to adapter package

### 用户需求

根据架构审查，需要彻底消除 `stitcher-python-adapter` 中的冗余代理模块，并将 `GriffePythonParser` 的实现移动到其正确的架构层级，以实现 `analysis` 和 `adapter` 包的真正解耦。

### 评论

这是一个关键的架构重构。`stitcher-python-analysis` 包的价值在于其作为一个**纯粹的、无应用上下文**的代码分析引擎。让它实现一个应用层的 `LanguageParserProtocol` 是一种“向上”依赖，污染了它的纯粹性。

通过将 `GriffePythonParser` 的实现（即协议的适配代码）移动到 `stitcher-python-adapter` 包，我们纠正了这一问题。`analysis` 包回归其纯粹角色，而 `adapter` 包则清晰地承担起连接“纯粹逻辑”与“应用协议”的桥梁作用。

**关于 `parser.py` 和 `transformer.py`**:
经过深入分析，这两个文件中的 `PythonParser` 和 `PythonTransformer` 类并非冗余。它们扮演了重要的**适配器**角色，将 `analysis` 包中的*纯函数*（如 `parse_source_code`）适配为 `stitcher-spec` 中定义的*协议接口*（如 `LanguageParserProtocol`）。因此，它们是 `adapter` 包的核心组成部分，应当予以保留。

### 目标

1.  将 `GriffePythonParser` 类的完整实现从 `stitcher-python-analysis` 包物理移动到 `stitcher-python-adapter` 包。
2.  用移动过来的实现代码覆盖 `stitcher-python-adapter` 中原有的代理模块（`griffe_parser.py`）。
3.  删除 `stitcher-python-analysis` 中遗留的原始文件，确保 `GriffePythonParser` 的实现有且仅有一个真理来源。

### 基本原理

此计划的核心是**物理性地重构代码以匹配逻辑架构**。当前 `GriffePythonParser` 的位置造成了逻辑上的倒置依赖。我们将通过 `write_file` 和 `delete_file` 操作，将代码移动到其本体论上正确的位置（the ontologically correct location），即 `adapter` 包。由于现有的代码库都通过 `stitcher.adapter.python.griffe_parser` 这个路径来导入，我们只需用真实实现替换掉这个路径上的代理模块，即可无缝地完成重构，无需修改任何消费端的代码。

### 标签

#intent/refine #flow/ready #priority/critical #comp/engine #concept/state #scope/core #dx #ai/brainstorm #task/domain/testing #task/object/test-organization #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 将 GriffePythonParser 的实现迁移到 adapter 包

我们将 `analysis` 包中的实现内容写入 `adapter` 包中的 `griffe_parser.py` 文件，用实现替换掉原来的代理。

~~~~~act
write_file
packages/stitcher-python-adapter/src/stitcher/adapter/python/griffe_parser.py
~~~~~
~~~~~python
import ast
from pathlib import Path
from typing import List, cast, Any, Optional
import logging

import griffe
from griffe import AliasResolutionError
from stitcher.spec import (
    ModuleDef,
    LanguageParserProtocol,
    FunctionDef,
    ClassDef,
    Attribute,
    Argument,
    ArgumentKind,
    SourceLocation,
)
from stitcher.python.analysis.cst.visitors import _enrich_typing_imports


class _ImportVisitor(ast.NodeVisitor):
    def __init__(self):
        self.imports: List[str] = []

    def visit_Import(self, node: ast.Import) -> None:
        self.imports.append(ast.unparse(node))

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        self.imports.append(ast.unparse(node))


class GriffePythonParser(LanguageParserProtocol):
    def parse(self, source_code: str, file_path: str = "") -> ModuleDef:
        # 1. Parse into AST
        try:
            tree = ast.parse(source_code)
        except SyntaxError as e:
            raise ValueError(f"Syntax error in {file_path}: {e}") from e

        # 1.5 Extract Imports via AST
        import_visitor = _ImportVisitor()
        import_visitor.visit(tree)
        imports = import_visitor.imports

        # 2. Visit with Griffe
        module_name = file_path.replace("/", ".").replace(".py", "") or "module"
        # Explicit cast to Any to bypass Pyright check if filepath is strict Path
        path_obj = Path(file_path) if file_path else None
        griffe_module = griffe.visit(
            module_name, filepath=cast(Any, path_obj), code=source_code
        )

        # 3. Map to Stitcher IR
        module_def = self._map_module(griffe_module, file_path, imports)

        # 4. Enrich imports
        _enrich_typing_imports(module_def)

        return module_def

    def _map_module(
        self, gm: griffe.Module, file_path: str, imports: List[str]
    ) -> ModuleDef:
        functions = []
        classes = []
        attributes = []

        for member in gm.members.values():
            if member.is_alias:
                attributes.append(self._map_alias(cast(griffe.Alias, member)))
            elif member.is_function:
                functions.append(self._map_function(cast(griffe.Function, member)))
            elif member.is_class:
                classes.append(self._map_class(cast(griffe.Class, member)))
            elif member.is_attribute:
                attributes.append(self._map_attribute(cast(griffe.Attribute, member)))

        docstring = gm.docstring.value if gm.docstring else None

        return ModuleDef(
            file_path=file_path,
            docstring=docstring,
            functions=functions,
            classes=classes,
            attributes=attributes,
            imports=imports,
        )

    def _extract_location(self, obj: griffe.Object) -> Optional[SourceLocation]:
        try:
            # Accessing lineno on an Alias triggers target resolution.
            # If the target is external/unresolvable, this raises AliasResolutionError (or KeyError).
            # We catch specific exceptions to safely degrade to "no location" for unresolvable aliases.
            if obj.lineno:
                # Safely access end_lineno as it might not be present on base Object type
                end_lineno = getattr(obj, "end_lineno", None) or obj.lineno
                return SourceLocation(
                    lineno=obj.lineno,
                    col_offset=0,  # Griffe doesn't provide column
                    end_lineno=end_lineno,
                    end_col_offset=0,
                )
        except (AliasResolutionError, KeyError):
            # This is expected for external imports in single-file mode.
            # We swallow the error and return None for location.
            pass
        except Exception as e:
            # Log unexpected errors but don't crash the scanner
            logging.getLogger(__name__).warning(
                f"Unexpected error extracting location for {obj.name}: {e}"
            )
        return None

    def _map_class(self, gc: griffe.Class) -> ClassDef:
        methods = []
        attributes = []
        for member in gc.members.values():
            if member.is_alias:
                attributes.append(self._map_alias(cast(griffe.Alias, member)))
            elif member.is_function:
                methods.append(self._map_function(cast(griffe.Function, member)))
            elif member.is_attribute:
                attributes.append(self._map_attribute(cast(griffe.Attribute, member)))
        docstring = gc.docstring.value if gc.docstring else None
        bases = [str(b) for b in gc.bases]
        return ClassDef(
            name=gc.name,
            bases=bases,
            decorators=[str(d.value) for d in gc.decorators],
            docstring=docstring,
            attributes=attributes,
            methods=methods,
            location=self._extract_location(gc),
        )

    def _map_attribute(self, ga: griffe.Attribute) -> Attribute:
        annotation = str(ga.annotation) if ga.annotation else None
        value = str(ga.value) if ga.value else None
        docstring = ga.docstring.value if ga.docstring else None
        return Attribute(
            name=ga.name,
            annotation=annotation,
            value=value,
            docstring=docstring,
            location=self._extract_location(ga),
        )

    def _map_alias(self, ga: griffe.Alias) -> Attribute:
        # Alias doesn't have a value or annotation typically, but it has a target path.
        return Attribute(
            name=ga.name,
            alias_target=ga.target_path,
            location=self._extract_location(ga),
        )

    def _map_function(self, gf: griffe.Function) -> FunctionDef:
        args = [self._map_argument(p) for p in gf.parameters]
        return_annotation = str(gf.returns) if gf.returns else None
        docstring = gf.docstring.value if gf.docstring else None
        return FunctionDef(
            name=gf.name,
            args=args,
            return_annotation=return_annotation,
            docstring=docstring,
            is_async="async" in gf.labels,
            decorators=[str(d.value) for d in gf.decorators],
            is_static="staticmethod" in gf.labels,
            is_class="classmethod" in gf.labels,
            location=self._extract_location(gf),
        )

    def _map_argument(self, param: griffe.Parameter) -> Argument:
        kind_map = {
            "positional-only": ArgumentKind.POSITIONAL_ONLY,
            "positional-or-keyword": ArgumentKind.POSITIONAL_OR_KEYWORD,
            "keyword-only": ArgumentKind.KEYWORD_ONLY,
            "variadic positional": ArgumentKind.VAR_POSITIONAL,
            "variadic keyword": ArgumentKind.VAR_KEYWORD,
        }
        st_kind = ArgumentKind.POSITIONAL_OR_KEYWORD
        if param.kind:
            slug = str(param.kind.value)
            st_kind = kind_map.get(slug, ArgumentKind.POSITIONAL_OR_KEYWORD)
        annotation = str(param.annotation) if param.annotation else None
        default = str(param.default) if param.default else None
        return Argument(
            name=param.name, kind=st_kind, annotation=annotation, default=default
        )
~~~~~

#### Acts 2: 移除 analysis 包中的旧实现

现在实现已经安全地迁移到了 `adapter` 包，我们可以放心地删除 `analysis` 包中的原始文件，完成解耦。

~~~~~act
delete_file
packages/stitcher-python-analysis/src/stitcher/python/analysis/griffe/parser.py
~~~~~

### 下一步建议

我们已经成功地将 `GriffePythonParser` 迁移到了其正确的架构位置，并消除了 `stitcher-python-analysis` 包对应用层协议的依赖。这使得我们的架构更加清晰和健壮。

下一步，我建议：
- **审查依赖关系**: 检查 `stitcher-python-analysis/pyproject.toml`，确认 `stitcher-spec` 是否仍然是必需的依赖。如果 `analysis` 包中其他模块（如 `cst/visitors.py`）仍然需要 `stitcher-spec` 中的 IR 模型，那么依赖需要保留。如果不再需要，我们可以将其移除，从而实现更彻底的解耦。
- **运行完整测试**: 执行 `pytest` 全量测试，确保我们的重构没有引入任何回归问题。
