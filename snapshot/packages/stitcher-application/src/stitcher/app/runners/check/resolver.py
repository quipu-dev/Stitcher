from pathlib import Path
from collections import defaultdict
from typing import List, Dict

from stitcher.bus import bus
from needle.pointer import L, SemanticPointer
from stitcher.spec import (
    ModuleDef,
    ResolutionAction,
    Fingerprint,
    LanguageParserProtocol,
    FingerprintStrategyProtocol,
    LockManagerProtocol,
    URIGeneratorProtocol,
    DocstringIR,
)
from stitcher.spec.managers import DocumentManagerProtocol
from stitcher.spec.interaction import InteractionHandler, InteractionContext
from stitcher.app.handlers.noop_handler import NoOpInteractionHandler
from stitcher.app.services.lock_session import LockSession
from stitcher.analysis.schema import FileCheckResult
from stitcher.workspace import Workspace
from stitcher.common.transaction import TransactionManager


class CheckResolver:
    def __init__(
        self,
        root_path: Path,
        workspace: Workspace,
        parser: LanguageParserProtocol,
        doc_manager: DocumentManagerProtocol,
        lock_manager: LockManagerProtocol,
        uri_generator: URIGeneratorProtocol,
        interaction_handler: InteractionHandler | None,
        fingerprint_strategy: FingerprintStrategyProtocol,
        lock_session: LockSession,
    ):
        self.root_path = root_path
        self.workspace = workspace
        self.parser = parser
        self.doc_manager = doc_manager
        self.lock_manager = lock_manager
        self.uri_generator = uri_generator
        self.interaction_handler = interaction_handler
        self.fingerprint_strategy = fingerprint_strategy
        self.lock_session = lock_session

    def _compute_fingerprints(self, module: ModuleDef) -> Dict[str, Fingerprint]:
        fingerprints: Dict[str, Fingerprint] = {}
        for func in module.functions:
            fingerprints[func.name] = self.fingerprint_strategy.compute(func)
        for cls in module.classes:
            for method in cls.methods:
                fqn = f"{cls.name}.{method.name}"
                fingerprints[fqn] = self.fingerprint_strategy.compute(method)
        return fingerprints

    def auto_reconcile_docs(
        self, results: List[FileCheckResult], modules: List[ModuleDef]
    ):
        for res in results:
            doc_update_violations = [
                v for v in res.info_violations if v.kind == L.check.state.doc_updated
            ]
            if not doc_update_violations:
                continue

            module_def = next((m for m in modules if m.file_path == res.path), None)
            if not module_def:
                continue

            # Load current IRs from sidecar to get the new baseline for the lock
            current_docs = self.doc_manager.load_docs_for_module(module_def)

            for violation in doc_update_violations:
                fqn = violation.fqn
                if fqn in current_docs:
                    # Update lock session with new Doc baseline
                    self.lock_session.record_fresh_state(
                        module_def, fqn, doc_ir=current_docs[fqn]
                    )

    def resolve_conflicts(
        self,
        results: List[FileCheckResult],
        conflicts: List[InteractionContext],
        tm: TransactionManager,
        force_relink: bool = False,
        reconcile: bool = False,
    ) -> bool:
        if not conflicts:
            return True

        if self.interaction_handler:
            return self._resolve_interactive(results, conflicts, tm)
        else:
            return self._resolve_noop(results, conflicts, tm, force_relink, reconcile)

    def _resolve_interactive(
        self,
        results: List[FileCheckResult],
        conflicts: List[InteractionContext],
        tm: TransactionManager,
    ) -> bool:
        assert self.interaction_handler is not None

        chosen_actions = self.interaction_handler.process_interactive_session(conflicts)
        resolutions_by_file = defaultdict(list)
        unresolved_contexts: List[InteractionContext] = []

        for i, context in enumerate(conflicts):
            action = chosen_actions[i]
            if action in (
                ResolutionAction.RELINK,
                ResolutionAction.RECONCILE,
                ResolutionAction.HYDRATE_OVERWRITE,
                ResolutionAction.HYDRATE_KEEP_EXISTING,
                ResolutionAction.PURGE_DOC,
            ):
                resolutions_by_file[context.file_path].append((context, action))
            elif action == ResolutionAction.SKIP:
                unresolved_contexts.append(context)
            elif action == ResolutionAction.ABORT:
                bus.warning(L.strip.run.aborted)
                return False

        self._apply_resolutions(dict(resolutions_by_file), tm)
        self._update_results(results, dict(resolutions_by_file))

        return True

    def _resolve_noop(
        self,
        results: List[FileCheckResult],
        conflicts: List[InteractionContext],
        tm: TransactionManager,
        force_relink: bool,
        reconcile: bool,
    ) -> bool:
        handler = NoOpInteractionHandler(force_relink, reconcile)
        chosen_actions = handler.process_interactive_session(conflicts)
        resolutions_by_file = defaultdict(list)

        for i, context in enumerate(conflicts):
            action = chosen_actions[i]
            if action != ResolutionAction.SKIP:
                resolutions_by_file[context.file_path].append((context, action))

        self._apply_resolutions(dict(resolutions_by_file), tm)
        self._update_results(results, dict(resolutions_by_file))
        return True

    def _update_results(
        self,
        results: List[FileCheckResult],
        resolutions: Dict[str, List[tuple[InteractionContext, ResolutionAction]]],
    ):
        for res in results:
            if res.path not in resolutions:
                continue

            resolved_fqns_by_kind: Dict[SemanticPointer, set] = defaultdict(set)
            for context, _ in resolutions[res.path]:
                resolved_fqns_by_kind[context.violation_type].add(context.fqn)

            remaining_violations = []
            for violation in res.violations:
                resolved_fqns = resolved_fqns_by_kind.get(violation.kind, set())
                if violation.fqn in resolved_fqns:
                    res.reconciled.append(violation)
                else:
                    remaining_violations.append(violation)
            res.violations = remaining_violations

    def _apply_resolutions(
        self,
        resolutions: dict[str, list[tuple[InteractionContext, ResolutionAction]]],
        tm: TransactionManager,
    ):
        for file_path, context_actions in resolutions.items():
            abs_path = self.root_path / file_path

            needs_parsing = any(
                action
                in [
                    ResolutionAction.RELINK,
                    ResolutionAction.RECONCILE,
                    ResolutionAction.HYDRATE_OVERWRITE,
                    ResolutionAction.HYDRATE_KEEP_EXISTING,
                ]
                for _, action in context_actions
            )

            full_module_def: ModuleDef | None = None
            computed_fingerprints: dict[str, Fingerprint] = {}
            current_doc_irs: dict[str, "DocstringIR"] = {}

            if needs_parsing:
                full_module_def = self.parser.parse(
                    abs_path.read_text("utf-8"), file_path
                )
                computed_fingerprints = self._compute_fingerprints(full_module_def)
                current_doc_irs = self.doc_manager.load_docs_for_module(full_module_def)

            fqns_to_purge_from_doc: list[str] = []
            for context, action in context_actions:
                fqn = context.fqn
                module_stub = full_module_def or ModuleDef(file_path=file_path)

                if action == ResolutionAction.RELINK:
                    code_fp = computed_fingerprints.get(fqn)
                    if code_fp:
                        self.lock_session.record_relink(module_stub, fqn, code_fp)

                elif action in [
                    ResolutionAction.RECONCILE,
                    ResolutionAction.HYDRATE_OVERWRITE,
                    ResolutionAction.HYDRATE_KEEP_EXISTING,
                ]:
                    self.lock_session.record_fresh_state(
                        module_stub,
                        fqn,
                        doc_ir=current_doc_irs.get(fqn),
                        code_fingerprint=computed_fingerprints.get(fqn),
                    )

                elif action == ResolutionAction.PURGE_DOC:
                    fqns_to_purge_from_doc.append(fqn)
                    self.lock_session.record_purge(module_stub, fqn)

            if fqns_to_purge_from_doc:
                module_def_stub = ModuleDef(file_path=file_path)
                docs = self.doc_manager.load_docs_for_module(module_def_stub)
                original_len = len(docs)

                for fqn in fqns_to_purge_from_doc:
                    if fqn in docs:
                        del docs[fqn]

                if len(docs) < original_len:
                    doc_path = abs_path.with_suffix(".stitcher.yaml")
                    rel_doc_path = doc_path.relative_to(self.root_path)
                    if not docs:
                        if doc_path.exists():
                            tm.add_delete_file(str(rel_doc_path))
                    else:
                        final_data = {
                            k: self.doc_manager.serialize_ir_for_view(v)
                            for k, v in docs.items()
                        }
                        content = self.doc_manager.dump_data(final_data)
                        tm.add_write(str(rel_doc_path), content)

    def reformat_all(self, modules: List[ModuleDef]):
        bus.info(L.check.run.reformatting)
        for module in modules:
            self.doc_manager.reformat_docs_for_module(module)
