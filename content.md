简短回答
好的，我们开始第二阶段的核心逻辑实现。首先，我们需要升级底层数据模型和服务，使其具备“捕获”和“存储”函数签名文本的能力，这是生成 Diff 的前提。

## [WIP] feat(core): 支持函数签名文本的提取与持久化

### 用户需求
为了在 `check` 命令中展示代码变更的差异（Diff），系统需要能够获取函数的“人类可读”签名文本，并将其作为基线（Baseline）持久化存储。

### 评论
当前系统只存储了签名的哈希值（`structure_hash`），这足以检测**变化**，但无法展示**哪里变了**。我们需要扩展 `Fingerprint` 规范以支持存储文本，并增强 `FunctionDef` 模型以能够自我重构为签名字符串。

### 目标
1.  修改 `stitcher.spec.FunctionDef`，添加 `get_signature_string()` 方法。
2.  修改 `stitcher.spec.Fingerprint`，更新键名校验正则，允许存储 `_text` 后缀的数据。
3.  修改 `stitcher.app.services.SignatureManager`，添加 `extract_signature_texts()` 方法。

### 基本原理
-   **所见即所得**: `get_signature_string` 应该尽可能还原代码中的函数定义行（`def foo(...) -> ...:`），以便用户在 Diff 中看到熟悉的 Python 语法。
-   **非破坏性扩展**: 通过扩展 `Fingerprint` 的正则校验，我们可以在不改变现有存储结构（JSON）的前提下，向其中注入新的元数据字段（`baseline_code_signature_text`）。

### 标签
#intent/build #flow/ready #priority/high
#comp/spec #comp/application #concept/state
#task/domain/core #task/object/signature #task/action/enhance
#task/state/continue

---

### Script

#### Acts 1: 增强 FunctionDef 模型

我们需要实现一个方法，将 `FunctionDef` 对象反向组装成函数定义字符串。

~~~~~act
patch_file
packages/stitcher-spec/src/stitcher/spec/models.py
~~~~~
~~~~~python.old
    def compute_fingerprint(self) -> str:
        # Build a stable string representation of the signature
        parts = [
            f"name:{self.name}",
            f"async:{self.is_async}",
            f"static:{self.is_static}",
            f"class:{self.is_class}",
            f"ret:{self.return_annotation or ''}",
        ]

        for arg in self.args:
            arg_sig = (
                f"{arg.name}:{arg.kind}:{arg.annotation or ''}:{arg.default or ''}"
            )
            parts.append(arg_sig)

        # We deliberately exclude decorators from the fingerprint for now,
        # as they often change without affecting the core API contract relevant to docs.
        # We also strictly exclude self.docstring.

        sig_str = "|".join(parts)
        return hashlib.sha256(sig_str.encode("utf-8")).hexdigest()
~~~~~
~~~~~python.new
    def compute_fingerprint(self) -> str:
        # Build a stable string representation of the signature
        parts = [
            f"name:{self.name}",
            f"async:{self.is_async}",
            f"static:{self.is_static}",
            f"class:{self.is_class}",
            f"ret:{self.return_annotation or ''}",
        ]

        for arg in self.args:
            arg_sig = (
                f"{arg.name}:{arg.kind}:{arg.annotation or ''}:{arg.default or ''}"
            )
            parts.append(arg_sig)

        # We deliberately exclude decorators from the fingerprint for now,
        # as they often change without affecting the core API contract relevant to docs.
        # We also strictly exclude self.docstring.

        sig_str = "|".join(parts)
        return hashlib.sha256(sig_str.encode("utf-8")).hexdigest()

    def get_signature_string(self) -> str:
        """
        Reconstructs the function signature as a string.
        Example: async def foo(a: int, b: str = 'default') -> bool:
        """
        parts = []
        if self.is_async:
            parts.append("async")
        parts.append("def")
        parts.append(f"{self.name}(")

        arg_strs = []
        # Simple reconstruction. Note: Does not handle / and * markers perfectly
        # for complex cases, but sufficient for diffing context.
        # To improve, we could reuse logic similar to StubGenerator._generate_args
        # but keep it simple for now.
        for arg in self.args:
            s = arg.name
            if arg.kind == ArgumentKind.VAR_POSITIONAL:
                s = f"*{arg.name}"
            elif arg.kind == ArgumentKind.VAR_KEYWORD:
                s = f"**{arg.name}"
            
            if arg.annotation:
                s += f": {arg.annotation}"
            if arg.default:
                s += f" = {arg.default}"
            arg_strs.append(s)
        
        parts.append(", ".join(arg_strs))
        parts.append(")")
        
        if self.return_annotation:
            parts.append(f"-> {self.return_annotation}")
        
        parts.append(":")
        return " ".join(parts).replace("( ", "(").replace(" )", ")")
