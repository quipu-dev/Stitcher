分析得非常透彻。你发现了文档定义（`Source_Object_State`）与示例（`State_Source_Object`）之间的矛盾，并敏锐地指出代码库实际上遵循的是示例中的命名。

**决策确认**：
1.  **遵循“现状/示例”的顺序**：即 `[State]_[Source]_[Object]_hash`（例如 `baseline_code_structure_hash`）。这是最务实的选择。
2.  **正则策略**：采用你提出的 `r"^(baseline|current)_[a-z]+_[a-z]+_hash$"`。这既强制了核心结构（状态开头，hash结尾，四段式），又保留了中间段的扩展性（支持未来增加 `ast` 等来源）。
3.  **迁移策略**：确认执行“发现非法键 -> 视为损坏 -> 丢弃并重写”的策略。

请生成 Plan。

## [WIP] refactor(core): 引入 Fingerprint 模型并实施严格的 Schema 验证

### 用户需求
解决 `stitcher hydrate` 在指纹文件使用旧版 Schema 时意外重写文件的问题。根本原因是系统缺乏统一的、强制性的指纹数据模型，导致读写逻辑不一致。

我们需要引入一个 `Fingerprint` 类作为通用容器，强制执行命名公理，并在遇到不合规数据时自动执行“清空并自愈”的策略。

### 评论
这是一个涉及核心状态管理的深度重构。通过引入 `Fingerprint` 模型，我们将隐式的命名约定转化为显式的、运行时强制的代码契约。这不仅能修复当前的 bug，还能为系统未来的扩展（如添加 AST 指纹）提供坚实的基础。

### 目标
1.  在 `stitcher-spec` 中定义 `Fingerprint` 类，实现基于正则的 Key 验证。
2.  更新 `SignatureManager`，使其读写操作都通过 `Fingerprint` 进行，并在读取到非法数据时自动返回空对象（触发重写）。
3.  重构 `StitcherApp`，将所有字典操作替换为 `Fingerprint` 对象操作。
4.  更新回归测试，断言系统能自动修正过时的指纹文件。

### 基本原理
我们放弃了“平滑迁移”的复杂逻辑，选择了更符合项目当前阶段的“快速失败与自愈”策略。
当 `SignatureManager` 遇到不符合 `^(baseline|current)_[a-z]+_[a-z]+_hash$` 正则的旧数据时，会直接抛出 `InvalidFingerprintKeyError`。Manager 捕获此错误并返回空数据，导致 `StitcherApp` 认为该文件未被追踪，从而在后续流程中生成全新的、合规的指纹文件。这种机制保证了系统状态总是趋向于收敛到最新标准。

### 标签
#intent/refactor #flow/ready #priority/high #comp/runtime #concept/state #ai/instruct #task/domain/core #task/object/fingerprint-model #task/action/implementation #task/state/continue

---

### Script

#### Acts 1: 定义 Fingerprint 模型

首先，我们在 `stitcher-spec` 包中创建新的 `fingerprint.py` 文件。这个类将作为字典的包装器，但在写入数据时强制执行命名公理。

~~~~~act
write_file
packages/stitcher-spec/src/stitcher/spec/fingerprint.py
~~~~~
~~~~~python
import re
from dataclasses import dataclass, field
from typing import Dict, Any, Optional

# Axiom: [State]_[Source]_[Object]_hash
# Example: baseline_code_structure_hash
# We enforce 4 segments, starting with state, ending with hash.
FINGERPRINT_KEY_PATTERN = re.compile(
    r"^(baseline|current)_[a-z]+_[a-z]+_hash$"
)


class InvalidFingerprintKeyError(KeyError):
    """Raised when a key does not conform to the Fingerprint naming axiom."""
    def __init__(self, key: str):
        super().__init__(
            f"Key '{key}' does not conform to the Fingerprint naming axiom "
            "('^(baseline|current)_[a-z]+_[a-z]+_hash$')."
        )


