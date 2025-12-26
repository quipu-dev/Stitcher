## [WIP] feat: 升级 `generate` 命令以支持文档解耦

### 用户需求
完成 **任务 2.3: 升级 `stitcher generate`**。核心需求是修改生成逻辑，使其不再仅仅依赖源代码中的文档字符串，而是优先读取并使用外部 `.stitcher.yaml` 文件中的文档内容。这是实现文档与代码解耦的关键一步。

### 评论
这将真正激活文档 I/O 模块的价值。我们需要在 `StitcherApp` 的生成流程中插入一个“文档合并/覆盖”的步骤。逻辑应当是：**Source (Code) + Overlay (YAML) -> Final IR -> .pyi**。

### 目标
1.  在 `ModuleDef` 层面或更高层面实现文档合并逻辑。
2.  修改 `StitcherApp._generate_stubs` 流程，在生成代码前，先加载对应的 `.stitcher.yaml`（如果存在），并更新内存中的 `ModuleDef` 对象。
3.  确保插件（Plugin）生成的虚拟模块也能（在未来）支持这种覆盖，虽然目前主要针对物理文件。
4.  验证：修改 YAML 文件后，再次运行 `generate`，生成的 `.pyi` 应反映 YAML 中的内容，而非源代码中的内容。

### 基本原理
1.  **加载阶段**：`DocumentManager` 需要提供一个 `load_docs_for_module(module)` 方法，返回该模块对应的文档字典。
2.  **合并阶段**：我们需要一个 `apply_docs_to_module(module, docs)` 函数，遍历 IR 树（Module -> Classes -> Functions），根据 FQN Key 将文档字典中的内容注入回 IR 对象。
3.  **生成阶段**：`StubGenerator` 使用更新后的 IR 生成 `.pyi`，此时它已经是“被缝合（Stitched）”过的状态。

### 标签
#intent/refine #flow/ready #priority/high #comp/runtime #concept/state #scope/core #ai/instruct #task/domain/doc-management #task/object/command-generate #task/action/upgrade #task/state/continue

---

### Script

#### Acts 1: 扩展 DocumentManager 以支持加载和应用文档

我们需要在 `DocumentManager` 中添加加载和应用文档的逻辑。

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/services/doc_manager.py
~~~~~
~~~~~python.old
        self.adapter.save(output_path, data)
        return output_path
~~~~~
~~~~~python.new
        self.adapter.save(output_path, data)
        return output_path

    def load_docs_for_module(self, module: ModuleDef) -> Dict[str, str]:
        """
        Loads documentation from the corresponding .stitcher.yaml file.
        Returns empty dict if file does not exist.
        """
        # ModuleDef.file_path is relative to project root (e.g. src/app.py)
        # We look for src/app.stitcher.yaml
        if not module.file_path:
            return {}
            
        module_path = self.root_path / module.file_path
        doc_path = module_path.with_suffix(".stitcher.yaml")
        
        return self.adapter.load(doc_path)

    def _apply_to_function(self, func: FunctionDef, docs: Dict[str, str], prefix: str = ""):
        full_name = f"{prefix}{func.name}"
        if full_name in docs:
            func.docstring = docs[full_name]

    def _apply_to_class(self, cls: ClassDef, docs: Dict[str, str], prefix: str = ""):
        full_name = f"{prefix}{cls.name}"
        if full_name in docs:
            cls.docstring = docs[full_name]
            
        for method in cls.methods:
            self._apply_to_function(method, docs, prefix=f"{full_name}.")
            
        for attr in cls.attributes:
            attr_key = f"{full_name}.{attr.name}"
            if attr_key in docs:
                attr.docstring = docs[attr_key]

    def apply_docs_to_module(self, module: ModuleDef) -> None:
        """
        Loads external docs and applies them to the ModuleDef IR in-place.
        Prioritizes external docs over existing source docs.
        """
        docs = self.load_docs_for_module(module)
        if not docs:
            return

        # 1. Module Docstring
        if "__doc__" in docs:
            module.docstring = docs["__doc__"]
            
        # 2. Functions
        for func in module.functions:
            self._apply_to_function(func, docs)
            
        # 3. Classes
        for cls in module.classes:
            self._apply_to_class(cls, docs)
            
        # 4. Attributes
        for attr in module.attributes:
            if attr.name in docs:
                attr.docstring = docs[attr.name]
