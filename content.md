## [WIP] fix: 修复 Fingerprint 缺失方法与单元测试回归

### 用户需求
1.  **修复 AttributeError**: `Fingerprint` 类缺少 `__delitem__` 方法，导致 `StitcherApp` 在运行 `run_init` 或 `check` 时无法删除临时键（如 `current_code_structure_hash`），抛出错误。
2.  **修复 TypeError**: `SignatureManager` 的构造函数签名已变更（增加了 `fingerprint_strategy`），但部分单元测试尚未更新，导致初始化失败。
3.  **修复 AttributeError**: `SignatureManager.extract_signature_texts` 方法已被移除（逻辑迁移至策略），但测试仍在使用它。

### 评论
这是重构后的标准“清理”工作。架构变更导致了 API 的破坏性修改，我们需要同步更新底层数据模型和相关的单元测试。

### 目标
1.  在 `packages/stitcher-spec/src/stitcher/spec/fingerprint.py` 中实现 `__delitem__`。
2.  更新 `packages/stitcher-application/tests/unit/test_signature_extraction.py`，使用 `PythonFingerprintStrategy` 并调用新的 `compute_fingerprints` API。
3.  更新 `packages/stitcher-application/tests/unit/test_signature_manager.py`，注入策略实例。

### 基本原理
-   **数据模型完整性**: `Fingerprint` 作为一个类字典对象（Dict-like），必须支持 `__delitem__` 以满足 `core.py` 中的业务逻辑需求。
-   **测试适配**: 单元测试必须反映代码的最新状态。由于 `extract_signature_texts` 的逻辑已经移动到 `PythonFingerprintStrategy` 中，原有的测试实际上变成了对“Manager + Strategy”集成工作的验证。

### 标签
#intent/fix #flow/ready #priority/high #comp/runtime #comp/tests #scope/core #ai/instruct #task/domain/architecture #task/object/test-suite #task/action/fix-regressions #task/state/end

---

### Script

#### Acts 1: 修复 Fingerprint 类
添加 `__delitem__` 方法。

~~~~~act
patch_file
packages/stitcher-spec/src/stitcher/spec/fingerprint.py
~~~~~
~~~~~python.old
    def __setitem__(self, key: str, value: str) -> None:
        self._validate_key(key)
        self._hashes[key] = value

    def __contains__(self, key: str) -> bool:
        return key in self._hashes
~~~~~
~~~~~python.new
    def __setitem__(self, key: str, value: str) -> None:
        self._validate_key(key)
        self._hashes[key] = value

    def __delitem__(self, key: str) -> None:
        self._validate_key(key)
        del self._hashes[key]

    def __contains__(self, key: str) -> bool:
        return key in self._hashes
~~~~~

#### Acts 2: 修复 test_signature_extraction.py
该测试调用的方法已被移除，且构造函数缺少参数。我们将引入 `PythonFingerprintStrategy` 来修复它。

~~~~~act
write_file
packages/stitcher-application/tests/unit/test_signature_extraction.py
~~~~~
~~~~~python
from stitcher.spec import Argument, ArgumentKind, FunctionDef, ModuleDef
from stitcher.app.services import SignatureManager
from stitcher.adapter.python import PythonFingerprintStrategy


def test_extract_signature_text_simple(tmp_path):
    # Arrange
    func = FunctionDef(
        name="my_func",
        args=[
            Argument(
                name="a",
                kind=ArgumentKind.POSITIONAL_OR_KEYWORD,
                annotation="int",
            ),
            Argument(
                name="b",
                kind=ArgumentKind.POSITIONAL_OR_KEYWORD,
                annotation="str",
                default="'default'",
            ),
        ],
        return_annotation="bool",
    )
    module = ModuleDef(file_path="src/main.py", functions=[func])

    # Inject the Python strategy
    manager = SignatureManager(
        root_path=tmp_path, fingerprint_strategy=PythonFingerprintStrategy()
    )

    # Act
    # Old: texts = manager.extract_signature_texts(module)
    # New: Use compute_fingerprints and extract the text from the result
    fingerprints = manager.compute_fingerprints(module)

    # Assert
    # The key for signature text is 'current_code_signature_text' defined in PythonFingerprintStrategy
    expected = "def my_func(a: int, b: str = 'default') -> bool:"
    assert (
        fingerprints["my_func"]["current_code_signature_text"]
        == expected
    )


def test_extract_signature_text_async(tmp_path):
    # Arrange
    func = FunctionDef(
        name="run",
        is_async=True,
        args=[],
        return_annotation="None",
    )
    module = ModuleDef(file_path="src/main.py", functions=[func])

    manager = SignatureManager(
        root_path=tmp_path, fingerprint_strategy=PythonFingerprintStrategy()
    )

    # Act
    fingerprints = manager.compute_fingerprints(module)

    # Assert
    expected = "async def run() -> None:"
    assert fingerprints["run"]["current_code_signature_text"] == expected
~~~~~

#### Acts 3: 修复 test_signature_manager.py
只需修复构造函数调用。这里我们也可以使用 `PythonFingerprintStrategy`，因为它已经可用且行为正确。

~~~~~act
patch_file
packages/stitcher-application/tests/unit/test_signature_manager.py
~~~~~
~~~~~python.old
import json
from pathlib import Path
from stitcher.spec import ModuleDef, FunctionDef, Argument, ArgumentKind, Fingerprint
from stitcher.app.services import SignatureManager


def create_func(name="func", args=None, ret=None):
~~~~~
~~~~~python.new
import json
from pathlib import Path
from stitcher.spec import ModuleDef, FunctionDef, Argument, ArgumentKind, Fingerprint
from stitcher.app.services import SignatureManager
from stitcher.adapter.python import PythonFingerprintStrategy


def create_func(name="func", args=None, ret=None):
~~~~~

~~~~~act
patch_file
packages/stitcher-application/tests/unit/test_signature_manager.py
~~~~~
~~~~~python.old
def test_manager_save_and_load_composite_hashes(tmp_path: Path):
    # Arrange
    manager = SignatureManager(root_path=tmp_path)
    module = ModuleDef(file_path="src/main.py", functions=[create_func(name="foo")])

    # Data is now composed of Fingerprint objects
~~~~~
~~~~~python.new
def test_manager_save_and_load_composite_hashes(tmp_path: Path):
    # Arrange
    manager = SignatureManager(
        root_path=tmp_path, fingerprint_strategy=PythonFingerprintStrategy()
    )
    module = ModuleDef(file_path="src/main.py", functions=[create_func(name="foo")])

    # Data is now composed of Fingerprint objects
~~~~~

### 下一步建议
再次运行测试套件。如果修复正确，所有测试（包括集成测试）应该都能通过。一旦绿色，我们就可以进行清理工作（删除旧代码）。
