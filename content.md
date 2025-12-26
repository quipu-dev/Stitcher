好的，基于你的确认，我们将执行 **任务一：实现 `check` 命令的函数签名校验**。

这个任务的核心挑战在于：目前的 `.stitcher.yaml` 仅存储了文档字符串，缺乏函数签名的信息，导致 `check` 命令无法感知代码结构的变更（如参数修改）。为了解决这个问题，我们将引入一套**轻量级的签名指纹 (Signature Fingerprint) 机制**。

这个机制将包括：
1.  **指纹计算**: 在内存对象 (`FunctionDef`, `ClassDef`) 中根据签名信息计算哈希值。
2.  **状态持久化**: 将这些指纹存储在 `.stitcher/signatures/` 目录下的影子文件中（不干扰人类编辑的 `.stitcher.yaml`）。
3.  **校验逻辑**: `check` 命令将比对“当前代码计算出的指纹”与“存储的旧指纹”，从而发现结构变更。

以下是具体的执行计划。

简要回答
我们将引入“签名指纹”机制来检测代码结构变更。本计划将涵盖指纹计算逻辑的实现、签名状态的存储管理，以及 `check` 命令的集成。

## [WIP] feat: 引入函数签名指纹机制以增强 check 命令

### 用户需求
`stitcher check` 命令目前只能检测文档条目的存在性（Missing/Extra），无法检测函数签名（参数、返回值）是否发生了变更。用户希望在代码结构发生变化（可能导致文档过时）时得到警告。

### 评论
这是一个关键的健壮性功能。如果没有它，开发者修改了函数参数却忘记更新文档，`stitcher` 将无法察觉，导致生成的 `.pyi` 文件虽然结构正确，但文档内容可能产生误导（例如参数名对不上）。引入“指纹”是解决此问题的标准做法，同时将指纹存储在 `.stitcher/` 隐藏目录中，避免了污染用户的文档工作区，保持了良好的 DX。

### 目标
1.  在 `stitcher-spec` 中为 `FunctionDef` 和 `ClassDef` 实现稳定的**结构指纹计算**逻辑。
2.  在 `stitcher-application` 中实现 `SignatureManager`，负责在 `.stitcher/signatures/` 目录下读写指纹文件。
3.  更新 `check` 命令，使其在校验文档存在性的同时，比对函数签名指纹。
4.  (后续) 更新 `init` 和 `generate` 命令以自动更新指纹库（本计划先聚焦于核心逻辑和 Check）。

### 基本原理
我们不希望在用户手动维护的 `.stitcher.yaml` 中添加机器生成的哈希值，因为这会破坏文件的可读性和可编辑性。因此，我们选择采用 **“影子状态” (Shadow State)** 模式，将签名指纹存储在 `.stitcher/signatures` 目录下的镜像文件结构中。`check` 命令将作为“哨兵”，对比实时代码的指纹与这个影子状态，从而发现差异。

### 标签
#intent/build #flow/ready #priority/high
#comp/runtime #comp/cli #concept/state
#scope/core
#task/domain/quality #task/object/signature-verification #task/action/implement #task/state/begin

---

### Script

#### Acts 1: 在 `stitcher-spec` 中实现指纹计算逻辑

我们需要在 IR 模型中添加一个方法来生成基于内容的哈希。

~~~~~act
patch_file
packages/stitcher-spec/src/stitcher/spec/models.py
~~~~~
~~~~~python.old
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional
~~~~~
~~~~~python.new
import hashlib
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional
~~~~~

~~~~~act
patch_file
packages/stitcher-spec/src/stitcher/spec/models.py
~~~~~
~~~~~python.old
@dataclass
class FunctionDef:
    """Represents a function or method definition."""

    name: str
    args: List[Argument] = field(default_factory=list)
    return_annotation: Optional[str] = None
    decorators: List[str] = field(default_factory=list)
    docstring: Optional[str] = None
    is_async: bool = False
    is_static: bool = False  # @staticmethod
    is_class: bool = False  # @classmethod
~~~~~
~~~~~python.new
@dataclass
class FunctionDef:
    """Represents a function or method definition."""

    name: str
    args: List[Argument] = field(default_factory=list)
    return_annotation: Optional[str] = None
    decorators: List[str] = field(default_factory=list)
    docstring: Optional[str] = None
    is_async: bool = False
    is_static: bool = False  # @staticmethod
    is_class: bool = False  # @classmethod

    def compute_fingerprint(self) -> str:
        """
        Computes a stable hash of the function signature (excluding docstring).
        Includes: name, args (name, kind, annotation, default), return annotation,
        async status, and static/class flags.
        """
        # Build a stable string representation of the signature
        parts = [
            f"name:{self.name}",
            f"async:{self.is_async}",
            f"static:{self.is_static}",
            f"class:{self.is_class}",
            f"ret:{self.return_annotation or ''}",
        ]
        
        for arg in self.args:
            arg_sig = f"{arg.name}:{arg.kind}:{arg.annotation or ''}:{arg.default or ''}"
            parts.append(arg_sig)
            
        # We deliberately exclude decorators from the fingerprint for now,
        # as they often change without affecting the core API contract relevant to docs.
        # We also strictly exclude self.docstring.

        sig_str = "|".join(parts)
        return hashlib.sha256(sig_str.encode("utf-8")).hexdigest()
