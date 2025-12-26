好的，这是一个非常有洞察力的需求。它处理了一个在混合（人类+AI）开发环境中非常现实的场景：AI 可能会无意中用低质量的文档“污染”源代码，而我们不希望这些内容覆盖掉我们精心维护的 YAML 文档。

这个新功能引入了一种新的合并策略：“YAML 优先”。我建议通过一个新的标志 `--reconcile` 来实现它，它与 `--force`（代码优先）互斥。

我将为 `hydrate` 命令添加一个 `--reconcile` 标志。启用后，命令在遇到代码和 YAML 之间的文档冲突时，将静默地以 YAML 中的版本为准，只合并那些在 YAML 中完全不存在的新文档。

## [WIP] feat: Add --reconcile flag to hydrate for YAML-first merging

### 用户需求
1.  为 `hydrate` 命令增加一种新的合并模式。
2.  在该模式下，如果代码和 YAML 中都存在文档，**以 YAML 中的为准**，忽略代码中的版本。
3.  在该模式下，如果代码中有文档而 YAML 中没有，则正常将代码文档合并进 YAML。
4.  这个功能主要用于防止 AI 辅助编码时产生的低质量文档覆盖高质量的权威文档。

### 评论
这是一个关键的功能增强，它使 `hydrate` 命令从一个简单的“抽水”工具演变为一个更智能的“同步”工具，提供了三种明确的冲突解决策略：
- **默认**: 发现冲突时报错，要求用户介入。
- **`--force`**: 代码优先，强制用代码中的文档覆盖 YAML。
- **`--reconcile`**: YAML 优先，忽略代码中的冲突文档。

这为不同的开发工作流（纯手动、半自动、AI 辅助）提供了极大的灵活性。

### 目标
1.  在 `stitcher-cli` 中为 `hydrate` 命令添加 `--reconcile` 标志，并确保它与 `--force` 互斥。
2.  在 `DocumentManager` 的 `hydrate_module` 方法中实现 "YAML-first" 的合并逻辑。
3.  添加新的消息 ID，用于在 `reconcile` 模式下告知用户有多少冲突被静默忽略。
4.  编写一个新的集成测试来验证 `--reconcile` 模式的行为。

### 基本原理
我们将通过在 `hydrate_module` 的核心循环中增加一个条件分支来实现。当 `--reconcile` 被激活时，遇到内容不一致的键，逻辑将简单地 `continue`，既不报错也不更新。这将优雅地实现“忽略代码冲突”的语义。

### 标签
#intent/build #flow/ready #priority/medium #comp/cli #comp/runtime #concept/sync #scope/ux #ai/instruct #task/domain/cli #task/object/command-hydrate #task/action/implementation #task/state/continue

---

### Script

#### Acts 1: 添加新的消息资产

我们需要一条新的消息来告知用户，在 `reconcile` 模式下有多少冲突被忽略了，以增加操作的透明度。

~~~~~act
write_file
packages/stitcher-common/src/stitcher/common/assets/needle/en/hydrate/main.json
~~~~~
~~~~~json
{
    "hydrate.run.start": "💧 Starting hydration process...",
    "hydrate.file.success": "💧 Hydrated {count} new docstrings from: {path}",
    "hydrate.run.complete": "✨ Hydration complete. {count} files updated.",
    "hydrate.run.no_changes": "🤔 No new docstrings found in source code to hydrate.",
    "hydrate.error.conflict": "❌ Conflict in {path}: Docstring for '{key}' exists in both source code and YAML but differs. Use --force to overwrite YAML.",
    "hydrate.run.conflict": "🚫 Hydration aborted due to conflicts in {count} files.",
    "hydrate.info.reconciled": "ℹ️  Ignored {count} conflicts in {path} due to --reconcile mode."
}
~~~~~

#### Acts 2: 更新核心服务 `DocumentManager`

