分析显示，验证测试的失败揭示了系统内部的一个深层不一致性：

为了继续执行任务，我必须解决以下未经证实的核心假设：
*   **假设 `InitRunner` 和 `PumpRunner` 会为所有 documentable 实体（包括类）创建基准指纹。**

**诊断：**
测试失败是因为生成的 `.json` 签名文件中缺少了 `MyClass` 的条目。通过检查代码，我发现：
1.  `InitRunner` 和 `PumpRunner` 的 `_compute_fingerprints` 方法只遍历了函数和方法，跳过了类。
2.  `stitcher-python-adapter` 中的 `StructureHasher` 和 `SignatureTextHasher` 目前也只处理 `FunctionDef`，对 `ClassDef` 仅做了 `pass` 处理。
3.  这导致 `signatures/*.json` (Baseline) 与 `index.db` (Actual) 以及 `.stitcher.yaml` (Docs) 之间出现了脱节：索引器和文档管理器都在追踪类，但签名管理器却没有。

根据 **ADAP v1.0** 协议，我必须停止简单的“测试修正”，转而修复这个导致确定性缺失的架构缺陷。只有让所有组件对“哪些实体需要追踪”达成共识，SURI 体系才能真正稳固。

## [WIP] refactor: 统一类实体的指纹追踪逻辑

### 用户需求
修复 `test_signature_suri_format.py` 中的断言失败，确保类实体（ClassDef）像函数和方法一样，在基准存档（Baseline）中拥有正确的 SURI 键和指纹数据。

### 评论
通过这次修复，我们将消除系统中的一个“盲区”。类不仅可以拥有文档字符串（需要被 `Check/Pump` 追踪），其定义结构（如父类变更）也属于“签名漂移”的一部分。

### 目标
1.  升级 `stitcher-python-adapter` 中的 `StructureHasher` 和 `SignatureTextHasher`，使其支持 `ClassDef`。
2.  升级 `InitRunner` 和 `PumpRunner`，在计算指纹时包含类实体。
3.  确保测试用例能够成功验证包含类的 SURI。

### 标签
#intent/refine #flow/ready #priority/high #comp/application #comp/runtime #concept/state #scope/core #ai/instruct #task/domain/storage #task/object/fingerprint #task/action/unify-tracking #task/state/continue

---

### Script

#### Acts 1: 升级 Python 适配器的哈希逻辑

我们将修改 `fingerprint.py`，为类实体提供结构哈希和签名文本提取。

~~~~~act
patch_file
packages/stitcher-python-adapter/src/stitcher/adapter/python/fingerprint.py
~~~~~
~~~~~python.old
    def update(
        self, entity: Union[FunctionDef, ClassDef], fingerprint: Fingerprint
    ) -> None:
        if isinstance(entity, FunctionDef):
            h = self._compute_func_hash(entity)
            fingerprint["current_code_structure_hash"] = h
        elif isinstance(entity, ClassDef):
            # Class-level structure hash logic can be added here if needed in future.
            # Currently Stitcher focuses on methods.
            pass

    def _compute_func_hash(self, func: FunctionDef) -> str:
~~~~~
~~~~~python.new
    def update(
        self, entity: Union[FunctionDef, ClassDef], fingerprint: Fingerprint
    ) -> None:
        if isinstance(entity, FunctionDef):
            h = self._compute_func_hash(entity)
            fingerprint["current_code_structure_hash"] = h
        elif isinstance(entity, ClassDef):
            h = self._compute_class_hash(entity)
            fingerprint["current_code_structure_hash"] = h

    def _compute_class_hash(self, cls: ClassDef) -> str:
        # Bases and name form the structure of a class
        parts = [f"name:{cls.name}", f"bases:{'|'.join(cls.bases)}"]
        sig_str = "|".join(parts)
        return hashlib.sha256(sig_str.encode("utf-8")).hexdigest()

    def _compute_func_hash(self, func: FunctionDef) -> str:
~~~~~

