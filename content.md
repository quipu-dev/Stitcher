分析非常准确。虽然我们之前修复了 `get_public_documentable_fqns`（用于 `check` 命令确定缺少文档的项），但我们遗漏了 `get_all_fqns` 和 `is_documentable`。

**为什么 `pump` 会触发这个问题？**

1.  `stitcher pump`（以及 `init`）使用 `ModuleDef.get_all_fqns()` 来决定要为哪些符号计算指纹并保存到 `.stitcher/signatures/` 中。
2.  当前的 `get_all_fqns` **没有过滤别名（Import）**。它将所有导入的符号（如 `Callable`, `Path`）都视为该模块的符号。
3.  因此，`pump` 运行后，它会生成包含这些导入符号的签名文件。
4.  一旦签名文件（`.stitcher/signatures/...json`）中包含了这些符号，`stitcher check`（在后续运行时）或 `pump` 自身的状态检查逻辑就会认为这些符号是该模块的合法组成部分，进而检查它们是否缺少文档。

**此外，`is_documentable` 也有同样的问题**：如果一个文件只包含导入（例如 `__init__.py` 有时只做重导出），当前的 `is_documentable` 会返回 `True`，因为导入被视为 Public Attribute。这会导致不应该被追踪的文件进入系统。

我们需要在 `ModuleDef` 模型中彻底封堵这个漏洞。

## [WIP] fix(spec): Exclude aliases from all ModuleDef symbol discovery methods

### 用户需求

`stitcher pump` 错误地将导入的符号（如 `Callable`, `Path`）包含在签名生成和文档追踪中。这是因为底层的 `ModuleDef.get_all_fqns` 方法没有排除别名。

### 评论

这是彻底解决“导入符号干扰”问题的最后一块拼图。之前的修复只覆盖了 `check` 命令的显示逻辑，而这个修复将纠正系统对“模块包含什么符号”的核心认知，防止污染签名数据库。

### 目标

修改 `packages/stitcher-spec/src/stitcher/spec/models.py`：
1.  更新 `is_documentable`：在判断是否有公共属性时，排除别名。
2.  更新 `get_all_fqns`：在收集所有 FQN 时，排除别名。

### 基本原理

`ModuleDef` 是整个系统的单一事实来源。通过在模型层面上强制过滤掉 `alias_target` 不为空的属性，我们确保了无论是生成签名 (`pump`/`init`) 还是检查文档 (`check`)，所有的下游组件都只会看到真正的本地定义符号。

### 标签

#intent/fix #flow/ready #priority/critical #comp/spec #concept/state #task/domain/core #task/object/module-model #task/action/bug-fix #task/state/end

---

### Script

#### Acts 1: 修正 `ModuleDef` 的剩余方法

~~~~~act
patch_file
packages/stitcher-spec/src/stitcher/spec/models.py
~~~~~
~~~~~python.old
    def is_documentable(self) -> bool:
        # A module is documentable if it has a docstring, or any public
        # attributes, functions, or classes.
        has_public_attributes = any(
            not attr.name.startswith("_") for attr in self.attributes
        )
        has_public_functions = any(
            not func.name.startswith("_") for func in self.functions
        )
        has_public_classes = any(not cls.name.startswith("_") for cls in self.classes)

        return bool(
            self.docstring
            or has_public_attributes
            or has_public_functions
            or has_public_classes
        )

    def get_all_fqns(self) -> List[str]:
        fqns = []
        if self.docstring:
            # Consistent with how we might handle module doc in the future
            # fqns.append("__doc__")
            pass

        for attr in self.attributes:
            fqns.append(attr.name)
        for func in self.functions:
            fqns.append(func.name)

        for cls in self.classes:
            fqns.append(cls.name)
            for attr in cls.attributes:
                fqns.append(f"{cls.name}.{attr.name}")
            for method in cls.methods:
                fqns.append(f"{cls.name}.{method.name}")
        return sorted(fqns)
~~~~~
~~~~~python.new
    def is_documentable(self) -> bool:
        # A module is documentable if it has a docstring, or any public
        # attributes, functions, or classes.
        has_public_attributes = any(
            not attr.name.startswith("_") and attr.alias_target is None
            for attr in self.attributes
        )
        has_public_functions = any(
            not func.name.startswith("_") for func in self.functions
        )
        has_public_classes = any(not cls.name.startswith("_") for cls in self.classes)

        return bool(
            self.docstring
            or has_public_attributes
            or has_public_functions
            or has_public_classes
        )

    def get_all_fqns(self) -> List[str]:
        fqns = []
        if self.docstring:
            # Consistent with how we might handle module doc in the future
            # fqns.append("__doc__")
            pass

        for attr in self.attributes:
            if attr.alias_target is None:
                fqns.append(attr.name)
        for func in self.functions:
            fqns.append(func.name)

        for cls in self.classes:
            fqns.append(cls.name)
            for attr in cls.attributes:
                # Class attributes that are aliases/imports should also be excluded
                # if we want to be consistent, though they are rarer.
                if attr.alias_target is None:
                    fqns.append(f"{cls.name}.{attr.name}")
            for method in cls.methods:
                fqns.append(f"{cls.name}.{method.name}")
        return sorted(fqns)
~~~~~

### 下一步建议

修复已应用。建议您清理一下现有的签名文件缓存（`rm -rf .stitcher/signatures`），然后再次运行 `stitcher pump`。这次，新生成的签名文件将不再包含导入符号，从而永久消除那些错误的警告。
