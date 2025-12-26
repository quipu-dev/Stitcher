## [WIP] feat: 实现文档提取与管理服务 DocumentManager

### 用户需求
为了实现 `stitcher init` 命令（Task 2.2），我们需要一个核心服务层组件，负责将解析后的代码结构（IR）转换为扁平的文档键值对，并持久化到存储中。这连接了之前完成的“解析器”（Task 1.2）和“I/O 适配器”（Task 2.1）。

### 评论
通过引入 `DocumentManager`，我们将“如何从代码中提取文档”和“如何保存文档”这两个关注点与具体的 CLI 命令解耦。这使得逻辑更加清晰，且易于测试。我们确立了 **相对 FQN (Relative Fully Qualified Name)** 作为文档 Key 的标准（例如 `MyClass.method`），这在单文件对应的 YAML 中是非常直观的。

### 目标
1.  在 `stitcher-application` 中创建 `DocumentManager` 服务类。
2.  实现从 `ModuleDef` 到扁平化文档字典 `Dict[str, str]` 的转换逻辑。
    *   支持模块级文档 (`__doc__`)。
    *   支持类、方法、函数的文档提取。
    *   使用点号连接嵌套结构（如 `ClassName.method_name`）。
3.  集成 `YamlAdapter`，实现将提取出的文档保存为 `.stitcher.yaml` 文件。
    *   命名规范：源文件 `foo.py` -> 文档文件 `foo.stitcher.yaml`。

### 基本原理
我们采用 **“就近存储 + 相对寻址”** 的策略：
1.  **存储**：文档文件默认放置在源文件同级目录，以 `.stitcher.yaml` 结尾。这符合直觉，便于开发者查找。
2.  **寻址**：YAML 文件内部的 Key 是相对于该模块的路径。例如在 `user.stitcher.yaml` 中，Key `login` 对应 `user.py` 中的 `login` 函数。这种相对路径设计使得重构（如移动整个文件）时，文档文件内部的内容不需要修改，只需要重命名文件即可。

### 标签
#intent/build #flow/ready #priority/high #comp/runtime #concept/state #scope/core #ai/instruct #task/domain/doc-management #task/object/doc-manager #task/action/implementation #task/state/continue

---

### Script

#### Acts 1: 创建 DocumentManager 服务

我们将创建 `packages/stitcher-application/src/stitcher/app/services/doc_manager.py`。这个类将包含核心的提取和保存逻辑。

~~~~~act
run_command
~~~~~
~~~~~bash
mkdir -p packages/stitcher-application/src/stitcher/app/services
touch packages/stitcher-application/src/stitcher/app/services/__init__.py
~~~~~

~~~~~act
write_file
packages/stitcher-application/src/stitcher/app/services/doc_manager.py
~~~~~
~~~~~python
from pathlib import Path
from typing import Dict, Optional

from stitcher.spec import ModuleDef, ClassDef, FunctionDef
from stitcher.io import DocumentAdapter, YamlAdapter
from stitcher.common import bus
from stitcher.needle import L