这是实现新合并策略的核心。我们将修改 `hydrate_module` 的逻辑。

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/services/doc_manager.py
~~~~~
~~~~~python.old
    def hydrate_module(
        self, module: ModuleDef, force: bool = False
    ) -> Dict[str, Any]:
        """
        Merges docstrings from Code into YAML.
        Returns a dict with 'success': bool, 'updated_keys': list, 'conflicts': list
        """
        source_docs = self.flatten_module_docs(module)
        if not source_docs:
            return {"success": True, "updated_keys": [], "conflicts": []}

        yaml_docs = self.load_docs_for_module(module)
        
        updated_keys = []
        conflicts = []
        
        # We will build a new dict to save, starting with existing YAML docs
        new_yaml_docs = yaml_docs.copy()
        
        for key, source_content in source_docs.items():
            if key not in yaml_docs:
                # New docstring, safe to add
                new_yaml_docs[key] = source_content
                updated_keys.append(key)
            elif yaml_docs[key] != source_content:
                # Conflict
                if force:
                    new_yaml_docs[key] = source_content
                    updated_keys.append(key)
                else:
                    conflicts.append(key)
            # Else: Content is identical, no action needed
            
        if conflicts:
            return {"success": False, "updated_keys": [], "conflicts": conflicts}
            
        if updated_keys:
            # Determine output path (same logic as save_docs_for_module)
            module_path = self.root_path / module.file_path
            output_path = module_path.with_suffix(".stitcher.yaml")
            self.adapter.save(output_path, new_yaml_docs)
            
        return {"success": True, "updated_keys": updated_keys, "conflicts": []}
~~~~~
~~~~~python.new
    def hydrate_module(
        self, module: ModuleDef, force: bool = False, reconcile: bool = False
    ) -> Dict[str, Any]:
        """
        Merges docstrings from Code into YAML.
        Returns a dict with 'success': bool, 'updated_keys': list, 'conflicts': list, 'reconciled_keys': list
        """
        source_docs = self.flatten_module_docs(module)
        if not source_docs:
            return {
                "success": True,
                "updated_keys": [],
                "conflicts": [],
                "reconciled_keys": [],
            }

        yaml_docs = self.load_docs_for_module(module)

        updated_keys = []
        conflicts = []
        reconciled_keys = []

        # We will build a new dict to save, starting with existing YAML docs
        new_yaml_docs = yaml_docs.copy()

        for key, source_content in source_docs.items():
            if key not in yaml_docs:
                # New docstring, safe to add
                new_yaml_docs[key] = source_content
                updated_keys.append(key)
            elif yaml_docs[key] != source_content:
                # Conflict exists
                if reconcile:
                    # YAML-first: Ignore the source content and do nothing.
                    reconciled_keys.append(key)
                    continue
                elif force:
                    # Code-first: Overwrite YAML with source content.
                    new_yaml_docs[key] = source_content
                    updated_keys.append(key)
                else:
                    # Default: Report conflict and fail.
                    conflicts.append(key)
            # Else: Content is identical, no action needed

        if conflicts:
            return {
                "success": False,
                "updated_keys": [],
                "conflicts": conflicts,
                "reconciled_keys": [],
            }

        if updated_keys:
            # Determine output path (same logic as save_docs_for_module)
            module_path = self.root_path / module.file_path
            output_path = module_path.with_suffix(".stitcher.yaml")
            self.adapter.save(output_path, new_yaml_docs)

        return {
            "success": True,
            "updated_keys": updated_keys,
            "conflicts": [],
            "reconciled_keys": reconciled_keys,
        }
~~~~~

#### Acts 3: 更新应用层 `StitcherApp`