~~~~~

#### Acts 2: 在 `stitcher-application` 中实现 `SignatureManager`

这个服务将负责管理指纹文件的 I/O。

~~~~~act
write_file
packages/stitcher-application/src/stitcher/app/services/signature_manager.py
~~~~~
~~~~~python
import json
from pathlib import Path
from typing import Dict, Optional

from stitcher.spec import ModuleDef


class SignatureManager:
    """
    Manages the persistence and verification of code structure fingerprints.
    Stores fingerprints in .stitcher/signatures/ mirroring the source tree.
    """

    def __init__(self, root_path: Path):
        self.root_path = root_path
        self.sig_root = root_path / ".stitcher" / "signatures"

    def _get_sig_path(self, module: ModuleDef) -> Path:
        """
        Determines the storage path for a module's signatures.
        e.g. src/app.py -> .stitcher/signatures/src/app.json
        """
        # module.file_path is relative to project root
        rel_path = Path(module.file_path)
        return self.sig_root / rel_path.with_suffix(".json")

    def compute_module_fingerprints(self, module: ModuleDef) -> Dict[str, str]:
        """
        Computes fingerprints for all addressable functions/methods in the module.
        Returns: { "FQN": "hash" }
        """
        fingerprints = {}

        # 1. Functions
        for func in module.functions:
            fingerprints[func.name] = func.compute_fingerprint()

        # 2. Classes and Methods
        for cls in module.classes:
            # We could fingerprint the class itself (bases etc.), but for now
            # let's focus on methods as they map to docstrings.
            for method in cls.methods:
                fqn = f"{cls.name}.{method.name}"
                fingerprints[fqn] = method.compute_fingerprint()

        return fingerprints

    def save_signatures(self, module: ModuleDef) -> None:
        """
        Computes and saves the current signatures of the module to disk.
        """
        fingerprints = self.compute_module_fingerprints(module)
        if not fingerprints:
            return

        sig_path = self._get_sig_path(module)
        sig_path.parent.mkdir(parents=True, exist_ok=True)
        
        with sig_path.open("w", encoding="utf-8") as f:
            json.dump(fingerprints, f, indent=2, sort_keys=True)

    def load_signatures(self, module: ModuleDef) -> Dict[str, str]:
        """
        Loads the stored signatures for a module.
        Returns empty dict if no signature file exists.
        """
        sig_path = self._get_sig_path(module)
        if not sig_path.exists():
            return {}

        try:
            with sig_path.open("r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return {}

    def check_signatures(self, module: ModuleDef) -> Dict[str, str]:
        """
        Compares current module structure against stored signatures.
        Returns a dict of changed items: { "FQN": "signature_mismatch" }
        """
        current_sigs = self.compute_module_fingerprints(module)
        stored_sigs = self.load_signatures(module)
        
        issues = {}
        
        for fqn, current_hash in current_sigs.items():
            stored_hash = stored_sigs.get(fqn)
            
            # If stored_hash is None, it's a new function (covered by 'missing' check in doc_manager).
            # We only care if it EXISTS in storage but differs.
            if stored_hash and stored_hash != current_hash:
                issues[fqn] = "signature_mismatch"
                
        return issues
~~~~~

#### Acts 3: 导出 `SignatureManager`

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/services/__init__.py
~~~~~
~~~~~python.old
from .doc_manager import DocumentManager

__all__ = ["DocumentManager"]
~~~~~
~~~~~python.new
from .doc_manager import DocumentManager
from .signature_manager import SignatureManager

__all__ = ["DocumentManager", "SignatureManager"]
~~~~~

#### Acts 4: 在 `stitcher-needle` 中定义新的错误消息

我们需要定义用于报告签名不匹配的消息 ID。

~~~~~act
write_file
.stitcher/needle/en/check/signatures.json
~~~~~
~~~~~json
{
    "check.issue.mismatch": "   - [CHANGED] {key} (signature changed, docs might be outdated)"
}
~~~~~

#### Acts 5: 更新 `StitcherApp` 以集成 `SignatureManager`

我们需要初始化 `SignatureManager`，并在 `run_check` 中使用它。
同时，为了让这个机制闭环，我们需要在 `run_init` 和 `run_from_config` (generate) 成功时 **更新/保存** 签名，这样下次 check 才有基准。

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/core.py
~~~~~
~~~~~python.old
from stitcher.config import load_config_from_path
from stitcher.app.services import DocumentManager


class StitcherApp:
    def __init__(self, root_path: Path):
        self.root_path = root_path
        self.generator = StubGenerator()
        self.doc_manager = DocumentManager(root_path)

    def _scan_files(self, files_to_scan: List[Path]) -> List[ModuleDef]:
~~~~~
~~~~~python.new
from stitcher.config import load_config_from_path
from stitcher.app.services import DocumentManager, SignatureManager


class StitcherApp:
    def __init__(self, root_path: Path):
        self.root_path = root_path
        self.generator = StubGenerator()
        self.doc_manager = DocumentManager(root_path)
        self.sig_manager = SignatureManager(root_path)

    def _scan_files(self, files_to_scan: List[Path]) -> List[ModuleDef]:
~~~~~

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/core.py
~~~~~
~~~~~python.old
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

            # Critical step: ensure parent directory exists
            output_path.parent.mkdir(parents=True, exist_ok=True)

            output_path.write_text(pyi_content, encoding="utf-8")

            relative_path = output_path.relative_to(self.root_path)
            bus.success(L.generate.file.success, path=relative_path)
            generated_files.append(output_path)
        return generated_files
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

            # Critical step: ensure parent directory exists
            output_path.parent.mkdir(parents=True, exist_ok=True)

            output_path.write_text(pyi_content, encoding="utf-8")
            
            # Step 3: Update signatures (Snapshot current state)
            # When we generate stubs, we assume the code is the new source of truth
            self.sig_manager.save_signatures(module)

            relative_path = output_path.relative_to(self.root_path)
            bus.success(L.generate.file.success, path=relative_path)
            generated_files.append(output_path)
        return generated_files
~~~~~

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/core.py
~~~~~
~~~~~python.old
        # 2. Extract and save docs
        created_files: List[Path] = []
        for module in modules:
            # save_docs_for_module returns an empty path if no docs found/saved
            output_path = self.doc_manager.save_docs_for_module(module)
            if output_path and output_path.name:
                relative_path = output_path.relative_to(self.root_path)
                bus.success(L.init.file.created, path=relative_path)
                created_files.append(output_path)
~~~~~
~~~~~python.new
        # 2. Extract and save docs
        created_files: List[Path] = []
        for module in modules:
            # Initialize signatures (Snapshot baseline)
            self.sig_manager.save_signatures(module)
            
            # save_docs_for_module returns an empty path if no docs found/saved
            output_path = self.doc_manager.save_docs_for_module(module)
            if output_path and output_path.name:
                relative_path = output_path.relative_to(self.root_path)
                bus.success(L.init.file.created, path=relative_path)
                created_files.append(output_path)
~~~~~

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/core.py
~~~~~
~~~~~python.old
        failed_files = 0

        for module in modules:
            issues = self.doc_manager.check_module(module)
            missing = issues["missing"]
            extra = issues["extra"]

            file_rel_path = module.file_path  # string

            if not missing and not extra:
                # Optional: verbose mode could show success
                # bus.success(L.check.file.pass, path=file_rel_path)
                continue

            failed_files += 1
            bus.error(
                L.check.file.fail, path=file_rel_path, count=len(missing) + len(extra)
            )

            # Sort for deterministic output
            for key in sorted(list(missing)):
                bus.error(L.check.issue.missing, key=key)
            for key in sorted(list(extra)):
                bus.error(L.check.issue.extra, key=key)

        if failed_files > 0:
~~~~~
~~~~~python.new
        failed_files = 0

        for module in modules:
            doc_issues = self.doc_manager.check_module(module)
            sig_issues = self.sig_manager.check_signatures(module)
            
            missing = doc_issues["missing"]
            extra = doc_issues["extra"]
            mismatched = sig_issues  # Dict[fqn, reason]

            file_rel_path = module.file_path  # string
            
            total_issues = len(missing) + len(extra) + len(mismatched)

            if total_issues == 0:
                # Optional: verbose mode could show success
                # bus.success(L.check.file.pass, path=file_rel_path)
                continue

            failed_files += 1
            bus.error(
                L.check.file.fail, path=file_rel_path, count=total_issues
            )

            # Sort for deterministic output
            for key in sorted(list(missing)):
                bus.error(L.check.issue.missing, key=key)
            for key in sorted(list(extra)):
                bus.error(L.check.issue.extra, key=key)
            for key in sorted(list(mismatched.keys())):
                bus.error(L.check.issue.mismatch, key=key)

        if failed_files > 0:
~~~~~

### 下一步建议
我们已经实现了签名指纹的核心机制并将其集成到了应用流程中。
下一步，我们需要：
1.  **添加测试**: 为 `SignatureManager` 和新的 `check` 逻辑编写集成测试，确保指纹能正确生成、存储并在变更时触发警告。
2.  **验证**: 验证 `init` -> 修改代码 -> `check` 的流程是否如预期工作。