class DocumentManager:
    """
    Service responsible for managing documentation assets.
    Handles extraction of docstrings from IR and persistence via adapters.
    """

    def __init__(self, root_path: Path, adapter: Optional[DocumentAdapter] = None):
        self.root_path = root_path
        # Default to YamlAdapter if none provided
        self.adapter = adapter or YamlAdapter()

    def _extract_from_function(self, func: FunctionDef, prefix: str = "") -> Dict[str, str]:
        """Recursively extracts docstrings from a function."""
        docs = {}
        full_name = f"{prefix}{func.name}"
        
        if func.docstring:
            docs[full_name] = func.docstring
            
        # Functions usually don't have nested items we care about for docstrings
        # (inner functions are typically implementation details)
        return docs

    def _extract_from_class(self, cls: ClassDef, prefix: str = "") -> Dict[str, str]:
        """Recursively extracts docstrings from a class and its methods."""
        docs = {}
        full_name = f"{prefix}{cls.name}"
        
        if cls.docstring:
            docs[full_name] = cls.docstring
            
        # Process methods
        for method in cls.methods:
            docs.update(self._extract_from_function(method, prefix=f"{full_name}."))
            
        # Future: Process nested classes if we support them
        
        return docs

    def flatten_module_docs(self, module: ModuleDef) -> Dict[str, str]:
        """
        Converts a ModuleDef IR into a flat dictionary of docstrings.
        Keys are relative FQNs (e.g. "MyClass.method").
        """
        docs: Dict[str, str] = {}
        
        # 1. Module Docstring
        if module.docstring:
            docs["__doc__"] = module.docstring
            
        # 2. Functions
        for func in module.functions:
            docs.update(self._extract_from_function(func))
            
        # 3. Classes
        for cls in module.classes:
            docs.update(self._extract_from_class(cls))
            
        # 4. Attributes (if they have docstrings)
        for attr in module.attributes:
            if attr.docstring:
                docs[attr.name] = attr.docstring
                
        # Also class attributes
        for cls in module.classes:
            for attr in cls.attributes:
                if attr.docstring:
                    docs[f"{cls.name}.{attr.name}"] = attr.docstring

        return docs

    def save_docs_for_module(self, module: ModuleDef) -> Path:
        """
        Extracts docs from the module and saves them to a sidecar .stitcher.yaml file.
        Returns the path to the saved file.
        """
        data = self.flatten_module_docs(module)
        
        if not data:
            # If no docs found, do we create an empty file?
            # For 'init', maybe yes, to signify it's tracked?
            # Or maybe no, to avoid clutter. 
            # Let's verify existing behavior: YamlAdapter creates file even if empty?
            # YamlAdapter.save does nothing if data is empty in our current impl.
            # Let's skip saving if empty for now.
            return Path("")

        # Construct output path: src/app.py -> src/app.stitcher.yaml
        # ModuleDef.file_path is relative to project root
        module_path = self.root_path / module.file_path
        output_path = module_path.with_suffix(".stitcher.yaml")
        
        self.adapter.save(output_path, data)
        return output_path
~~~~~

#### Acts 2: 导出服务

~~~~~act
write_file
packages/stitcher-application/src/stitcher/app/services/__init__.py
~~~~~
~~~~~python
from .doc_manager import DocumentManager

__all__ = ["DocumentManager"]
~~~~~

#### Acts 3: 添加单元测试

验证提取逻辑的正确性，特别是嵌套结构（类方法）和特殊的 `__doc__` 键。

~~~~~act
write_file
packages/stitcher-application/tests/test_doc_manager.py
~~~~~
~~~~~python
import pytest
from pathlib import Path
from stitcher.spec import ModuleDef, FunctionDef, ClassDef, Attribute
from stitcher.app.services import DocumentManager
from stitcher.io import DocumentAdapter

class MockAdapter(DocumentAdapter):
    def __init__(self):
        self.saved_data = {}
        self.saved_path = None

    def load(self, path: Path):
        return {}

    def save(self, path: Path, data: dict):
        self.saved_path = path
        self.saved_data = data


@pytest.fixture
def sample_module_ir():
    """
    def func():
        '''Func doc'''
        
    class MyClass:
        '''Class doc'''
        attr: int
        '''Attr doc'''
        
        def method(self):
            '''Method doc'''
    """
    return ModuleDef(
        file_path="src/main.py",
        docstring="Module doc",
        functions=[
            FunctionDef(name="func", docstring="Func doc")
        ],
        classes=[
            ClassDef(
                name="MyClass",
                docstring="Class doc",
                attributes=[
                    Attribute(name="attr", docstring="Attr doc")
                ],
                methods=[
                    FunctionDef(name="method", docstring="Method doc")
                ]
            )
        ]
    )


def test_flatten_module_docs(tmp_path, sample_module_ir):
    manager = DocumentManager(root_path=tmp_path)
    docs = manager.flatten_module_docs(sample_module_ir)
    
    assert docs["__doc__"] == "Module doc"
    assert docs["func"] == "Func doc"
    assert docs["MyClass"] == "Class doc"
    assert docs["MyClass.method"] == "Method doc"
    assert docs["MyClass.attr"] == "Attr doc"


def test_save_docs_for_module(tmp_path, sample_module_ir):
    mock_adapter = MockAdapter()
    manager = DocumentManager(root_path=tmp_path, adapter=mock_adapter)
    
    output_path = manager.save_docs_for_module(sample_module_ir)
    
    expected_path = tmp_path / "src/main.stitcher.yaml"
    assert output_path == expected_path
    assert mock_adapter.saved_path == expected_path
    assert mock_adapter.saved_data["MyClass.method"] == "Method doc"
~~~~~

### 下一步建议
现在 `DocumentManager` 已经就绪，我们可以正式实现 `stitcher init` 命令。该命令将编排整个流程：调用 `StitcherApp` 扫描文件，然后使用 `DocumentManager` 批量生成 YAML 文件。我们将需要在 `StitcherApp` 中添加一个新的入口点 `run_init()`。