我们需要将新的 `reconcile` 参数传递下去，并处理新的 `reconciled_keys` 返回值。

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/core.py
~~~~~
~~~~~python.old
    def run_hydrate(self, strip: bool = False, force: bool = False) -> bool:
        """
        Extracts docstrings from source code and merges them into YAML files.
        If 'strip' is True, removes docstrings from source files after successful hydration.
        """
        bus.info(L.hydrate.run.start)
        config = load_config_from_path(self.root_path)
        modules = self._scan_files(self._get_files_from_config(config))
        
        if not modules:
            bus.warning(L.warning.no_files_or_plugins_found)
            return True

        updated_files_count = 0
        conflict_files_count = 0
        
        # Phase 1: Hydrate (Update YAMLs)
        # We process all files. If any file has conflicts, we fail the whole operation
        # (or at least report it). But 'strip' should definitely check per-file success.
        
        files_to_strip = []

        for module in modules:
            result = self.doc_manager.hydrate_module(module, force=force)
            
            if not result["success"]:
                conflict_files_count += 1
                for conflict_key in result["conflicts"]:
                    bus.error(
                        L.hydrate.error.conflict, 
                        path=module.file_path, 
                        key=conflict_key
                    )
                continue
            
            # If successful (or no changes needed), we consider this file "clean"/synced.
            if result["updated_keys"]:
                updated_files_count += 1
                bus.success(
                    L.hydrate.file.success, 
                    path=module.file_path, 
                    count=len(result["updated_keys"])
                )
            
            # If successful, this file is a candidate for stripping
            files_to_strip.append(module)

        if conflict_files_count > 0:
            bus.error(L.hydrate.run.conflict, count=conflict_files_count)
            return False
            
        if updated_files_count == 0:
            bus.info(L.hydrate.run.no_changes)
        else:
            bus.success(L.hydrate.run.complete, count=updated_files_count)
~~~~~
~~~~~python.new
    def run_hydrate(
        self, strip: bool = False, force: bool = False, reconcile: bool = False
    ) -> bool:
        """
        Extracts docstrings from source code and merges them into YAML files.
        - strip: Removes docstrings from source after successful hydration.
        - force: Code-first conflict resolution.
        - reconcile: YAML-first conflict resolution.
        """
        bus.info(L.hydrate.run.start)
        config = load_config_from_path(self.root_path)
        modules = self._scan_files(self._get_files_from_config(config))

        if not modules:
            bus.warning(L.warning.no_files_or_plugins_found)
            return True

        updated_files_count = 0
        conflict_files_count = 0

        # Phase 1: Hydrate (Update YAMLs)
        files_to_strip = []

        for module in modules:
            result = self.doc_manager.hydrate_module(
                module, force=force, reconcile=reconcile
            )

            if not result["success"]:
                conflict_files_count += 1
                for conflict_key in result["conflicts"]:
                    bus.error(
                        L.hydrate.error.conflict, path=module.file_path, key=conflict_key
                    )
                continue

            if result["reconciled_keys"]:
                bus.info(
                    L.hydrate.info.reconciled,
                    path=module.file_path,
                    count=len(result["reconciled_keys"]),
                )

            if result["updated_keys"]:
                updated_files_count += 1
                bus.success(
                    L.hydrate.file.success,
                    path=module.file_path,
                    count=len(result["updated_keys"]),
                )

            # If successful, this file is a candidate for stripping
            files_to_strip.append(module)

        if conflict_files_count > 0:
            bus.error(L.hydrate.run.conflict, count=conflict_files_count)
            return False

        if updated_files_count == 0:
            bus.info(L.hydrate.run.no_changes)
        else:
            bus.success(L.hydrate.run.complete, count=updated_files_count)
~~~~~

#### Acts 4: 更新 CLI 层

添加 `--reconcile` 标志并确保与 `--force` 互斥。

~~~~~act
patch_file
packages/stitcher-cli/src/stitcher/cli/main.py
~~~~~
~~~~~python.old
@app.command()
def hydrate(
    strip: bool = typer.Option(
        False, "--strip", help="Remove docstrings from source code after hydration."
    ),
    force: bool = typer.Option(
        False, "--force", help="Overwrite YAML content if it differs from source code."
    ),
):
    """
    Extract new docstrings from source code and merge them into .stitcher.yaml.
    """
    project_root = Path.cwd()
    app_instance = StitcherApp(root_path=project_root)
    success = app_instance.run_hydrate(strip=strip, force=force)
    if not success:
        raise typer.Exit(code=1)
~~~~~
~~~~~python.new
@app.command()
def hydrate(
    strip: bool = typer.Option(
        False, "--strip", help="Remove docstrings from source code after hydration."
    ),
    force: bool = typer.Option(
        False,
        "--force",
        help="Code-first: Overwrite YAML content if it differs from source code.",
    ),
    reconcile: bool = typer.Option(
        False,
        "--reconcile",
        help="YAML-first: Ignore source docstrings if they conflict with existing YAML.",
    ),
):
    """
    Extract new docstrings from source code and merge them into .stitcher.yaml.
    """
    if force and reconcile:
        bus.error("Cannot use --force and --reconcile simultaneously.")
        raise typer.Exit(code=1)

    project_root = Path.cwd()
    app_instance = StitcherApp(root_path=project_root)
    success = app_instance.run_hydrate(strip=strip, force=force, reconcile=reconcile)
    if not success:
        raise typer.Exit(code=1)
