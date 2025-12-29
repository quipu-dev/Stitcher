好的，你的决策非常清晰且安全。**禁用 "跳过" 选项是现阶段最负责任的做法**，因为它彻底杜绝了用户在不知情的情况下因 `strip` 操作而丢失文档字符串的风险。

我们立即开始实施阶段一。

我将生成一个完整的计划，该计划包含我们最终达成共识的所有要点：
1.  **统一解析器**: 所有命令都将使用 Griffe 进行代码分析。
2.  **原子化 `pump` 逻辑**: `pump` 命令中的用户决策将原子化地更新代码和文档的状态。
3.  **禁用 `pump` 中的“跳过”**: 为了防止数据丢失，暂时从 `pump` 的交互流程中移除“跳过”选项。

这是最终的执行计划。

## [WIP] refactor(app): 实现原子化 pump 逻辑并统一解析器

### 用户需求
`stitcher pump` 命令存在一个严重的设计缺陷：它会在执行过程中，不经用户确认就将被修改代码的新签名保存为基线，从而导致后续的 `stitcher check` 命令无法检测到本应存在的“签名漂移”错误。此外，如果用户在 `pump` 中“跳过”一个冲突，后续的 `strip` 命令仍会移除该函数的文档字符串，造成数据丢失。

### 评论
这是一个至关重要的、根本性的修复，旨在恢复系统的状态完整性和用户信任。本次重构将实施“由文档驱动的状态协调”原则，确保用户在 `pump` 中所做的每一个决策（无论是接受代码文档还是保留 YAML 文档）都能原子化地、正确地更新所有相关的签名基线。为了配合当前文件级 `strip` 的能力，我们暂时禁用 `pump` 中的“跳过”选项，作为一项关键的安全措施，以杜绝任何数据丢失的可能性。

### 目标
1.  **重构 `StitcherApp.run_pump`**: 实现新的状态更新逻辑，确保用户决策（`Force-hydrate` 或 `Reconcile`）能够原子性地更新代码结构哈希和文档内容哈希。
2.  **禁用 `pump` 的“跳过”选项**: 修改 `TyperInteractionHandler`，在处理 `pump` 命令的文档内容冲突时，不向用户提供“跳过”选项，强制用户做出明确决策。
3.  **统一解析器**: 修改 `make_app` 工厂，强制所有命令使用 `GriffePythonParser`，以确保所有签名计算逻辑的一致性。
4.  **清理调用点**: 移除所有命令中对 `make_app` 的 `parser_type` 参数传递。

### 基本原理
我们通过实施两个关键的架构原则来解决问题：
1.  **原子化状态更新**: 用户在 `pump` 中的决策将被视为一个完整的事务。选择 `Force-hydrate` (代码优先) 会同时更新 YAML 文件和代码签名基线。选择 `Reconcile` (YAML 优先) 会保持 YAML 不变，但仍更新代码签名基线以反映代码的当前状态。这确保了 `pump` 之后系统总是处于一致状态。
2.  **单一事实来源**: 所有代码的**读取和分析**操作将统一使用 Griffe。所有代码的**转换和写入**操作将继续使用 LibCST (`PythonTransformer`)。这确保了跨命令的一致性。

### 标签
#intent/fix #intent/refine #flow/ready #priority/critical #comp/application #comp/cli #concept/state #concept/parser #scope/core #scope/ux #ai/brainstorm #task/domain/architecture #task/object/state-integrity #task/action/refactor #task/state/continue

---
### Script

#### Acts 1: 重构 `run_pump` 以实现原子化状态更新

