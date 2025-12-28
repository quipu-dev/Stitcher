## [WIP] fix: 修复 viewdiff 测试失败与签名格式问题

### 错误分析

1.  **`test_check_generates_signature_diff` 失败**:
    *   **现象**: 断言 `"-def func(a: int):"` 失败，实际输出为 `"-def func(a: int) :"`。
    *   **原因**: `FunctionDef.get_signature_string()` 方法在拼接字符串时，冒号 `:` 前多了一个空格（由于 `join(" ")`）。
    *   **分析**: 这是一个代码格式化的小瑕疵，虽然不影响逻辑，但影响可读性。应当修复 `get_signature_string` 方法以生成标准的 Python 签名格式。

2.  **`test_extract_signature_text_*` 失败**:
    *   **现象**: `TypeError: unsupported operand type(s) for /: 'NoneType' and 'str'`.
    *   **原因**: 测试用例中初始化 `SignatureManager(root_path=None)`，但 `__init__` 方法中直接使用了 `root_path / ...`，导致空指针异常。
    *   **分析**: 单元测试应当提供一个有效的 `Path` 对象（如 `tmp_path`）或 Mock 对象，而不是 `None`。

### 用户需求
修复上述测试错误，确保所有测试通过。

### 评论
修复这些问题将提高代码质量（更标准的签名显示）和测试的健壮性。

### 目标
1.  修改 `stitcher-spec` 中的 `models.py`，优化 `get_signature_string` 的输出格式，去除冒号前的空格。
2.  修改 `stitcher-application` 中的单元测试 `test_signature_extraction.py`，使用 `tmp_path` fixture 初始化 `SignatureManager`。

### 基本原理
*   **字符串处理**: 在 `get_signature_string` 返回前增加 `.replace(" :", ":")` 处理。
*   **测试固件**: 利用 `pytest` 的 `tmp_path` fixture 为 `SignatureManager` 提供临时的根目录。

### 标签
#intent/fix #flow/ready #priority/high #comp/spec #comp/tests #scope/core #ai/instruct #task/domain/testing #task/object/test-suite #task/action/fix

---

### Script

#### Acts 1: 修复签名字符串格式

优化 `FunctionDef` 的字符串生成逻辑，使其符合标准 Python 格式（去除冒号前的空格）。

~~~~~act
patch_file
packages/stitcher-spec/src/stitcher/spec/models.py
~~~~~
~~~~~python.old
        
        parts.append(":")
        return " ".join(parts).replace("( ", "(").replace(" )", ")")
~~~~~
~~~~~python.new
        
        parts.append(":")
        return " ".join(parts).replace("( ", "(").replace(" )", ")").replace(" :", ":")
~~~~~

#### Acts 2: 修复单元测试初始化错误

更新测试用例，传入有效的 `tmp_path`。

~~~~~act
patch_file
packages/stitcher-application/tests/unit/test_signature_extraction.py
~~~~~
~~~~~python.old
def test_extract_signature_text_simple():
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
    
    manager = SignatureManager(root_path=None) # type: ignore

    # Act
    texts = manager.extract_signature_texts(module)

    # Assert
    expected = "def my_func(a: int, b: str = 'default') -> bool:"
    assert texts["my_func"] == expected


def test_extract_signature_text_async():
    # Arrange
    func = FunctionDef(
        name="run",
        is_async=True,
        args=[],
        return_annotation="None",
    )
    module = ModuleDef(file_path="src/main.py", functions=[func])
    
    manager = SignatureManager(root_path=None) # type: ignore

    # Act
    texts = manager.extract_signature_texts(module)

    # Assert
    expected = "async def run() -> None:"
    assert texts["run"] == expected
~~~~~
~~~~~python.new
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
    
    manager = SignatureManager(root_path=tmp_path)

    # Act
    texts = manager.extract_signature_texts(module)

    # Assert
    expected = "def my_func(a: int, b: str = 'default') -> bool:"
    assert texts["my_func"] == expected


def test_extract_signature_text_async(tmp_path):
    # Arrange
    func = FunctionDef(
        name="run",
        is_async=True,
        args=[],
        return_annotation="None",
    )
    module = ModuleDef(file_path="src/main.py", functions=[func])
    
    manager = SignatureManager(root_path=tmp_path)

    # Act
    texts = manager.extract_signature_texts(module)

    # Assert
    expected = "async def run() -> None:"
    assert texts["run"] == expected
~~~~~
