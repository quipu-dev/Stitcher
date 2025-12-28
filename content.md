好的，根据基础设施的就绪状态，我将生成执行 **Application Layer (Diff 生成/保存)** 和 **UI Layer (Diff 渲染)** 变更的计划。

这将分为两个主要部分：
1.  **`stitcher-application`**: 修改 `core.py` 以集成 `difflib`，并在 `init`/`pump` 时保存签名文本，在 `check`/`pump` 时生成差异。
2.  **`stitcher-cli`**: 修改 `interactive.py` 以美观地渲染这些差异。

简要回答：
将通过修改 `core.py` 实现签名文本的持久化和差异生成逻辑，并更新 CLI 的 `interactive.py` 以支持差异的彩色渲染。

## [WIP] feat: 实现 viewdiff 核心逻辑与 UI 渲染

### 用户需求
在交互式解决冲突（`check` 或 `pump`）时，用户目前只能看到冲突的键名，处于“盲选”状态。用户希望直接在 CLI 中看到具体的差异（Diff），以便做出明智的决策。

### 评论
这是一个极高价值的 DX 改进。通过在 `check`（签名漂移）和 `pump`（文档冲突）阶段提供上下文差异，Stitcher 将从一个单纯的报错工具转变为一个辅助决策工具。由于基础设施（Protocol 和 Fingerprint 验证）已支持携带 diff 和 text 字段，此计划主要关注业务逻辑的串联。

### 目标
1.  **持久化签名文本**: 在 `init` 和 `pump` 时，除了保存哈希，还要保存 `baseline_code_signature_text` 到签名文件中。
2.  **生成差异**:
    *   `check`: 在检测到 `SIGNATURE_DRIFT` 或 `CO_EVOLUTION` 时，对比当前代码签名与基线签名，生成 `signature_diff`。
    *   `pump`: 在检测到 `DOC_CONTENT_CONFLICT` 时，对比当前代码文档与 YAML 文档，生成 `doc_diff`。
3.  **渲染差异**: 在 CLI 交互界面中，自动展示生成的 diff，并使用红/绿颜色高亮差异行。

### 基本原理
*   **Diff 引擎**: 使用 Python 标准库 `difflib.unified_diff` 生成差异。
*   **数据流**: `StitcherApp` 负责生成数据并填充到 `InteractionContext` 中 -> `TyperInteractiveRenderer` 负责消费并展示数据。
*   **签名文本存储**: 利用 `Fingerprint` 类已有的灵活键值验证机制 (`^(baseline|current)_[a-z]+_[a-z]+_(hash|text)$`)，新增 `baseline_code_signature_text` 字段，无需修改 Schema。

### 标签
#intent/build #flow/ready #priority/high #comp/runtime #comp/cli #concept/ui #scope/ux #ai/instruct #task/domain/ui #task/object/viewdiff #task/action/implementation #task/state/continue

---

### Script

#### Acts 1: 更新 StitcherApp 核心逻辑

我们将修改 `core.py`。
1.  引入 `difflib`。
2.  在 `run_init` 和 `run_pump` 的保存阶段，调用 `extract_signature_texts` 并保存为 `baseline_code_signature_text`。
3.  在 `_analyze_file` (用于 `check`) 中，生成签名 Diff。
4.  在 `run_pump` 的分析阶段，生成文档 Diff。

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/core.py
~~~~~
~~~~~python.old
import copy
from pathlib import Path
from typing import Dict, List, Optional
from collections import defaultdict
from dataclasses import dataclass, field