@dataclass
class Fingerprint:
    """
    A dynamic, self-validating container for symbol fingerprints.
    It enforces that all keys adhere to the strict naming axiom.
    """
    _hashes: Dict[str, str] = field(default_factory=dict)

    @staticmethod
    def _validate_key(key: str) -> None:
        if not FINGERPRINT_KEY_PATTERN.match(key):
            raise InvalidFingerprintKeyError(key)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Fingerprint":
        """
        Constructs a Fingerprint from a dictionary.
        Validates all keys immediately. Any invalid key raises InvalidFingerprintKeyError.
        """
        validated_hashes = {}
        for key, value in data.items():
            cls._validate_key(key)
            if value is not None:
                validated_hashes[key] = str(value)
        return cls(_hashes=validated_hashes)

    def to_dict(self) -> Dict[str, str]:
        """Returns a copy of the internal hashes."""
        return self._hashes.copy()

    def get(self, key: str, default: Optional[str] = None) -> Optional[str]:
        # We validate key on read too, to ensure consumer uses correct keys
        self._validate_key(key)
        return self._hashes.get(key, default)

    def __getitem__(self, key: str) -> str:
        self._validate_key(key)
        return self._hashes[key]

    def __setitem__(self, key: str, value: str) -> None:
        self._validate_key(key)
        self._hashes[key] = value

    def __contains__(self, key: str) -> bool:
        return key in self._hashes

    def items(self):
        return self._hashes.items()
        
    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, Fingerprint):
            return NotImplemented
        return self._hashes == other._hashes
~~~~~

#### Acts 2: 导出新模型

更新 `__init__.py` 以导出新的类和异常。

~~~~~act
patch_file
packages/stitcher-spec/src/stitcher/spec/__init__.py
~~~~~
~~~~~python
    Resolution,
    ResolutionPlan,
)

__all__ = [
    "Argument",
~~~~~
~~~~~python
    Resolution,
    ResolutionPlan,
)
from .fingerprint import Fingerprint, InvalidFingerprintKeyError