这是核心修复。我们将替换 `run_pump` 方法中陈旧的、会造成状态腐化的签名更新逻辑，代之以新的、能够根据用户决策进行精确状态更新的逻辑。

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/core.py
~~~~~
~~~~~python.old
            # Update signatures if successful
            computed_fingerprints = self.sig_manager.compute_fingerprints(module)
            yaml_hashes = self.doc_manager.compute_yaml_content_hashes(module)
            all_fqns = set(computed_fingerprints.keys()) | set(yaml_hashes.keys())

            combined: Dict[str, Fingerprint] = {}
            for fqn in all_fqns:
                fp = computed_fingerprints.get(fqn, Fingerprint())

                # Convert 'current' to 'baseline'
                if "current_code_structure_hash" in fp:
                    fp["baseline_code_structure_hash"] = fp[
                        "current_code_structure_hash"
                    ]
                    del fp["current_code_structure_hash"]

                if "current_code_signature_text" in fp:
                    fp["baseline_code_signature_text"] = fp[
                        "current_code_signature_text"
                    ]
                    del fp["current_code_signature_text"]

                if fqn in yaml_hashes:
                    fp["baseline_yaml_content_hash"] = yaml_hashes[fqn]
                combined[fqn] = fp

            self.sig_manager.save_composite_hashes(module, combined)

            # Collect candidates for stripping
~~~~~
~~~~~python.new
            # Update signatures based on hydration results
            if result["updated_keys"] or result["reconciled_keys"]:
                stored_hashes = self.sig_manager.load_composite_hashes(module)
                new_hashes = copy.deepcopy(stored_hashes)
                computed_fingerprints = self.sig_manager.compute_fingerprints(module)
                current_yaml_map = self.doc_manager.compute_yaml_content_hashes(
                    module
                )

                # For keys where code doc was authoritative (updated)
                for fqn in result["updated_keys"]:
                    fp = computed_fingerprints.get(fqn, Fingerprint())
                    # Convert current to baseline for both code and doc
                    if "current_code_structure_hash" in fp:
                        fp["baseline_code_structure_hash"] = fp[
                            "current_code_structure_hash"
                        ]
                        del fp["current_code_structure_hash"]
                    if "current_code_signature_text" in fp:
                        fp["baseline_code_signature_text"] = fp[
                            "current_code_signature_text"
                        ]
                        del fp["current_code_signature_text"]
                    if fqn in current_yaml_map:
                        fp["baseline_yaml_content_hash"] = current_yaml_map[fqn]
                    new_hashes[fqn] = fp

                # For keys where yaml doc was authoritative (reconciled)
                for fqn in result["reconciled_keys"]:
                    fp = new_hashes.get(fqn, Fingerprint())
                    current_fp = computed_fingerprints.get(fqn, Fingerprint())
                    # only update code baseline
                    if "current_code_structure_hash" in current_fp:
                        fp["baseline_code_structure_hash"] = current_fp[
                            "current_code_structure_hash"
                        ]
                    if "current_code_signature_text" in current_fp:
                        fp["baseline_code_signature_text"] = current_fp[
                            "current_code_signature_text"
                        ]
                    new_hashes[fqn] = fp

                self.sig_manager.save_composite_hashes(module, new_hashes)

            # Collect candidates for stripping
~~~~~

#### Acts 2: 在 `pump` 交互中禁用“跳过”选项

为了防止因文件级 `strip` 造成的数据丢失，我们暂时从 `pump` 命令的交互式冲突解决流程中移除“跳过”(`Skip`)选项。

