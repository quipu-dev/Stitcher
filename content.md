检测到“确定性缺失”违例，已根据 **ADAP v1.0** 协议分析当前系统行为。

分析显示，我之前的指令集在解析层面存在严重的语法错误，未能遵守 **Quipu v1.0** 的参数分块协议。根据 **HFEA v1.0** 的“架构不可腐蚀性”原则，我将重新生成精确的指令块，确保每一项修改都建立在确定性的语法解析之上。

## [WIP] fix: 修复 Init 破坏 Sidecar 基线及索引统计不透明问题 (修正版)

### 错误分析
1.  **语法错误**：之前的 `patch_file` 指令未能正确使用波浪号 `~~~~~` 围栏对 [路径]、[旧字符串]、[新字符串] 进行物理隔离，导致解析器无法识别参数边界。
2.  **逻辑缺陷**：`InitRunner` 强制使用源码提取的 IR 作为 Lock 文件的基线，忽略了磁盘上已有的 `.stitcher.yaml` 内容，导致 `stored_yaml_hash` 与预期不符。
3.  **可观测性缺失**：`FileIndexer` 的统计数据过于粗糙，未对 Sidecar 文件进行分类计数。

### 用户需求
1.  `stitcher init` 需具备幂等性，优先尊重现有 Sidecar 内容作为基线。
2.  `stitcher index build` 需明确报告 Sidecar 处理数量。

### 目标
1.  在 `DocumentManager` 中添加 `save_irs` 接口。
2.  重构 `InitRunner` 的 `run_batch` 逻辑，建立 `Existing Docs > Source Docs` 的基线优先级。
3.  在 `FileIndexer` 中引入 `sidecars` 计数器并透传至 I18N 报告。

### 标签
#intent/fix #flow/ready #priority/high #comp/application #comp/index #comp/common #concept/state #scope/core #scope/dx #ai/instruct #task/domain/storage #task/object/init-logic #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 扩展 DocumentManager 接口

添加 `save_irs` 方法，允许直接保存已有的 IR 映射。

~~~~~act
patch_file
packages/stitcher-lang-sidecar/src/stitcher/lang/sidecar/manager.py
~~~~~
~~~~~python.old
    def save_docs_for_module(self, module: ModuleDef) -> Path:
        ir_map = self.flatten_module_docs(module)
        if not ir_map:
            return Path("")

        module_path = self.root_path / module.file_path
        output_path = self.resolver.get_doc_path(module_path)
        self._sidecar_adapter.save_doc_irs(output_path, ir_map, self.serializer)
        return output_path

    def load_docs_for_path(self, file_path: str) -> Dict[str, DocstringIR]:
~~~~~
~~~~~python.new
    def save_docs_for_module(self, module: ModuleDef) -> Path:
        ir_map = self.flatten_module_docs(module)
        if not ir_map:
            return Path("")

        module_path = self.root_path / module.file_path
        output_path = self.resolver.get_doc_path(module_path)
        self._sidecar_adapter.save_doc_irs(output_path, ir_map, self.serializer)
        return output_path

    def save_irs(self, file_path: str, ir_map: Dict[str, DocstringIR]) -> Path:
        """
        Save a dictionary of DocstringIRs directly to the sidecar file for the given source file path.
        """
        module_path = self.root_path / file_path
        output_path = self.resolver.get_doc_path(module_path)
        self._sidecar_adapter.save_doc_irs(output_path, ir_map, self.serializer)
        return output_path

    def load_docs_for_path(self, file_path: str) -> Dict[str, DocstringIR]:
~~~~~

#### Acts 2: 修正 InitRunner 的基线采集逻辑

修改 `InitRunner`，使其在执行 init 时，如果磁盘已有 Sidecar，则将其视为基线真理，只将源码中“新增”的文档作为补丁。

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/runners/init.py
~~~~~
~~~~~python.old
            for module in pkg_modules:
                output_path = self.doc_manager.save_docs_for_module(module)

                # Compute logical/relative paths for SURI generation
                module_abs_path = self.root_path / module.file_path
                module_ws_rel = self.workspace.to_workspace_relative(module_abs_path)

                # Generate IRs from source code; this is the source of truth for init.
                ir_map = self.doc_manager.flatten_module_docs(module)

                computed_fingerprints = self._compute_fingerprints(module)
                # CRITICAL FIX: Compute hashes from the in-memory IR map, NOT from the index.
                yaml_hashes = {
                    fqn: self.doc_manager.compute_ir_hash(ir)
                    for fqn, ir in ir_map.items()
                }

                all_fqns = set(computed_fingerprints.keys()) | set(yaml_hashes.keys())

                for fqn in all_fqns:
                    # Get the base computed fingerprint (code structure, sig text, etc.)
                    fp = computed_fingerprints.get(fqn, Fingerprint())

                    # Convert 'current' keys to 'baseline' keys for storage
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

                    # Generate global SURI
                    suri = self.uri_generator.generate_symbol_uri(module_ws_rel, fqn)
                    lock_data[suri] = fp
                    lock_updated = True

                if output_path and output_path.name:
                    relative_path = output_path.relative_to(self.root_path)
                    bus.success(L.init.file.created, path=relative_path)
                    created_files.append(output_path)