__all__ = [
    "Fingerprint",
    "InvalidFingerprintKeyError",
    "Argument",
~~~~~

#### Acts 3: 适配 SignatureManager

修改 `SignatureManager`。在 `load` 时使用 `Fingerprint.from_dict`，并捕获 `InvalidFingerprintKeyError`。如果捕获到错误，我们选择忽略旧数据（返回空），这将迫使系统在后续步骤中重新生成指纹。

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/services/signature_manager.py
~~~~~
~~~~~python
import json
from pathlib import Path
from typing import Dict, Any

from stitcher.spec import ModuleDef


class SignatureManager:
~~~~~
~~~~~python
import json
from pathlib import Path
from typing import Dict, Any

from stitcher.spec import ModuleDef, Fingerprint, InvalidFingerprintKeyError


class SignatureManager:
~~~~~

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/services/signature_manager.py
~~~~~
~~~~~python
    def save_composite_hashes(self, module: ModuleDef, hashes: Dict[str, Any]) -> None:
        if not hashes:
            sig_path = self._get_sig_path(module)
            if sig_path.exists():
                sig_path.unlink()
            return

        sig_path = self._get_sig_path(module)
        sig_path.parent.mkdir(parents=True, exist_ok=True)

        with sig_path.open("w", encoding="utf-8") as f:
            json.dump(hashes, f, indent=2, sort_keys=True)

    def load_composite_hashes(self, module: ModuleDef) -> Dict[str, Any]:
        sig_path = self._get_sig_path(module)
        if not sig_path.exists():
            return {}
        try:
            with sig_path.open("r", encoding="utf-8") as f:
                data = json.load(f)
                return data if isinstance(data, dict) else {}
        except (json.JSONDecodeError, OSError):
            return {}
~~~~~
~~~~~python
    def save_composite_hashes(
        self, module: ModuleDef, hashes: Dict[str, Fingerprint]
    ) -> None:
        if not hashes:
            sig_path = self._get_sig_path(module)
            if sig_path.exists():
                sig_path.unlink()
            return

        sig_path = self._get_sig_path(module)
        sig_path.parent.mkdir(parents=True, exist_ok=True)

        # Serialize Fingerprint objects to dicts
        serialized_data = {fqn: fp.to_dict() for fqn, fp in hashes.items()}

        with sig_path.open("w", encoding="utf-8") as f:
            json.dump(serialized_data, f, indent=2, sort_keys=True)

    def load_composite_hashes(self, module: ModuleDef) -> Dict[str, Fingerprint]:
        sig_path = self._get_sig_path(module)
        if not sig_path.exists():
            return {}
        try:
            with sig_path.open("r", encoding="utf-8") as f:
                data = json.load(f)
                if not isinstance(data, dict):
                    return {}
                
                # Deserialize into Fingerprint objects.
                # If any key is invalid (e.g. legacy format), we catch the error
                # and treat the whole file as corrupted/outdated -> return empty.
                result = {}
                for fqn, fp_data in data.items():
                    result[fqn] = Fingerprint.from_dict(fp_data)
                return result
        except (json.JSONDecodeError, OSError, InvalidFingerprintKeyError):
            # InvalidFingerprintKeyError triggers "clean slate" logic
            return {}
~~~~~

#### Acts 4: 重构 StitcherApp

这是核心逻辑的重构。我们需要将所有字典操作 (`dict.get(...)`) 替换为 `Fingerprint` 对象的操作。

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/core.py
~~~~~
~~~~~python
from stitcher.spec import ModuleDef, ConflictType, ResolutionAction
from stitcher.common import bus
from needle.pointer import L
~~~~~
~~~~~python
from stitcher.spec import ModuleDef, ConflictType, ResolutionAction, Fingerprint
from stitcher.common import bus
from needle.pointer import L
~~~~~

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/core.py
~~~~~
~~~~~python
    def run_init(self) -> List[Path]:
        configs, _ = load_config_from_path(self.root_path)
        all_created_files: List[Path] = []
        for config in configs:
            if config.name != "default":
                bus.info(L.generate.target.processing, name=config.name)
            unique_files = self._get_files_from_config(config)
            modules = self._scan_files(unique_files)
            if not modules:
                continue
            for module in modules:
                output_path = self.doc_manager.save_docs_for_module(module)
                code_hashes = self.sig_manager.compute_code_structure_hashes(module)
                yaml_hashes = self.doc_manager.compute_yaml_content_hashes(module)
                combined = {}
                all_fqns = set(code_hashes.keys()) | set(yaml_hashes.keys())
                for fqn in all_fqns:
                    combined[fqn] = {
                        "baseline_code_structure_hash": code_hashes.get(fqn),
                        "baseline_yaml_content_hash": yaml_hashes.get(fqn),
                    }
                self.sig_manager.save_composite_hashes(module, combined)
                if output_path and output_path.name:
                    relative_path = output_path.relative_to(self.root_path)
                    bus.success(L.init.file.created, path=relative_path)
                    all_created_files.append(output_path)
        if all_created_files:
            bus.success(L.init.run.complete, count=len(all_created_files))
        else:
            bus.info(L.init.no_docs_found)
        return all_created_files
~~~~~
~~~~~python
    def run_init(self) -> List[Path]:
        configs, _ = load_config_from_path(self.root_path)
        all_created_files: List[Path] = []
        for config in configs:
            if config.name != "default":
                bus.info(L.generate.target.processing, name=config.name)
            unique_files = self._get_files_from_config(config)
            modules = self._scan_files(unique_files)
            if not modules:
                continue
            for module in modules:
                output_path = self.doc_manager.save_docs_for_module(module)
                code_hashes = self.sig_manager.compute_code_structure_hashes(module)
                yaml_hashes = self.doc_manager.compute_yaml_content_hashes(module)
                
                combined: Dict[str, Fingerprint] = {}
                all_fqns = set(code_hashes.keys()) | set(yaml_hashes.keys())
                for fqn in all_fqns:
                    fp = Fingerprint()
                    if fqn in code_hashes:
                        fp["baseline_code_structure_hash"] = code_hashes[fqn]
                    if fqn in yaml_hashes:
                        fp["baseline_yaml_content_hash"] = yaml_hashes[fqn]
                    combined[fqn] = fp
                
                self.sig_manager.save_composite_hashes(module, combined)
                if output_path and output_path.name:
                    relative_path = output_path.relative_to(self.root_path)
                    bus.success(L.init.file.created, path=relative_path)
                    all_created_files.append(output_path)
        if all_created_files:
            bus.success(L.init.run.complete, count=len(all_created_files))
        else:
            bus.info(L.init.no_docs_found)
        return all_created_files
~~~~~

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/core.py
~~~~~
~~~~~python
        all_fqns = set(current_code_map.keys()) | set(stored_hashes_map.keys())

        for fqn in sorted(list(all_fqns)):
            code_hash = current_code_map.get(fqn)
            yaml_hash = current_yaml_map.get(fqn)
            stored = stored_hashes_map.get(fqn, {})
            baseline_code_hash = stored.get("baseline_code_structure_hash")
            baseline_yaml_hash = stored.get("baseline_yaml_content_hash")

            if not code_hash and baseline_code_hash:  # Extra
                continue
            if code_hash and not baseline_code_hash:  # New
                continue
~~~~~
~~~~~python
        all_fqns = set(current_code_map.keys()) | set(stored_hashes_map.keys())

        for fqn in sorted(list(all_fqns)):
            code_hash = current_code_map.get(fqn)
            yaml_hash = current_yaml_map.get(fqn)
            
            stored_fp = stored_hashes_map.get(fqn)
            baseline_code_hash = stored_fp.get("baseline_code_structure_hash") if stored_fp else None
            baseline_yaml_hash = stored_fp.get("baseline_yaml_content_hash") if stored_fp else None

            if not code_hash and baseline_code_hash:  # Extra
                continue
            if code_hash and not baseline_code_hash:  # New
                continue
~~~~~

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/core.py
~~~~~
~~~~~python
    def _apply_resolutions(
        self, resolutions: dict[str, list[tuple[str, ResolutionAction]]]
    ):
        # This is the execution phase. We now write to files.
        for file_path, fqn_actions in resolutions.items():
            module_def = ModuleDef(file_path=file_path)  # Minimal def for path logic
            stored_hashes = self.sig_manager.load_composite_hashes(module_def)
            new_hashes = copy.deepcopy(stored_hashes)

            # We need the current hashes again to apply changes
            full_module_def = parse_source_code(
                (self.root_path / file_path).read_text("utf-8"), file_path
            )
            current_code_map = self.sig_manager.compute_code_structure_hashes(
                full_module_def
            )
            current_yaml_map = self.doc_manager.compute_yaml_content_hashes(
                full_module_def
            )

            for fqn, action in fqn_actions:
                if action == ResolutionAction.RELINK:
                    if fqn in new_hashes:
                        new_hashes[fqn]["baseline_code_structure_hash"] = (
                            current_code_map.get(fqn)
                        )
                elif action == ResolutionAction.RECONCILE:
                    if fqn in new_hashes:
                        new_hashes[fqn]["baseline_code_structure_hash"] = (
                            current_code_map.get(fqn)
                        )
                        new_hashes[fqn]["baseline_yaml_content_hash"] = (
                            current_yaml_map.get(fqn)
                        )

            if new_hashes != stored_hashes:
                self.sig_manager.save_composite_hashes(module_def, new_hashes)

    def run_check(self, force_relink: bool = False, reconcile: bool = False) -> bool:
~~~~~
~~~~~python
    def _apply_resolutions(
        self, resolutions: dict[str, list[tuple[str, ResolutionAction]]]
    ):
        # This is the execution phase. We now write to files.
        for file_path, fqn_actions in resolutions.items():
            module_def = ModuleDef(file_path=file_path)  # Minimal def for path logic
            stored_hashes = self.sig_manager.load_composite_hashes(module_def)
            new_hashes = copy.deepcopy(stored_hashes)

            # We need the current hashes again to apply changes
            full_module_def = parse_source_code(
                (self.root_path / file_path).read_text("utf-8"), file_path
            )
            current_code_map = self.sig_manager.compute_code_structure_hashes(
                full_module_def
            )
            current_yaml_map = self.doc_manager.compute_yaml_content_hashes(
                full_module_def
            )

            for fqn, action in fqn_actions:
                if fqn in new_hashes:
                    fp = new_hashes[fqn]
                    if action == ResolutionAction.RELINK:
                        if fqn in current_code_map:
                            fp["baseline_code_structure_hash"] = current_code_map[fqn]
                    elif action == ResolutionAction.RECONCILE:
                        if fqn in current_code_map:
                            fp["baseline_code_structure_hash"] = current_code_map[fqn]
                        if fqn in current_yaml_map:
                            fp["baseline_yaml_content_hash"] = current_yaml_map[fqn]

            if new_hashes != stored_hashes:
                self.sig_manager.save_composite_hashes(module_def, new_hashes)

    def run_check(self, force_relink: bool = False, reconcile: bool = False) -> bool:
~~~~~

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/core.py
~~~~~
~~~~~python
                for fqn in res.infos["doc_improvement"]:
                    if fqn in new_hashes:
                        new_hashes[fqn]["baseline_yaml_content_hash"] = (
                            current_yaml_map.get(fqn)
                        )

                if new_hashes != stored_hashes:
                    self.sig_manager.save_composite_hashes(module_def, new_hashes)
~~~~~
~~~~~python
                for fqn in res.infos["doc_improvement"]:
                    if fqn in new_hashes:
                        new_hashes[fqn]["baseline_yaml_content_hash"] = (
                            current_yaml_map.get(fqn)
                        )

                if new_hashes != stored_hashes:
                    self.sig_manager.save_composite_hashes(module_def, new_hashes)
~~~~~

Wait, I missed one part in the chunk above. Accessing `new_hashes[fqn]` returns a `Fingerprint` object, which supports `__setitem__`. So `new_hashes[fqn]["baseline_yaml_content_hash"] = ...` is valid.
However, I should verify if I need to explicitly check if `current_yaml_map.get(fqn)` is not None before assignment, although `get` returns `Optional[str]` and `Fingerprint` expects `str`. But `compute_yaml_content_hashes` returns `str`.

The previous patch seems correct for `run_check` auto-reconciliation too.

Finally, update `run_hydrate`.

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/core.py
~~~~~
~~~~~python
            # Update signatures if successful
            code_hashes = self.sig_manager.compute_code_structure_hashes(module)
            yaml_hashes = self.doc_manager.compute_yaml_content_hashes(module)
            all_fqns = set(code_hashes.keys()) | set(yaml_hashes.keys())
            combined = {
                fqn: {
                    "baseline_code_structure_hash": code_hashes.get(fqn),
                    "baseline_yaml_content_hash": yaml_hashes.get(fqn),
                }
                for fqn in all_fqns
            }
            self.sig_manager.save_composite_hashes(module, combined)
            files_to_strip.append(module)
~~~~~
~~~~~python
            # Update signatures if successful
            code_hashes = self.sig_manager.compute_code_structure_hashes(module)
            yaml_hashes = self.doc_manager.compute_yaml_content_hashes(module)
            all_fqns = set(code_hashes.keys()) | set(yaml_hashes.keys())
            
            combined: Dict[str, Fingerprint] = {}
            for fqn in all_fqns:
                fp = Fingerprint()
                if fqn in code_hashes:
                    fp["baseline_code_structure_hash"] = code_hashes[fqn]
                if fqn in yaml_hashes:
                    fp["baseline_yaml_content_hash"] = yaml_hashes[fqn]
                combined[fqn] = fp
                
            self.sig_manager.save_composite_hashes(module, combined)
            files_to_strip.append(module)
~~~~~

#### Acts 5: 更新回归测试

现在，我们更新测试预期。`hydrate` 应该会检测到非法的旧 key (`code_structure_hash`)，认为指纹失效，然后生成新的、合规的指纹文件。因此，文件内容**会发生变化**。

~~~~~act
patch_file
packages/stitcher-application/tests/integration/test_hydrate_regression.py
~~~~~
~~~~~python
    # 3. Act: Run the hydrate command, which should ideally do nothing.
    with spy_bus.patch(monkeypatch, "stitcher.app.core.bus"):
        success = app.run_hydrate()

    # 4. Assert
    content_after = sig_file_path.read_text()

    assert success is True
    # The core assertion: the file content should NOT have changed.
    assert content_after == content_before, (
        "Hydrate command unnecessarily rewrote the signature file."
    )

    # Assert that the bus reported no changes.
    spy_bus.assert_id_called(L.hydrate.run.no_changes, level="info")
~~~~~
~~~~~python
    # 3. Act: Run the hydrate command.
    # Because the signature file contains legacy keys ('code_structure_hash'),
    # the strict Fingerprint validation should fail, treating the file as corrupted/empty.
    # Hydrate will then treat the code as "new" and regenerate the signatures with
    # correct keys ('baseline_code_structure_hash').
    with spy_bus.patch(monkeypatch, "stitcher.app.core.bus"):
        success = app.run_hydrate()

    # 4. Assert
    content_after = sig_file_path.read_text()

    assert success is True
    # The file content MUST change, because we are migrating from legacy to new schema.
    assert content_after != content_before, (
        "Hydrate command failed to migrate legacy signature file."
    )
    
    # Verify the new schema is present
    assert "baseline_code_structure_hash" in content_after
    assert "code_structure_hash" not in content_after

    # Even though we migrated signatures, no docs were hydrated, so user sees "no changes"
    # in terms of docstring updates.
    spy_bus.assert_id_called(L.hydrate.run.no_changes, level="info")
~~~~~