~~~~~act
patch_file
packages/stitcher-cli/src/stitcher/cli/handlers.py
~~~~~
~~~~~python.old
                    )
                )

            options.append(
                SemanticMenuOption(
                    key="s",
                    action=ResolutionAction.SKIP,
                    label_id=L.interactive.option.skip.label,
                    desc_id=L.interactive.option.skip.desc,
                )
            )
            options.append(
                SemanticMenuOption(
~~~~~
~~~~~python.new
                    )
                )
                # NOTE: Skip is disabled for pump to prevent data loss with file-level strip
                if context.conflict_type != ConflictType.DOC_CONTENT_CONFLICT:
                    options.append(
                        SemanticMenuOption(
                            key="s",
                            action=ResolutionAction.SKIP,
                            label_id=L.interactive.option.skip.label,
                            desc_id=L.interactive.option.skip.desc,
                        )
                    )

            options.append(
                SemanticMenuOption(
~~~~~

#### Acts 3: 统一应用工厂及所有调用点

我们将修改核心工厂和所有命令，以强制使用 Griffe 作为唯一的代码解析器。

~~~~~act
patch_file
packages/stitcher-cli/src/stitcher/cli/factories.py
~~~~~
~~~~~python.old
def make_app(
    handler: Optional[InteractionHandler] = None,
    parser_type: str = "cst",
) -> StitcherApp:
    # Composition Root: Assemble the dependencies
    if parser_type == "griffe":
        parser = GriffePythonParser()
    else:
        parser = PythonParser()

    transformer = PythonTransformer()
~~~~~
~~~~~python.new
def make_app(
    handler: Optional[InteractionHandler] = None,
) -> StitcherApp:
    # Composition Root: Assemble the dependencies
    # UNIFIED: Always use Griffe for analysis
    parser = GriffePythonParser()

    transformer = PythonTransformer()
~~~~~
~~~~~act
patch_file
packages/stitcher-cli/src/stitcher/cli/commands/basics.py
~~~~~
~~~~~python.old
def generate_command():
    app_instance = make_app(parser_type="griffe")
    app_instance.run_from_config()


def init_command():
    app_instance = make_app(parser_type="cst")
    app_instance.run_init()


def strip_command():
    if not typer.confirm(bus.render_to_string(L.strip.run.confirm)):
        bus.warning(L.strip.run.aborted)
        raise typer.Abort()

    app_instance = make_app(parser_type="cst")
    app_instance.run_strip()


def inject_command():
    if not typer.confirm(bus.render_to_string(L.inject.run.confirm)):
        bus.warning(L.inject.run.aborted)
        raise typer.Abort()

    app_instance = make_app(parser_type="cst")
    app_instance.run_inject()
~~~~~
~~~~~python.new
def generate_command():
    app_instance = make_app()
    app_instance.run_from_config()


def init_command():
    app_instance = make_app()
    app_instance.run_init()


def strip_command():
    if not typer.confirm(bus.render_to_string(L.strip.run.confirm)):
        bus.warning(L.strip.run.aborted)
        raise typer.Abort()

    app_instance = make_app()
    app_instance.run_strip()


def inject_command():
    if not typer.confirm(bus.render_to_string(L.inject.run.confirm)):
        bus.warning(L.inject.run.aborted)
        raise typer.Abort()

    app_instance = make_app()
    app_instance.run_inject()
~~~~~
~~~~~act
patch_file
packages/stitcher-cli/src/stitcher/cli/commands/check.py
~~~~~
~~~~~python.old
    app_instance = make_app(handler, parser_type="griffe")
    success = app_instance.run_check(force_relink=force_relink, reconcile=reconcile)
~~~~~
~~~~~python.new
    app_instance = make_app(handler)
    success = app_instance.run_check(force_relink=force_relink, reconcile=reconcile)
~~~~~
~~~~~act
patch_file
packages/stitcher-cli/src/stitcher/cli/commands/pump.py
~~~~~
~~~~~python.old
    app_instance = make_app(handler, parser_type="cst")

    # 1. Run Pump
~~~~~
~~~~~python.new
    app_instance = make_app(handler)

    # 1. Run Pump
~~~~~

### 下一步建议
1.  **执行计划**: 请执行此计划以应用所有修复。
2.  **强制重新基线化**: 由于我们更改了核心签名逻辑，旧的签名文件已完全失效。请运行 `stitcher init` 来清除旧签名并基于 Griffe 生成全新的、正确的基线。
3.  **验证**:
    *   运行 `stitcher pump`，确认交互式会话中不再有“跳过”选项。
    *   对冲突做出决策后，运行 `stitcher check`，确认系统状态一致，没有伪“签名漂移”错误。
4.  **规划未来**: 将“实现精确到函数的 `strip` 命令”作为一个新任务进行规划，这将允许我们安全地重新启用“跳过”选项。

