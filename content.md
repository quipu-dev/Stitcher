好的，测试失败为我们指明了前进的道路。现在，我们将执行一个全面的修复计划，以解决这两个已验证的 bug，并让测试转绿。

### Script

#### Acts 1: 重构 `run_pump` 以实现原子化和状态安全更新

这是最核心的修复。我们将彻底替换 `run_pump` 中有问题的签名更新逻辑，引入新的、健壮的流程，该流程能够根据 `hydrate_module` 的结果（成功或失败）来保证文件级的原子性，并根据用户的具体决策（代码优先或 YAML 优先）来精确更新签名。

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/core.py
~~~~~
~~~~~python.old
            if not result["success"]:
                # If conflicts persist (e.g. user chose SKIP), verify failure
                total_conflicts_remaining += len(result["conflicts"])
                for conflict_key in result["conflicts"]:
                    bus.error(
                        L.pump.error.conflict,
                        path=module.file_path,
                        key=conflict_key,
                    )
                continue

            if result["reconciled_keys"]:
                bus.info(
                    L.pump.info.reconciled,
                    path=module.file_path,
                    count=len(result["reconciled_keys"]),
                )
            if result["updated_keys"]:
                total_updated += 1
                bus.success(
                    L.pump.file.success,
                    path=module.file_path,
                    count=len(result["updated_keys"]),
                )

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
~~~~~
~~~~~python.new
            if not result["success"]:
                # If conflicts persist, it's a failure for this file.
                # Do not update anything for this module. This ensures file-level atomicity.
                total_conflicts_remaining += len(result["conflicts"])
                for conflict_key in result["conflicts"]:
                    bus.error(
                        L.pump.error.conflict,
                        path=module.file_path,
                        key=conflict_key,
                    )
                continue

            # --- ATOMIC SIGNATURE UPDATE ---
            # This block only runs if hydrate_module succeeded for the entire file.

            if result["reconciled_keys"]:
                bus.info(
                    L.pump.info.reconciled,
                    path=module.file_path,
                    count=len(result["reconciled_keys"]),
                )
            if result["updated_keys"]:
                total_updated += 1
                bus.success(
                    L.pump.file.success,
                    path=module.file_path,
                    count=len(result["updated_keys"]),
                )

            # Only update signatures if something was actually hydrated or reconciled.
            if result["updated_keys"] or result["reconciled_keys"]:
                stored_hashes = self.sig_manager.load_composite_hashes(module)
                new_hashes = copy.deepcopy(stored_hashes)
                computed_fingerprints = self.sig_manager.compute_fingerprints(module)
                current_yaml_map = self.doc_manager.compute_yaml_content_hashes(
                    module
                )

                # For keys where code doc was authoritative (updated/force-hydrated)
                for fqn in result["updated_keys"]:
                    fp = computed_fingerprints.get(fqn, Fingerprint())
                    # Atomically convert current to baseline for both code and doc hashes
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
                    # Start with the existing hash to preserve yaml_content_hash
                    fp = new_hashes.get(fqn, Fingerprint())
                    current_fp = computed_fingerprints.get(fqn, Fingerprint())
                    # Only update the code baseline, leaving yaml baseline intact
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
~~~~~

#### Acts 2: 禁用 `pump` 的“跳过”选项并统一 CLI 解析器

我们将一次性应用所有对 CLI 包的修改：禁用 `pump` 交互中的“跳过”选项，并将所有命令的解析器统一为 Griffe。

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
1.  **执行计划**: 执行此计划以应用所有修复。
2.  **运行测试 (预期成功)**: 再次运行 `pytest packages/stitcher-application/tests/integration/test_pump_state_integrity.py`。现在，两个测试都应该通过（GREEN）。
3.  **提交变更**: 在测试通过后，你可以将这些修复和新的测试文件一起提交，完成这次重要的重构。
