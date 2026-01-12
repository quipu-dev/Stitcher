I see the errors. My previous refactoring was incomplete and caused a circular dependency by overwriting `protocols.py` and also missed updating some call sites after purifying the manager protocols. My apologies.

I will now generate a plan to fix these issues. The core problem is that `SymbolState` and `CheckSubject`, which are internal types/protocols for the `check` runner, were removed from `protocols.py` when I added the new `Check...Protocol` definitions. The correct approach is to have them all in the same file. Additionally, I need to fix the remaining call sites that were using the old, impure protocol methods.

## [WIP] fix: Correct check runner protocols and fix broken call sites

### 错误分析
1.  **`ImportError` & `pyright` Symbol Errors**: My previous `write_file` operation on `.../check/protocols.py` overwrote the existing file that contained `SymbolState` and `CheckSubject`. This broke all imports depending on them. The correct action is to merge the old content with the new protocol definitions in that file.
2.  **`pyright` Attribute Errors**: The protocol purification in the last step (removing `_serialize_ir`, `adapter`, etc.) was not applied to all call sites. `CheckResolver` and `ASTCheckSubjectAdapter` are still attempting to use these removed attributes, causing type errors.

### 用户需求
The user needs to fix the build and type-checking errors that arose from the previous refactoring attempt. This involves correcting the protocol definitions and updating all related code to use the new, purified interfaces.

### 评论
This fix addresses an oversight in the refactoring process. By consolidating all `check`-related protocols and data classes into a single file and updating the remaining incorrect call sites, we complete the dependency injection refactoring for `CheckRunner`, making it fully testable and decoupled from its sub-components as intended.

### 目标
1.  **Restore `protocols.py`**: Re-create `packages/stitcher-application/src/stitcher/app/runners/check/protocols.py` with the correct, combined content, including `SymbolState`, `CheckSubject`, and the new `...Protocol` definitions.
2.  **Fix `CheckResolver`**: Update `_apply_resolutions` to use the new `doc_manager.serialize_ir` and `doc_manager.dump_data` methods instead of the removed private attributes.
3.  **Fix `ASTCheckSubjectAdapter`**: Update `get_all_symbol_states` to use `doc_manager.compute_ir_hash(ir)` which correctly encapsulates the serialization and hashing logic.

### 基本原理
This plan corrects the implementation of the Dependency Injection pattern started previously. By providing the complete and correct set of abstractions (protocols and data classes) and ensuring all client code adheres to these abstractions, we resolve the import errors and type inconsistencies.

### 标签
#intent/fix #flow/ready #priority/critical #comp/runtime #comp/interfaces #scope/core #ai/instruct #task/domain/architecture #task/object/dependency-injection #task/action/bug-fix #task/state/continue

---

### Script

#### Acts 1: Restore and Combine Protocol Definitions

I will use `write_file` to create the correct, consolidated `protocols.py`.

~~~~~act
write_file
packages/stitcher-application/src/stitcher/app/runners/check/protocols.py
~~~~~
~~~~~python
from typing import Protocol, Dict, Optional, List, Tuple
from dataclasses import dataclass

from stitcher.spec import DocstringIR, ModuleDef
from stitcher.spec.interaction import InteractionContext
from stitcher.app.types import FileCheckResult


@dataclass
class SymbolState:
    fqn: str
    is_public: bool

    # --- Source Code State (Current) ---
    exists_in_code: bool
    source_doc_content: Optional[str]
    signature_hash: Optional[str]
    signature_text: Optional[str]

    # --- YAML Documentation State (Current) ---
    exists_in_yaml: bool
    yaml_doc_ir: Optional[DocstringIR]
    yaml_content_hash: Optional[str]

    # --- Baseline State (Stored) ---
    baseline_signature_hash: Optional[str]
    baseline_signature_text: Optional[str]
    baseline_yaml_content_hash: Optional[str]


class CheckSubject(Protocol):
    @property
    def file_path(self) -> str: ...

    def is_documentable(self) -> bool: ...

    def get_all_symbol_states(self) -> Dict[str, SymbolState]: ...


class CheckAnalyzerProtocol(Protocol):
    def analyze_subject(
        self, subject: "CheckSubject"
    ) -> Tuple[FileCheckResult, List[InteractionContext]]: ...


class CheckResolverProtocol(Protocol):
    def auto_reconcile_docs(
        self, results: List[FileCheckResult], modules: List[ModuleDef]
    ): ...

    def resolve_conflicts(
        self,
        results: List[FileCheckResult],
        conflicts: List[InteractionContext],
        force_relink: bool = False,
        reconcile: bool = False,
    ) -> bool: ...

    def reformat_all(self, modules: List[ModuleDef]): ...


class CheckReporterProtocol(Protocol):
    def report(self, results: List[FileCheckResult]) -> bool: ...
~~~~~

#### Acts 2: Fix `CheckResolver` Usage of Deprecated Protocol Methods

I'll update `CheckResolver` to use the new public methods on the `DocumentManagerProtocol`.

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/runners/check/resolver.py
~~~~~
~~~~~python.old
                    if doc_path.exists():
                        doc_path.unlink()
                else:
                    final_data = {
                        k: self.doc_manager._serialize_ir(v) for k, v in docs.items()
                    }
                    self.doc_manager.adapter.save(doc_path, final_data)

    def reformat_all(self, modules: List[ModuleDef]):
        bus.info(L.check.run.reformatting)
~~~~~
~~~~~python.new
                    if doc_path.exists():
                        doc_path.unlink()
                else:
                    final_data = {
                        k: self.doc_manager.serialize_ir(v) for k, v in docs.items()
                    }
                    content = self.doc_manager.dump_data(final_data)
                    doc_path.write_text(content, encoding="utf-8")

    def reformat_all(self, modules: List[ModuleDef]):
        bus.info(L.check.run.reformatting)
~~~~~

#### Acts 3: Fix `ASTCheckSubjectAdapter` Hashing Logic

Finally, I'll update `ASTCheckSubjectAdapter` to use the new `compute_ir_hash` method.

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/runners/check/subject.py
~~~~~
~~~~~python.old
    def get_all_symbol_states(self) -> Dict[str, SymbolState]:
        # 1. Load data from all sources
        symbols_from_db = self._index_store.get_symbols_by_file_path(self.file_path)
        yaml_docs = self._doc_manager.load_docs_for_path(self.file_path)
        stored_hashes = self._sig_manager.load_composite_hashes(self.file_path)

        yaml_content_hashes = {
            fqn: self._doc_manager.compute_yaml_content_hash(
                self._doc_manager._serialize_ir(ir)
            )
            for fqn, ir in yaml_docs.items()
        }

        # 2. Map symbols for easy lookup
        symbol_map: Dict[str, SymbolRecord] = {}
~~~~~
~~~~~python.new
    def get_all_symbol_states(self) -> Dict[str, SymbolState]:
        # 1. Load data from all sources
        symbols_from_db = self._index_store.get_symbols_by_file_path(self.file_path)
        yaml_docs = self._doc_manager.load_docs_for_path(self.file_path)
        stored_hashes = self._sig_manager.load_composite_hashes(self.file_path)

        yaml_content_hashes = {
            fqn: self._doc_manager.compute_ir_hash(ir)
            for fqn, ir in yaml_docs.items()
        }

        # 2. Map symbols for easy lookup
        symbol_map: Dict[str, SymbolRecord] = {}
~~~~~

### 下一步建议
现在 `CheckRunner` 的依赖注入重构已经完成并修正。我们可以继续将此模式应用到 `PumpRunner` 等其他复杂 Runner，以实现整个应用层依赖管理的一致性。