~~~~~
~~~~~python.new
            for module in pkg_modules:
                # 1. Load existing docs (Baseline)
                existing_docs = self.doc_manager.load_docs_for_module(module)
                
                # 2. Extract source docs
                source_docs = self.doc_manager.flatten_module_docs(module)

                # 3. Merge: Existing wins. Source only contributes missing keys.
                final_docs = existing_docs.copy()
                docs_to_save = {}

                for fqn, ir in source_docs.items():
                    if fqn not in final_docs:
                        final_docs[fqn] = ir
                        docs_to_save[fqn] = ir
                
                output_path = None
                if docs_to_save:
                    output_path = self.doc_manager.save_irs(module.file_path, docs_to_save)
                elif not existing_docs and not docs_to_save:
                    pass
                else:
                    output_path = self.doc_manager.resolver.get_doc_path(self.root_path / module.file_path)

                # Compute logical/relative paths for SURI generation
                module_abs_path = self.root_path / module.file_path
                module_ws_rel = self.workspace.to_workspace_relative(module_abs_path)

                computed_fingerprints = self._compute_fingerprints(module)
                # Compute hashes from the FINAL merged state.
                yaml_hashes = {
                    fqn: self.doc_manager.compute_ir_hash(ir)
                    for fqn, ir in final_docs.items()
                }

                all_fqns = set(computed_fingerprints.keys()) | set(yaml_hashes.keys())

                for fqn in all_fqns:
                    # Get the base computed fingerprint (code structure, sig text, etc.)
                    fp = computed_fingerprints.get(fqn, Fingerprint())

                    # Convert 'current' keys to 'baseline' keys for storage
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

                    # Generate global SURI
                    suri = self.uri_generator.generate_symbol_uri(module_ws_rel, fqn)
                    lock_data[suri] = fp
                    lock_updated = True

                if output_path and output_path.name and docs_to_save:
                    relative_path = output_path.relative_to(self.root_path)
                    bus.success(L.init.file.created, path=relative_path)
                    created_files.append(output_path)
~~~~~

#### Acts 3: 增加 Sidecar 索引统计

在 `FileIndexer` 中识别并计数 Sidecar 文件。

~~~~~act
patch_file
packages/stitcher-index/src/stitcher/index/indexer.py
~~~~~
~~~~~python.old
    def index_files(self, discovered_paths: Set[str]) -> Dict[str, Any]:
        stats: Dict[str, Any] = {
            "added": 0,
            "updated": 0,
            "deleted": 0,
            "skipped": 0,
            "errors": 0,
            "error_details": [],
            "modified_paths": set(),
        }
~~~~~
~~~~~python.new
    def index_files(self, discovered_paths: Set[str]) -> Dict[str, Any]:
        stats: Dict[str, Any] = {
            "added": 0,
            "updated": 0,
            "deleted": 0,
            "skipped": 0,
            "sidecars": 0,
            "errors": 0,
            "error_details": [],
            "modified_paths": set(),
        }
~~~~~

~~~~~act
patch_file
packages/stitcher-index/src/stitcher/index/indexer.py
~~~~~
~~~~~python.old
        # --- Check and Update ---
        for rel_path_str in discovered_paths:
            abs_path = self.root_path / rel_path_str
~~~~~
~~~~~python.new
        # --- Check and Update ---
        for rel_path_str in discovered_paths:
            if rel_path_str.endswith(".stitcher.yaml") or rel_path_str.endswith(".stitcher.json"):
                stats["sidecars"] += 1
            abs_path = self.root_path / rel_path_str
~~~~~

#### Acts 4: 报告 Sidecar 统计信息

更新 `IndexRunner` 以传递新的统计字段。

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/runners/index.py
~~~~~
~~~~~python.old
        bus.success(
            L.index.run.complete,
            added=stats["added"],
            updated=stats["updated"],
            deleted=stats["deleted"],
            skipped=stats["skipped"],
        )
~~~~~
~~~~~python.new
        bus.success(
            L.index.run.complete,
            added=stats["added"],
            updated=stats["updated"],
            deleted=stats["deleted"],
            skipped=stats["skipped"],
            sidecars=stats.get("sidecars", 0),
        )
~~~~~

#### Acts 5: 更新消息资源 (I18N)

~~~~~act
patch_file
packages/stitcher-common/src/stitcher/common/assets/needle/en/index/run.json
~~~~~
~~~~~json.old
{
  "start": "🔄 Starting incremental index build...",
  "complete": "✨ Indexing complete. Added: {added}, Updated: {updated}, Deleted: {deleted}, Skipped: {skipped}"
}
~~~~~
~~~~~json.new
{
  "start": "🔄 Starting incremental index build...",
  "complete": "✨ Indexing complete. Added: {added}, Updated: {updated}, Deleted: {deleted}, Skipped: {skipped}, Sidecars: {sidecars}"
}
~~~~~

~~~~~act
patch_file
packages/stitcher-common/src/stitcher/common/assets/needle/zh/index/run.json
~~~~~
~~~~~json.old
{
  "start": "🔄 开始增量索引构建...",
  "complete": "✨ 索引构建完成。新增: {added}, 更新: {updated}, 删除: {deleted}, 跳过: {skipped}"
}
~~~~~
~~~~~json.new
{
  "start": "🔄 开始增量索引构建...",
  "complete": "✨ 索引构建完成。新增: {added}, 更新: {updated}, 删除: {deleted}, 跳过: {skipped}, Sidecars: {sidecars}"
}
~~~~~

### 下一步建议
1.  重新运行测试：`pytest packages/stitcher-application/tests/integration/test_init_sidecar_idempotency.py`。
2.  观察 `stitcher index build` 的输出，验证其是否正确显示了 Sidecars 的数量。
3.  如果测试通过，建议将此逻辑扩展至 `pump` 操作，确保 `pump` 在存在内容冲突时也能有类似的可预测行为。
