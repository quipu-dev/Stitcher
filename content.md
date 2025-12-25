简要回答：
分析完毕。这是一个经典的“双重责任”错误。
1.  **测试数据** (`test_stub_generator.py`) 手动在 IR 中加入了 `@`: `decorators=["@my_decorator"]`。
2.  **生成器** (`stub_generator.py`) 的逻辑也负责添加 `@`: `lines.append(f"{indent}@{dec}")`。

这就导致了 `@@my_decorator` 的产生。

**正确契约**：根据我们的 `Scanner` 实现，`decorators` 列表中存储的是**不带 `@`** 的纯粹的装饰器名称或调用代码。因此，我们应该修复测试数据，使其符合这个契约，而不是修改生成器的逻辑。

## [COMMIT] fix(io): 纠正 StubGenerator 测试中的 decorator 数据

### 错误分析
`test_generate_simple_pyi` 测试失败的根本原因在于，我们手动构造的 `ModuleDef` 对象中的 `decorators` 字段 (`["@my_decorator"]`) 与 `stitcher-scanner` 实际产生的 IR 格式 (`["my_decorator"]`) 不一致。`StubGenerator` 的实现正确地假设了 IR 中不包含 `@` 符号，并负责在生成代码时添加它，这导致了双重添加。

### 用户需求
修复 `test_generate_simple_pyi` 中的断言错误，确保测试通过。

### 评论
这是一个很好的例子，说明了为什么组件间的接口契约（IR 格式）至关重要。通过修复测试数据以符合 `Scanner` 的输出格式，我们强化了这个契约，并确保了 `Generator` 的测试是高保真的。

### 目标
1.  修改 `packages/stitcher-io/tests/test_stub_generator.py`。
2.  从测试用的 `FunctionDef` 构造器中移除硬编码的 `@` 符号。
3.  确保所有测试通过。

### 基本原理
我们遵循单一职责原则：Scanner 负责解析，Generator 负责格式化。`@` 属于格式化的一部分，因此应该由 Generator 添加。测试数据必须反映 Scanner 解析后的纯粹数据。

### 标签
#intent/fix #flow/ready #priority/medium
#comp/io #comp/tests #scope/core #ai/instruct
#task/domain/testing #task/object/stub-generator-tests #task/action/fix-bug
#task/state/end #task/status/completed

---

### Script

#### Acts 1: 修复测试数据
我们将精确地修改测试文件，移除多余的 `@` 符号。

~~~~~act
patch_file
packages/stitcher-io/tests/test_stub_generator.py
~~~~~
~~~~~python.old
                return_annotation="bool",
                docstring="A test function.",
                is_async=True,
                decorators=["@my_decorator"],
            )
        ],
        classes=[
~~~~~
~~~~~python.new
                return_annotation="bool",
                docstring="A test function.",
                is_async=True,
                decorators=["my_decorator"],
            )
        ],
        classes=[
~~~~~

### 下一步建议
所有测试现在应该都通过了。我们已经成功地构建并验证了 `Spec` -> `Scanner` -> `IO` 的核心数据流。

下一步是进入 **Application Layer** 的开发。我们将：
1.  **编写一个集成测试**: 这个测试将不再手动构造 IR，而是提供一个真实的 Python 源文件路径，调用 `Application` 层的方法，然后断言在文件系统上生成了正确的 `.pyi` 文件。
2.  **实现 `stitcher-application`**: 创建一个 `StitcherApp` 类，它会调用 `Scanner` 来解析文件，然后将得到的 `ModuleDef` 传递给 `StubGenerator` 来生成内容，最后将内容写入文件。

这会将我们所有的独立组件**“缝合”**在一起，形成一个可用的端到端工作流。
