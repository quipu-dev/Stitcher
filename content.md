简单回答
生成的 `.pyi` 文件丢失了类的装饰器（特别是 `@dataclass`），导致静态分析工具（Pyright/Mypy）无法识别 `__init__` 方法的自动生成，从而认为这些类继承自默认的 `object`，不接受任何构造参数。我们需要在 IR（Spec）、扫描器（Scanner）和生成器（IO）中增加对类装饰器的支持。

## [WIP] fix(core): 支持 Class Decorator 以修复 Dataclass 类型推断缺失

### 错误分析
**现象**: `pyrefly check` (Pyright) 报错 `Unexpected keyword argument ... in function object.__init__`。
**原因**:
1.  **Stubs 不完整**: 当前 `stitcher` 生成的 `.pyi` 文件中，`ModuleDef` 等类虽然包含属性定义，但**丢失了 `@dataclass` 装饰器**。
2.  **类型推断失效**: 在 `.pyi` 文件中，如果没有 `@dataclass` 装饰器，类型检查器不会为该类合成 `__init__` 方法，而是将其视为普通类。普通类默认继承 `object`，其 `__init__` 不接受参数。
3.  ** IR 缺失**: `stitcher-spec` 中的 `ClassDef` 模型目前没有 `decorators` 字段，导致扫描器即使读到了装饰器也无法存储，生成器更无法输出。

### 用户需求
修复生成的 `.pyi` 文件，使其包含类的装饰器（如 `@dataclass`），从而让类型检查器能正确识别数据类的构造函数签名。

### 评论
这是一个典型的“元数据丢失”导致的问题。虽然代码逻辑没变，但生成的接口描述文件（Stub）失真了。修复这个问题不仅能解决当前的报错，还能支持未来其他类装饰器（如 `@runtime_checkable` 等）的透传。

### 目标
1.  修改 `ClassDef` Spec，增加 `decorators` 字段。
2.  更新 `Scanner`，使其在解析 Class 时提取装饰器。
3.  更新 `StubGenerator`，使其在生成 Class 时输出装饰器。

### 基本原理
通过完善从源码到 IR 再到 Stub 的数据链路，确保“装饰器”这一关键语义信息不丢失。只要 `.pyi` 文件中保留了 `from dataclasses import dataclass` (现有逻辑已支持 import 保留) 和 `@dataclass` 装饰器，Pyright 就能正确推断出 `__init__`。

### 标签
#intent/fix #flow/ready #priority/high #comp/engine #concept/parser #scope/core #task/domain/codemod #task/object/decorators #task/action/fix #task/state/begin

---

### Script

#### Acts 1: 更新 Spec 模型

首先在 `ClassDef` 中添加存储装饰器的字段。

~~~~~act
patch_file
packages/stitcher-spec/src/stitcher/spec/models.py
~~~~~
~~~~~python.old
@dataclass
class ClassDef:
    """Represents a class definition."""

    name: str
    bases: List[str] = field(default_factory=list)
    docstring: Optional[str] = None
    attributes: List[Attribute] = field(default_factory=list)
    methods: List[FunctionDef] = field(default_factory=list)
    # Nested classes can be supported later if needed, but usually .pyi flattens or keeps them nested.
    # For MVP, let's keep it simple.
~~~~~
~~~~~python.new
@dataclass
class ClassDef:
    """Represents a class definition."""

    name: str
    bases: List[str] = field(default_factory=list)
    decorators: List[str] = field(default_factory=list)
    docstring: Optional[str] = None
    attributes: List[Attribute] = field(default_factory=list)
    methods: List[FunctionDef] = field(default_factory=list)
    # Nested classes can be supported later if needed, but usually .pyi flattens or keeps them nested.
    # For MVP, let's keep it simple.
~~~~~

#### Acts 2: 更新 Scanner 解析逻辑

修改 `parser.py`，在访问类定义时提取装饰器。

~~~~~act
patch_file
packages/stitcher-scanner/src/stitcher/scanner/parser.py
~~~~~
~~~~~python.old
    def visit_ClassDef(self, node: cst.ClassDef) -> Optional[bool]:
        # 1. Extract Name
        class_name = node.name.value

        # 2. Extract Docstring
        docstring = node.get_docstring()
        if isinstance(docstring, bool):
            docstring = None

        # 3. Extract Bases
        bases = []
        dummy_module = cst.Module([])
        for base in node.bases:
            # base.value is the expression (Name, Attribute, Call etc.)
            base_code = dummy_module.code_for_node(base.value).strip()
            bases.append(base_code)

        # 4. Create ClassDef object and push to stack
        cls_def = ClassDef(
            name=class_name, bases=bases, docstring=docstring, methods=[], attributes=[]
        )
        self._class_stack.append(cls_def)

        # Continue visiting children (to find methods)
        return True
~~~~~
~~~~~python.new
    def visit_ClassDef(self, node: cst.ClassDef) -> Optional[bool]:
        # 1. Extract Name
        class_name = node.name.value

        # 2. Extract Docstring
        docstring = node.get_docstring()
        if isinstance(docstring, bool):
            docstring = None

        # 3. Extract Bases
        bases = []
        dummy_module = cst.Module([])
        for base in node.bases:
            # base.value is the expression (Name, Attribute, Call etc.)
            base_code = dummy_module.code_for_node(base.value).strip()
            bases.append(base_code)

        # 4. Extract Decorators
        decorators = []
        for dec in node.decorators:
            dec_code = dummy_module.code_for_node(dec.decorator).strip()
            decorators.append(dec_code)

        # 5. Create ClassDef object and push to stack
        cls_def = ClassDef(
            name=class_name,
            bases=bases,
            decorators=decorators,
            docstring=docstring,
            methods=[],
            attributes=[],
        )
        self._class_stack.append(cls_def)

        # Continue visiting children (to find methods)
        return True
~~~~~

#### Acts 3: 更新 Generator 输出逻辑

修改 `stub_generator.py`，在生成类定义前输出装饰器。

~~~~~act
patch_file
packages/stitcher-io/src/stitcher/io/stub_generator.py
~~~~~
~~~~~python.old
    def _generate_class(self, cls: ClassDef, level: int) -> str:
        indent = self._indent(level)
        lines = []

        # Class Def
        bases_str = ""
        if cls.bases:
            bases_str = f"({', '.join(cls.bases)})"

        lines.append(f"{indent}class {cls.name}{bases_str}:")

        # Body
~~~~~
~~~~~python.new
    def _generate_class(self, cls: ClassDef, level: int) -> str:
        indent = self._indent(level)
        lines = []

        # Decorators
        for dec in cls.decorators:
            lines.append(f"{indent}@{dec}")

        # Class Def
        bases_str = ""
        if cls.bases:
            bases_str = f"({', '.join(cls.bases)})"

        lines.append(f"{indent}class {cls.name}{bases_str}:")

        # Body
~~~~~

### 下一步建议

执行完此计划后，你应该重新运行 `stitcher generate` 以更新所有 `.pyi` 文件，然后再次运行 `pyrefly check`。预期结果是所有关于 `unexpected keyword argument` 的错误都将消失。