~~~~~

#### Acts 5: 添加集成测试

最后，为新的 `--reconcile` 模式添加一个专门的测试用例。

~~~~~act
patch_file
tests/integration/test_hydrate_command.py
~~~~~
~~~~~python.old
def test_hydrate_with_strip_removes_source_doc(tmp_path, monkeypatch):
    """Scenario 4: Strip Integration"""
    # Arrange
    factory = WorkspaceFactory(tmp_path)
    source_path = "src/main.py"
    project_root = (
        factory.with_config({"scan_paths": ["src"]})
        .with_source(source_path, 'def func():\n    """New doc."""\n    pass')
        .build()
    )

    app = StitcherApp(root_path=project_root)
    spy_bus = SpyBus()

    # Act
    with spy_bus.patch(monkeypatch, "stitcher.app.core.bus"):
        success = app.run_hydrate(strip=True)

    # Assert
    assert success is True
    spy_bus.assert_id_called(L.hydrate.file.success)
    spy_bus.assert_id_called(L.strip.file.success)
    spy_bus.assert_id_called(L.strip.run.complete)

    # Verify source was stripped
    final_code = (project_root / source_path).read_text()
    assert '"""' not in final_code
~~~~~
~~~~~python.new
def test_hydrate_with_strip_removes_source_doc(tmp_path, monkeypatch):
    """Scenario 4: Strip Integration"""
    # Arrange
    factory = WorkspaceFactory(tmp_path)
    source_path = "src/main.py"
    project_root = (
        factory.with_config({"scan_paths": ["src"]})
        .with_source(source_path, 'def func():\n    """New doc."""\n    pass')
        .build()
    )

    app = StitcherApp(root_path=project_root)
    spy_bus = SpyBus()

    # Act
    with spy_bus.patch(monkeypatch, "stitcher.app.core.bus"):
        success = app.run_hydrate(strip=True)

    # Assert
    assert success is True
    spy_bus.assert_id_called(L.hydrate.file.success)
    spy_bus.assert_id_called(L.strip.file.success)
    spy_bus.assert_id_called(L.strip.run.complete)

    # Verify source was stripped
    final_code = (project_root / source_path).read_text()
    assert '"""' not in final_code


def test_hydrate_reconcile_ignores_source_conflict(tmp_path, monkeypatch):
    """Scenario 5: Reconcile (YAML-first) Mode"""
    # Arrange (same as conflict test)
    factory = WorkspaceFactory(tmp_path)
    project_root = (
        factory.with_config({"scan_paths": ["src"]})
        .with_source("src/main.py", 'def func():\n    """Code doc."""\n    pass')
        .with_docs("src/main.stitcher.yaml", {"func": "YAML doc"})
        .build()
    )

    app = StitcherApp(root_path=project_root)
    spy_bus = SpyBus()

    # Act
    with spy_bus.patch(monkeypatch, "stitcher.app.core.bus"):
        success = app.run_hydrate(reconcile=True)

    # Assert
    assert success is True
    spy_bus.assert_id_called(L.hydrate.info.reconciled, level="info")
    
    # Verify no errors were raised
    error_msgs = [m for m in spy_bus.get_messages() if m["level"] == "error"]
    assert not error_msgs

    # Verify YAML was NOT changed
    doc_path = project_root / "src/main.stitcher.yaml"
    with doc_path.open("r") as f:
        data = yaml.safe_load(f)
        assert data["func"] == "YAML doc"
~~~~~

### 下一步建议
我们已经成功地实现了 `reconcile` 功能并为其添加了测试。`hydrate` 命令现在是一个功能完备的同步工具。这是一个逻辑上的完成点，我们可以将这一系列关于 `hydrate` 的变更作为一个完整的特性提交。