~~~~~act
patch_file
packages/stitcher-python-adapter/src/stitcher/adapter/python/fingerprint.py
~~~~~
~~~~~python.old
class SignatureTextHasher:
    def update(
        self, entity: Union[FunctionDef, ClassDef], fingerprint: Fingerprint
    ) -> None:
        if isinstance(entity, FunctionDef):
            text = self._get_signature_string(entity)
            fingerprint["current_code_signature_text"] = text

    def _get_signature_string(self, func: FunctionDef) -> str:
~~~~~
~~~~~python.new
class SignatureTextHasher:
    def update(
        self, entity: Union[FunctionDef, ClassDef], fingerprint: Fingerprint
    ) -> None:
        if isinstance(entity, FunctionDef):
            text = self._get_func_signature_string(entity)
            fingerprint["current_code_signature_text"] = text
        elif isinstance(entity, ClassDef):
            text = self._get_class_signature_string(entity)
            fingerprint["current_code_signature_text"] = text

    def _get_class_signature_string(self, cls: ClassDef) -> str:
        bases_str = f"({', '.join(cls.bases)})" if cls.bases else ""
        return f"class {cls.name}{bases_str}:"

    def _get_func_signature_string(self, func: FunctionDef) -> str:
~~~~~

#### Acts 2: 更新 InitRunner 以包含类

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/runners/init.py
~~~~~
~~~~~python.old
    def _compute_fingerprints(self, module: ModuleDef) -> Dict[str, Fingerprint]:
        fingerprints: Dict[str, Fingerprint] = {}
        for func in module.functions:
            fingerprints[func.name] = self.fingerprint_strategy.compute(func)
        for cls in module.classes:
            for method in cls.methods:
                fqn = f"{cls.name}.{method.name}"
                fingerprints[fqn] = self.fingerprint_strategy.compute(method)
        return fingerprints
~~~~~
~~~~~python.new
    def _compute_fingerprints(self, module: ModuleDef) -> Dict[str, Fingerprint]:
        fingerprints: Dict[str, Fingerprint] = {}
        for func in module.functions:
            fingerprints[func.name] = self.fingerprint_strategy.compute(func)
        for cls in module.classes:
            # Include the class itself
            fingerprints[cls.name] = self.fingerprint_strategy.compute(cls)
            for method in cls.methods:
                fqn = f"{cls.name}.{method.name}"
                fingerprints[fqn] = self.fingerprint_strategy.compute(method)
        return fingerprints
~~~~~

#### Acts 3: 更新 PumpRunner 以包含类

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/runners/pump.py
~~~~~
~~~~~python.old
    def _compute_fingerprints(self, module: ModuleDef) -> Dict[str, Fingerprint]:
        fingerprints: Dict[str, Fingerprint] = {}
        for func in module.functions:
            fingerprints[func.name] = self.fingerprint_strategy.compute(func)
        for cls in module.classes:
            for method in cls.methods:
                fqn = f"{cls.name}.{method.name}"
                fingerprints[fqn] = self.fingerprint_strategy.compute(method)
        return fingerprints
~~~~~
~~~~~python.new
    def _compute_fingerprints(self, module: ModuleDef) -> Dict[str, Fingerprint]:
        fingerprints: Dict[str, Fingerprint] = {}
        for func in module.functions:
            fingerprints[func.name] = self.fingerprint_strategy.compute(func)
        for cls in module.classes:
            # Include the class itself
            fingerprints[cls.name] = self.fingerprint_strategy.compute(cls)
            for method in cls.methods:
                fqn = f"{cls.name}.{method.name}"
                fingerprints[fqn] = self.fingerprint_strategy.compute(method)
        return fingerprints
~~~~~

### 下一步建议

由于底层逻辑发生了变更，现有的其他集成测试可能会因为签名文件中多了类条目而需要重新运行。

请再次执行 SURI 验证测试：
`pytest packages/stitcher-application/tests/integration/test_signature_suri_format.py`

如果通过，我们将确保了全系统对 SURI 和实体追踪的一致性，随后即可开始对 `PumpRunner` 的重构。
