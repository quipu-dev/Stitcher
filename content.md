简要回答
针对 `InMemoryStateBackend.pyi` 中出现的 `_run_id: Any = run_id` 作用域错误，我们需要修改 `StubGenerator`，使其在生成类属性时强制忽略赋值。这是因为在 `.pyi` 文件中，类体内的赋值通常会引用 `__init__` 上下文中才存在的局部变量，从而导致语法错误。

我将生成一个计划来实施此修复，并更新相关的单元测试。

## [WIP] fix(adapter): 禁止类属性生成赋值以防止作用域错误

### 用户需求
修复生成的 `.pyi` 文件中，类属性错误地包含从 `__init__` 提取的局部变量赋值（如 `_run_id: Any = run_id`），导致生成的文件包含无效代码。

### 评论
这是一个关键的正确性修复。虽然简单的字面量赋值（如 `x = 1`）在 `.pyi` 中是合法的，但没有任何简单的方法能区分“安全的字面量”和“不安全的局部变量引用”。因此，**在生成类属性存根时统一丢弃赋值**是最安全、最稳健的策略，这也是 PEP 484 推荐的做法（即 `name: type`）。模块级属性的赋值将保留。

### 目标
1.  修改 `packages/stitcher-python-adapter/src/stitcher/adapter/python/internal/stub_generator.py`，为 `_generate_attribute` 添加 `include_value` 参数。
2.  在 `_generate_class` 中调用该方法时，强制传入 `include_value=False`。
3.  更新 `packages/stitcher-python-adapter/tests/unit/test_stub_generator.py`，验证类属性不再包含赋值，同时确保模块级属性仍然包含赋值。

### 基本原理
`.pyi` 文件的核心职责是类型定义。类属性的默认值或初始值对于静态类型检查通常是次要的，而错误的赋值会直接破坏文件。通过在类作用域内禁用赋值生成，我们消除了这种风险。

### 标签
#intent/fix #flow/ready #priority/high #comp/runtime #concept/codegen #scope/core #ai/instruct
#task/domain/engine #task/object/stub-generator #task/action/fix #task/state/continue

---

### Script

#### Acts 1: 修改 StubGenerator 逻辑

我们将修改 `_generate_attribute` 方法以支持可选地忽略值，并在生成类属性时使用此选项。

~~~~~act
patch_file
packages/stitcher-python-adapter/src/stitcher/adapter/python/internal/stub_generator.py
~~~~~
~~~~~python.old
    def _indent(self, level: int) -> str:
        return self._indent_str * level

    def _generate_attribute(self, attr: Attribute, level: int) -> str:
        indent = self._indent(level)
        # In .pyi files, we prefer Type Hints:  name: type
        # If value is present (constant), we might output: name: type = value
        # But PEP 484 recommends name: type = ... for constants or just name: type
        # Let's stick to name: type for now as per test expectation.

        annotation = attr.annotation if attr.annotation else "Any"
        line = f"{indent}{attr.name}: {annotation}"

        if attr.value:
            line += f" = {attr.value}"

        return line

    def _generate_args(self, args: List[Argument]) -> str:
~~~~~
~~~~~python.new
    def _indent(self, level: int) -> str:
        return self._indent_str * level

    def _generate_attribute(
        self, attr: Attribute, level: int, include_value: bool = True
    ) -> str:
        indent = self._indent(level)
        # In .pyi files, we prefer Type Hints:  name: type
        # If value is present (constant), we might output: name: type = value
        # But PEP 484 recommends name: type = ... for constants or just name: type
        # For class attributes, we purposefully exclude values to avoid scoping issues.

        annotation = attr.annotation if attr.annotation else "Any"
        line = f"{indent}{attr.name}: {annotation}"

        if include_value and attr.value:
            line += f" = {attr.value}"

        return line

    def _generate_args(self, args: List[Argument]) -> str:
~~~~~

~~~~~act
patch_file
packages/stitcher-python-adapter/src/stitcher/adapter/python/internal/stub_generator.py
~~~~~
~~~~~python.old
        # Attributes
        for attr in cls.attributes:
            lines.append(self._generate_attribute(attr, level + 1))
            has_content = True

        if has_content and cls.methods:
~~~~~
~~~~~python.new
        # Attributes
        for attr in cls.attributes:
            # We explicitly DISABLE value generation for class attributes.
            # This prevents bugs where instance attributes initialized from __init__ arguments
            # (e.g. self.x = x) are generated as class attrs with invalid values (x: Any = x).
            lines.append(
                self._generate_attribute(attr, level + 1, include_value=False)
            )
            has_content = True

        if has_content and cls.methods:
~~~~~

#### Acts 2: 更新单元测试

修改现有的测试用例以反映新的预期行为，并添加一个新的测试用例来专门验证类属性值已被移除。

~~~~~act
patch_file
packages/stitcher-python-adapter/tests/unit/test_stub_generator.py
~~~~~
~~~~~python.old
        output = generator.generate(module)

        assert "@decorator" in output
        assert "class MyClass(Base1, Base2):" in output
        assert "    x: int = 1" in output
        assert "    def method(self): ..." in output
~~~~~
~~~~~python.new
        output = generator.generate(module)

        assert "@decorator" in output
        assert "class MyClass(Base1, Base2):" in output
        # Class attribute values should be stripped
        assert "    x: int" in output
        assert "    x: int =" not in output
        assert "    def method(self): ..." in output

    def test_generate_attribute_value_handling(self, generator):
        """
        Verify that module attributes KEEP values, but class attributes DROP values.
        """
        # Module attribute
        mod_attr = Attribute(name="CONST", annotation="int", value="42")
        
        # Class attribute (simulating self.param = param injection)
        cls_attr = Attribute(name="param", annotation="str", value="param")
        cls = ClassDef(name="MyClass", attributes=[cls_attr])
        
        module = ModuleDef(file_path="test.py", attributes=[mod_attr], classes=[cls])
        
        output = generator.generate(module)
        
        # Module level: "CONST: int = 42"
        assert "CONST: int = 42" in output
        
        # Class level: "    param: str" (No "= param")
        assert "    param: str" in output
        assert " = param" not in output
~~~~~

### 下一步建议

由于这是对生成逻辑的核心修改，建议在应用修复后再次运行 `test_stub_generator.py`。
然后，你可以再次尝试 `stitcher generate` 或查看之前生成的 `.pyi` 文件（如果测试环境中有的话），确认 `InMemoryStateBackend.pyi` 中的 `_run_id: Any` 后面的 `= run_id` 是否已经消失。

此修复目前只涉及 `stitcher-python-adapter`，不会影响 CLI 或 Application 的逻辑，因此风险较低。
