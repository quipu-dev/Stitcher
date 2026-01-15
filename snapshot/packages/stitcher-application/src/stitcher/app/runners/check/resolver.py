from pathlib import Path
from collections import defaultdict
from typing import List, Dict

from stitcher.common import bus
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
        # Helper duplicated here for simplicity in applying updates,
        # ideally this logic belongs to a shared utility or service.
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
        # Group by package to batch lock updates
        updates_by_pkg: Dict[Path, Dict[str, Fingerprint]] = defaultdict(dict)

        # Pre-load needed lock data? Or load on demand.
        # Since this is auto-reconcile, we iterate results.

        for res in results:
            doc_update_violations = [
                v for v in res.info_violations if v.kind == L.check.state.doc_updated
            ]
            if not doc_update_violations:
                continue

            module_def = next((m for m in modules if m.file_path == res.path), None)
            if not module_def:
                continue

            abs_path = self.root_path / module_def.file_path
            pkg_root = self.workspace.find_owning_package(abs_path)
            ws_rel_path = self.workspace.to_workspace_relative(abs_path)

            # Load lock only if not already loaded for this batch?
            # For simplicity, we load fresh, update in memory, then save later.
            # But here we need cumulative updates.
            if pkg_root not in updates_by_pkg:
                updates_by_pkg[pkg_root] = self.lock_manager.load(pkg_root)

            lock_data = updates_by_pkg[pkg_root]
            current_yaml_map = self.doc_manager.compute_yaml_content_hashes(module_def)

            for violation in doc_update_violations:
                fqn = violation.fqn
                suri = self.uri_generator.generate_symbol_uri(ws_rel_path, fqn)

                if suri in lock_data:
                    fp = lock_data[suri]
                    new_yaml_hash = current_yaml_map.get(fqn)

                    if new_yaml_hash is not None:
                        fp["baseline_yaml_content_hash"] = new_yaml_hash
                    elif "baseline_yaml_content_hash" in fp:
                        del fp["baseline_yaml_content_hash"]

        # Save all updated locks
        for pkg_root, lock_data in updates_by_pkg.items():
            self.lock_manager.save(pkg_root, lock_data)

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

        # Unresolved conflicts are kept in the violations list, so no action needed.
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

            # Filter out violations that have been resolved and move them to reconciled
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
        # Process file-by-file, as each might need parsing.
        # LockSession will handle aggregation by package root internally.
        for file_path, context_actions in resolutions.items():
            abs_path = self.root_path / file_path

            # Determine if we need to parse the file to get current state
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

            # --- Data Loading (on demand) ---
            full_module_def: ModuleDef | None = None
            computed_fingerprints: dict[str, Fingerprint] = {}
            current_doc_irs: dict[str, "DocstringIR"] = {}

            if needs_parsing:
                full_module_def = self.parser.parse(
                    abs_path.read_text("utf-8"), file_path
                )
                computed_fingerprints = self._compute_fingerprints(full_module_def)
                current_doc_irs = self.doc_manager.load_docs_for_module(full_module_def)

            # --- Action Execution ---
            fqns_to_purge_from_doc: list[str] = []
            for context, action in context_actions:
                fqn = context.fqn
                # Use a lightweight stub for purge actions if we didn't parse
                module_stub = full_module_def or ModuleDef(file_path=file_path)

                if action == ResolutionAction.RELINK:
                    code_fp = computed_fingerprints.get(fqn)
                    if code_fp:
                        self.lock_session.record_relink(module_stub, fqn, code_fp)

                elif (
                    action
                    in [
                        ResolutionAction.RECONCILE,
                        ResolutionAction.HYDRATE_OVERWRITE,
                        ResolutionAction.HYDRATE_KEEP_EXISTING,  # In check, this is a reconcile
                    ]
                ):
                    self.lock_session.record_fresh_state(
                        module_stub,
                        fqn,
                        doc_ir=current_doc_irs.get(fqn),
                        code_fingerprint=computed_fingerprints.get(fqn),
                    )

                elif action == ResolutionAction.PURGE_DOC:
                    fqns_to_purge_from_doc.append(fqn)
                    self.lock_session.record_purge(module_stub, fqn)

            # --- Sidecar Doc File Updates (Transactional) ---
            if fqns_to_purge_from_doc:
                # Create a stub ModuleDef to pass to the doc manager
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
        # Reformatting only applies to docs now. Lock file is auto-formatted on save.
        for module in modules:
            self.doc_manager.reformat_docs_for_module(module)