~~~~~

#### Acts 2: 更新 Fingerprint 校验规则

更新正则表达式，允许 `_text` 后缀的键名，以便存储 `baseline_code_signature_text`。

~~~~~act
patch_file
packages/stitcher-spec/src/stitcher/spec/fingerprint.py
~~~~~
~~~~~python.old
# Axiom: [State]_[Source]_[Object]_hash
# Example: baseline_code_structure_hash
# We enforce 4 segments, starting with state, ending with hash.
FINGERPRINT_KEY_PATTERN = re.compile(r"^(baseline|current)_[a-z]+_[a-z]+_hash$")


class InvalidFingerprintKeyError(KeyError):
    def __init__(self, key: str):
        super().__init__(
            f"Key '{key}' does not conform to the Fingerprint naming axiom "
            "('^(baseline|current)_[a-z]+_[a-z]+_hash$')."
        )
~~~~~
~~~~~python.new
# Axiom: [State]_[Source]_[Object]_[Type]
# Example: baseline_code_structure_hash, baseline_code_signature_text
# We enforce 4 segments, starting with state, ending with type (hash or text).
FINGERPRINT_KEY_PATTERN = re.compile(r"^(baseline|current)_[a-z]+_[a-z]+_(hash|text)$")


class InvalidFingerprintKeyError(KeyError):
    def __init__(self, key: str):
        super().__init__(
            f"Key '{key}' does not conform to the Fingerprint naming axiom "
            "('^(baseline|current)_[a-z]+_[a-z]+_(hash|text)$')."
        )
~~~~~

#### Acts 3: 扩展 SignatureManager

添加 `extract_signature_texts` 方法，用于批量提取模块中所有函数的签名文本。

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/services/signature_manager.py
~~~~~
~~~~~python.old
    def compute_code_structure_hashes(self, module: ModuleDef) -> Dict[str, str]:
        hashes = {}
        for func in module.functions:
            hashes[func.name] = func.compute_fingerprint()
        for cls in module.classes:
            for method in cls.methods:
                fqn = f"{cls.name}.{method.name}"
                hashes[fqn] = method.compute_fingerprint()
        return hashes

    def save_composite_hashes(
        self, module: ModuleDef, hashes: Dict[str, Fingerprint]
    ) -> None:
~~~~~
~~~~~python.new
    def compute_code_structure_hashes(self, module: ModuleDef) -> Dict[str, str]:
        hashes = {}
        for func in module.functions:
            hashes[func.name] = func.compute_fingerprint()
        for cls in module.classes:
            for method in cls.methods:
                fqn = f"{cls.name}.{method.name}"
                hashes[fqn] = method.compute_fingerprint()
        return hashes

    def extract_signature_texts(self, module: ModuleDef) -> Dict[str, str]:
        texts = {}
        for func in module.functions:
            texts[func.name] = func.get_signature_string()
        for cls in module.classes:
            for method in cls.methods:
                fqn = f"{cls.name}.{method.name}"
                texts[fqn] = method.get_signature_string()
        return texts

    def save_composite_hashes(
        self, module: ModuleDef, hashes: Dict[str, Fingerprint]
    ) -> None:
~~~~~

### 下一步建议
基础设施已经就绪。接下来的步骤是：
1.  **应用层变更**: 更新 `StitcherApp`。
    *   在 `run_init` 和 `run_pump` 中调用 `extract_signature_texts` 并保存签名文本。
    *   在 `run_check` 中利用这些文本生成 Diff。
2.  **Pump Diff**: 在 `pump` 流程中生成文档内容的 Diff。
3.  **UI 层**: 更新 Handler 以显示这些 Diff。
