分析显示，`pyright` 报错的主要原因是 `stitcher-spec` 的 `__init__.py` 尚未导出新定义的协议，导致 `stitcher-application` 无法正确识别这些符号。此外，`StitcherApp.run_index_build` 的返回类型与实现不一致，需要修正。

## [WIP] fix: 导出核心协议并修正核心应用返回类型

### 错误分析
1.  **导出缺失**: 在 `packages/stitcher-spec/src/stitcher/spec/protocols.py` 中定义的协议没有在 `stitcher/spec/__init__.py` 中通过 `__all__` 导出，导致下游包通过 `from stitcher.spec import ...` 引用时失败。
2.  **类型不匹配**: `StitcherApp.run_index_build` 在 `core.py` 中被声明为返回 `bool`，但它直接返回了 `index_runner.run_build` 的结果，而后者返回的是包含统计信息的 `Dict[str, Any]`。

### 用户需求
修正 `pyright` 类型检查错误，确保新定义的协议可以被外部包引用，并保持 `StitcherApp` 方法签名的正确性。

### 评论
这是协议化重构后的必要收尾工作。在大型项目中，`__init__.py` 作为包的“大门”，必须严格管理其导出符号，以维持清晰的 API 边界。

### 目标
1.  更新 `packages/stitcher-spec/src/stitcher/spec/__init__.py`，导出 `DocumentManagerProtocol` 等四个新协议。
2.  修正 `packages/stitcher-application/src/stitcher/app/core.py` 中的 `run_index_build` 方法，使其根据 `stats["success"]` 返回布尔值。

### 基本原理
-   **符号可见性**: 在 Python 中，通过 `__init__.py` 显式导出符号是定义公共 API 的最佳实践。
-   **类型一致性**: 确保方法的实际返回值符合其 `-> bool` 的类型契约。

### 标签
#intent/fix #flow/ready #priority/high
#comp/interfaces #comp/runtime
#concept/architecture
#ai/instruct
#task/domain/architecture
#task/object/type-safety
#task/action/fix-exports
#task/state/continue

---

### Script

#### Acts 1: 在 stitcher-spec 中导出服务协议

~~~~~act
patch_file
packages/stitcher-spec/src/stitcher/spec/__init__.py
~~~~~
~~~~~python.old
    FingerprintStrategyProtocol,
    StubGeneratorProtocol,
    DocstringParserProtocol,
    DocstringRendererProtocol,
    DocstringSerializerProtocol,
)

__all__ = [
    "DocstringIR",
    "DocstringSection",
    "DocstringItem",
    "SectionKind",
    "LanguageParserProtocol",
    "LanguageTransformerProtocol",
    "FingerprintStrategyProtocol",
    "StubGeneratorProtocol",
    "DocstringParserProtocol",
    "DocstringRendererProtocol",
    "DocstringSerializerProtocol",
    "Fingerprint",
~~~~~
~~~~~python.new
    FingerprintStrategyProtocol,
    StubGeneratorProtocol,
    DocstringParserProtocol,
    DocstringRendererProtocol,
    DocstringSerializerProtocol,
    DocumentManagerProtocol,
    SignatureManagerProtocol,
    DifferProtocol,
    DocstringMergerProtocol,
)

__all__ = [
    "DocstringIR",
    "DocstringSection",
    "DocstringItem",
    "SectionKind",
    "LanguageParserProtocol",
    "LanguageTransformerProtocol",
    "FingerprintStrategyProtocol",
    "StubGeneratorProtocol",
    "DocstringParserProtocol",
    "DocstringRendererProtocol",
    "DocstringSerializerProtocol",
    "DocumentManagerProtocol",
    "SignatureManagerProtocol",
    "DifferProtocol",
    "DocstringMergerProtocol",
    "Fingerprint",
~~~~~

#### Acts 2: 修正 core.py 中的返回类型错误

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/core.py
~~~~~
~~~~~python.old
    def run_index_build(self) -> bool:
        return self.index_runner.run_build(self.workspace)
~~~~~
~~~~~python.new
    def run_index_build(self) -> bool:
        stats = self.index_runner.run_build(self.workspace)
        return stats.get("success", False)
~~~~~

### 下一步建议
导出完成后，`pyright` 的错误应该会消失。建议重新运行类型检查以验证结果。如果通过，我们将继续对 `ScannerService` 进行协议化，或者开始对子组件（如 `CheckAnalyzer`）进行深度清理。