from stitcher.scanner import (
~~~~~
~~~~~python.new
import copy
import difflib
from pathlib import Path
from typing import Dict, List, Optional
from collections import defaultdict
from dataclasses import dataclass, field

from stitcher.scanner import (
~~~~~

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/core.py
~~~~~
~~~~~python.old
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

    def _analyze_file(
        self, module: ModuleDef
    ) -> tuple[FileCheckResult, list[InteractionContext]]:
        result = FileCheckResult(path=module.file_path)
        unresolved_conflicts: list[InteractionContext] = []

        # Content checks (unchanged)
        if (self.root_path / module.file_path).with_suffix(".stitcher.yaml").exists():
            doc_issues = self.doc_manager.check_module(module)
            result.warnings["missing"].extend(doc_issues["missing"])
            result.warnings["redundant"].extend(doc_issues["redundant"])
            result.errors["pending"].extend(doc_issues["pending"])
            result.errors["conflict"].extend(doc_issues["conflict"])
            result.errors["extra"].extend(doc_issues["extra"])

        # State machine analysis
        is_tracked = (
            (self.root_path / module.file_path).with_suffix(".stitcher.yaml").exists()
        )
        current_code_map = self.sig_manager.compute_code_structure_hashes(module)
        current_yaml_map = self.doc_manager.compute_yaml_content_hashes(module)
        stored_hashes_map = self.sig_manager.load_composite_hashes(module)

        all_fqns = set(current_code_map.keys()) | set(stored_hashes_map.keys())

        for fqn in sorted(list(all_fqns)):
            code_hash = current_code_map.get(fqn)
            yaml_hash = current_yaml_map.get(fqn)

            stored_fp = stored_hashes_map.get(fqn)
            baseline_code_hash = (
                stored_fp.get("baseline_code_structure_hash") if stored_fp else None
            )
            baseline_yaml_hash = (
                stored_fp.get("baseline_yaml_content_hash") if stored_fp else None
            )

            if not code_hash and baseline_code_hash:  # Extra
                continue
            if code_hash and not baseline_code_hash:  # New
                continue

            code_matches = code_hash == baseline_code_hash
            yaml_matches = yaml_hash == baseline_yaml_hash

            if code_matches and not yaml_matches:  # Doc improvement
                result.infos["doc_improvement"].append(fqn)
            elif not code_matches and yaml_matches:  # Signature Drift
                unresolved_conflicts.append(
                    InteractionContext(
                        module.file_path, fqn, ConflictType.SIGNATURE_DRIFT
                    )
                )
            elif not code_matches and not yaml_matches:  # Co-evolution
                unresolved_conflicts.append(
                    InteractionContext(module.file_path, fqn, ConflictType.CO_EVOLUTION)
                )

        # Untracked file check
~~~~~
~~~~~python.new
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
                code_texts = self.sig_manager.extract_signature_texts(module)
                yaml_hashes = self.doc_manager.compute_yaml_content_hashes(module)

                combined: Dict[str, Fingerprint] = {}
                all_fqns = set(code_hashes.keys()) | set(yaml_hashes.keys())
                for fqn in all_fqns:
                    fp = Fingerprint()
                    if fqn in code_hashes:
                        fp["baseline_code_structure_hash"] = code_hashes[fqn]
                    if fqn in code_texts:
                        fp["baseline_code_signature_text"] = code_texts[fqn]
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

    def _generate_diff(self, a: str, b: str, label_a: str, label_b: str) -> str:
        return "\n".join(
            difflib.unified_diff(
                a.splitlines(),
                b.splitlines(),
                fromfile=label_a,
                tofile=label_b,
                lineterm="",
            )
        )

    def _analyze_file(
        self, module: ModuleDef
    ) -> tuple[FileCheckResult, list[InteractionContext]]:
        result = FileCheckResult(path=module.file_path)
        unresolved_conflicts: list[InteractionContext] = []

        # Content checks (unchanged)
        if (self.root_path / module.file_path).with_suffix(".stitcher.yaml").exists():
            doc_issues = self.doc_manager.check_module(module)
            result.warnings["missing"].extend(doc_issues["missing"])
            result.warnings["redundant"].extend(doc_issues["redundant"])
            result.errors["pending"].extend(doc_issues["pending"])
            result.errors["conflict"].extend(doc_issues["conflict"])
            result.errors["extra"].extend(doc_issues["extra"])

        # State machine analysis
        is_tracked = (
            (self.root_path / module.file_path).with_suffix(".stitcher.yaml").exists()
        )
        current_code_map = self.sig_manager.compute_code_structure_hashes(module)
        current_yaml_map = self.doc_manager.compute_yaml_content_hashes(module)
        current_sig_texts = self.sig_manager.extract_signature_texts(module)
        stored_hashes_map = self.sig_manager.load_composite_hashes(module)

        all_fqns = set(current_code_map.keys()) | set(stored_hashes_map.keys())

        for fqn in sorted(list(all_fqns)):
            code_hash = current_code_map.get(fqn)
            yaml_hash = current_yaml_map.get(fqn)

            stored_fp = stored_hashes_map.get(fqn)
            baseline_code_hash = (
                stored_fp.get("baseline_code_structure_hash") if stored_fp else None
            )
            baseline_yaml_hash = (
                stored_fp.get("baseline_yaml_content_hash") if stored_fp else None
            )
            baseline_sig_text = (
                stored_fp.get("baseline_code_signature_text") if stored_fp else None
            )

            if not code_hash and baseline_code_hash:  # Extra
                continue
            if code_hash and not baseline_code_hash:  # New
                continue

            code_matches = code_hash == baseline_code_hash
            yaml_matches = yaml_hash == baseline_yaml_hash

            if code_matches and not yaml_matches:  # Doc improvement
                result.infos["doc_improvement"].append(fqn)
            elif not code_matches:
                # Signature changed (either Drift or Co-evolution)
                sig_diff = None
                if baseline_sig_text and fqn in current_sig_texts:
                    sig_diff = self._generate_diff(
                        baseline_sig_text,
                        current_sig_texts[fqn],
                        "baseline",
                        "current",
                    )
                elif fqn in current_sig_texts:
                    sig_diff = f"(No baseline signature stored)\n+++ current\n{current_sig_texts[fqn]}"

                conflict_type = (
                    ConflictType.SIGNATURE_DRIFT
                    if yaml_matches
                    else ConflictType.CO_EVOLUTION
                )

                unresolved_conflicts.append(
                    InteractionContext(
                        module.file_path, fqn, conflict_type, signature_diff=sig_diff
                    )
                )

        # Untracked file check
~~~~~

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/core.py
~~~~~
~~~~~python.old
    def run_pump(
        self, strip: bool = False, force: bool = False, reconcile: bool = False
    ) -> PumpResult:
        bus.info(L.pump.run.start)
        configs, _ = load_config_from_path(self.root_path)

        all_modules: List[ModuleDef] = []
        all_conflicts: List[InteractionContext] = []

        # 1. Analysis Phase (Dry Run)
        for config in configs:
            if config.name != "default":
                bus.info(L.generate.target.processing, name=config.name)
            unique_files = self._get_files_from_config(config)
            modules = self._scan_files(unique_files)
            if not modules:
                continue
            all_modules.extend(modules)

            for module in modules:
                # Dry run to detect conflicts
                res = self.doc_manager.hydrate_module(
                    module, force=force, reconcile=reconcile, dry_run=True
                )
                if not res["success"]:
                    for key in res["conflicts"]:
                        all_conflicts.append(
                            InteractionContext(
                                module.file_path, key, ConflictType.DOC_CONTENT_CONFLICT
                            )
                        )

        # 2. Decision Phase
~~~~~
~~~~~python.new
    def run_pump(
        self, strip: bool = False, force: bool = False, reconcile: bool = False
    ) -> PumpResult:
        bus.info(L.pump.run.start)
        configs, _ = load_config_from_path(self.root_path)

        all_modules: List[ModuleDef] = []
        all_conflicts: List[InteractionContext] = []

        # 1. Analysis Phase (Dry Run)
        for config in configs:
            if config.name != "default":
                bus.info(L.generate.target.processing, name=config.name)
            unique_files = self._get_files_from_config(config)
            modules = self._scan_files(unique_files)
            if not modules:
                continue
            all_modules.extend(modules)

            for module in modules:
                # Dry run to detect conflicts
                res = self.doc_manager.hydrate_module(
                    module, force=force, reconcile=reconcile, dry_run=True
                )
                if not res["success"]:
                    # Generate content diffs for conflicts
                    source_docs = self.doc_manager.flatten_module_docs(module)
                    yaml_docs = self.doc_manager.load_docs_for_module(module)

                    for key in res["conflicts"]:
                        doc_diff = None
                        if key in source_docs and key in yaml_docs:
                            doc_diff = self._generate_diff(
                                yaml_docs[key], source_docs[key], "yaml", "code"
                            )

                        all_conflicts.append(
                            InteractionContext(
                                module.file_path,
                                key,
                                ConflictType.DOC_CONTENT_CONFLICT,
                                doc_diff=doc_diff,
                            )
                        )

        # 2. Decision Phase
~~~~~

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/core.py
~~~~~
~~~~~python.old
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
~~~~~
~~~~~python.new
            # Update signatures if successful
            code_hashes = self.sig_manager.compute_code_structure_hashes(module)
            code_texts = self.sig_manager.extract_signature_texts(module)
            yaml_hashes = self.doc_manager.compute_yaml_content_hashes(module)
            all_fqns = set(code_hashes.keys()) | set(yaml_hashes.keys())

            combined: Dict[str, Fingerprint] = {}
            for fqn in all_fqns:
                fp = Fingerprint()
                if fqn in code_hashes:
                    fp["baseline_code_structure_hash"] = code_hashes[fqn]
                if fqn in code_texts:
                    fp["baseline_code_signature_text"] = code_texts[fqn]
                if fqn in yaml_hashes:
                    fp["baseline_yaml_content_hash"] = yaml_hashes[fqn]
                combined[fqn] = fp

            self.sig_manager.save_composite_hashes(module, combined)
~~~~~

#### Acts 2: 更新交互式渲染器 (UI)

我们将修改 `TyperInteractiveRenderer` 以支持 diff 显示。

~~~~~act
patch_file
packages/stitcher-cli/src/stitcher/cli/interactive.py
~~~~~
~~~~~python.old
        # Reason
        reason_map = {
            ConflictType.SIGNATURE_DRIFT: L.interactive.reason.signature_drift,
            ConflictType.CO_EVOLUTION: L.interactive.reason.co_evolution,
            ConflictType.DOC_CONTENT_CONFLICT: L.interactive.reason.doc_content_conflict,
        }
        reason_l = reason_map.get(context.conflict_type)
        if reason_l:
            typer.secho("  " + self.nexus.get(reason_l), fg=typer.colors.YELLOW)

        # Prompt
        typer.echo("  " + self.nexus.get(L.interactive.prompt))
~~~~~
~~~~~python.new
        # Reason
        reason_map = {
            ConflictType.SIGNATURE_DRIFT: L.interactive.reason.signature_drift,
            ConflictType.CO_EVOLUTION: L.interactive.reason.co_evolution,
            ConflictType.DOC_CONTENT_CONFLICT: L.interactive.reason.doc_content_conflict,
        }
        reason_l = reason_map.get(context.conflict_type)
        if reason_l:
            typer.secho("  " + self.nexus.get(reason_l), fg=typer.colors.YELLOW)

        # View Diff
        if context.signature_diff:
            typer.echo("")
            typer.secho("  [ SIGNATURE DIFF ]", bold=True)
            for line in context.signature_diff.splitlines():
                color = None
                if line.startswith("+"):
                    color = typer.colors.GREEN
                elif line.startswith("-"):
                    color = typer.colors.RED
                typer.secho(f"  {line}", fg=color)

        if context.doc_diff:
            typer.echo("")
            typer.secho("  [ DOCSTRING DIFF ]", bold=True)
            for line in context.doc_diff.splitlines():
                color = None
                if line.startswith("+"):
                    color = typer.colors.GREEN
                elif line.startswith("-"):
                    color = typer.colors.RED
                typer.secho(f"  {line}", fg=color)

        # Prompt
        typer.echo("\n  " + self.nexus.get(L.interactive.prompt))
~~~~~

### 下一步建议
运行 `check` 和 `pump` 的集成测试，验证 `InteractionContext` 中是否正确生成并传递了 diff 文本。特别是要验证 `baseline` 缺失时的回退行为，以及 `relink` 操作后签名文本是否正确更新到了存储中。