~~~~~

#### Acts 2: 更新 StitcherApp 生成流程

在 `_generate_stubs` 中调用 `apply_docs_to_module`。

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/core.py
~~~~~
~~~~~python.old
    def _generate_stubs(self, modules: List[ModuleDef]) -> List[Path]:
        """Generates .pyi files from a list of ModuleDefs."""
        generated_files: List[Path] = []
        for module in modules:
            pyi_content = self.generator.generate(module)
            # Output path is relative to the project root
            output_path = self.root_path / Path(module.file_path).with_suffix(".pyi")
~~~~~
~~~~~python.new
    def _generate_stubs(self, modules: List[ModuleDef]) -> List[Path]:
        """Generates .pyi files from a list of ModuleDefs."""
        generated_files: List[Path] = []
        for module in modules:
            # Step 1: Hydrate IR with external docs (The "Stitching" process)
            self.doc_manager.apply_docs_to_module(module)

            # Step 2: Generate code
            pyi_content = self.generator.generate(module)
            # Output path is relative to the project root
            output_path = self.root_path / Path(module.file_path).with_suffix(".pyi")
~~~~~

#### Acts 3: 添加测试用例

验证覆盖逻辑：源文件有文档 A，YAML 文件有文档 B，生成结果应为 B。

~~~~~act
write_file
packages/stitcher-application/tests/test_doc_overlay.py
~~~~~
~~~~~python
import pytest
from pathlib import Path
from stitcher.spec import ModuleDef, FunctionDef
from stitcher.app.services import DocumentManager
from stitcher.io import YamlAdapter


def test_apply_docs_overlay(tmp_path: Path):
    """
    Verifies that external docs overwrite source docs in the IR.
    """
    # 1. Setup IR with "Source Docs"
    module = ModuleDef(
        file_path="src/main.py",
        docstring="Source Module Doc",
        functions=[
            FunctionDef(name="func", docstring="Source Func Doc")
        ]
    )
    
    # 2. Setup External Docs (Mocking file system via YamlAdapter)
    # create src/main.stitcher.yaml
    doc_file = tmp_path / "src" / "main.stitcher.yaml"
    doc_file.parent.mkdir(parents=True)
    
    adapter = YamlAdapter()
    external_docs = {
        "__doc__": "YAML Module Doc",
        "func": "YAML Func Doc"
    }
    adapter.save(doc_file, external_docs)
    
    # 3. Apply
    manager = DocumentManager(root_path=tmp_path)
    manager.apply_docs_to_module(module)
    
    # 4. Assert IR is updated
    assert module.docstring == "YAML Module Doc"
    assert module.functions[0].docstring == "YAML Func Doc"


def test_apply_docs_partial_overlay(tmp_path: Path):
    """
    Verifies that if a key is missing in YAML, source doc is preserved.
    """
    module = ModuleDef(
        file_path="src/main.py",
        functions=[
            FunctionDef(name="func1", docstring="Source 1"),
            FunctionDef(name="func2", docstring="Source 2")
        ]
    )
    
    doc_file = tmp_path / "src" / "main.stitcher.yaml"
    doc_file.parent.mkdir(parents=True)
    
    adapter = YamlAdapter()
    # Only overriding func1
    adapter.save(doc_file, {"func1": "YAML 1"})
    
    manager = DocumentManager(root_path=tmp_path)
    manager.apply_docs_to_module(module)
    
    assert module.functions[0].docstring == "YAML 1"
    assert module.functions[1].docstring == "Source 2"
~~~~~

### 下一步建议
我们现在完成了核心的“解耦闭环”：`init` 导出文档，`generate` 缝合文档。
下一个关键步骤是 **任务 2.4: `stitcher check` 命令**。这个命令对于 CI/CD 至关重要，它确保代码和文档没有“漂移”（Drift）。例如，如果在代码中删除了一个函数，但在 YAML 中还保留着它的文档，或者反之，`check` 命令应该报错。这将极大地提升项目的健康度。
