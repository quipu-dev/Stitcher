好的，我将执行“阶段三”中的协议净化任务。首要目标是移除 `DocumentManagerProtocol` 和 `SignatureManagerProtocol` 中暴露的实现细节（私有方法和属性），代之以更高层的语义接口，并同步更新实现层和调用方 (`PumpRunner`)。

## [WIP] refactor: 净化文档与签名管理协议以移除实现细节泄漏

### 用户需求
当前 `stitcher-spec` 中的协议定义（`DocumentManagerProtocol`, `SignatureManagerProtocol`）为了迎合 `PumpRunner` 的实现细节，暴露了带下划线的私有方法 (`_serialize_ir`, `_get_sig_path`) 和内部属性 (`adapter`)。这违反了接口抽象原则，导致上层逻辑与底层实现（如文件系统路径计算、YAML 序列化细节）强耦合。用户需要通过重构来净化这些协议。

### 评论
这是一个关键的架构治理步骤。通过将“如何计算 IR 的哈希”和“如何将数据转储为字符串”的逻辑封装在 Manager 内部，Runner 将不再需要知道 Manager 背后是否使用了 YAML 还是数据库，也不需要知道 adapter 的存在。这显著提升了系统的可测试性和未来替换存储后端的能力。

### 目标
1.  **重构 `DocumentManagerProtocol`**:
    *   移除 `_serialize_ir` 和 `adapter` 属性。
    *   新增 `compute_ir_hash(ir: DocstringIR) -> str` 方法，封装序列化和哈希计算。
    *   新增 `dump_data(data: Dict[str, Any]) -> str` 方法，封装数据的最终序列化（替代直接访问 adapter）。
2.  **重构 `SignatureManagerProtocol`**:
    *   将 `_get_sig_path` 重命名为 `get_signature_path` 并作为公共协议接口，允许 Runner 获取路径进行事务操作。
3.  **更新实现类**: 在 `stitcher-application` 的 `DocumentManager` 和 `SignatureManager` 中实现上述变更。
4.  **更新消费方**: 修改 `PumpRunner` 以使用新的纯净接口。

### 基本原理
**抽象倒置原则 (DIP)** 要求高层模块不依赖低层模块的实现细节。当前 Runner 知道太多关于“如何序列化”和“Adapter 是什么”的细节。通过引入 `compute_ir_hash` 和 `dump_data`，我们将这些“怎么做”的知识归还给了 Manager，Runner 只需表达“我要这个 IR 的哈希”或“我要把这些数据转成字符串”的意图。

### 标签
#intent/refine #flow/ready #priority/high #comp/interfaces #comp/runtime #scope/core #ai/instruct #task/domain/architecture #task/object/protocols #task/action/purify #task/state/begin

---

### Script

#### Acts 1: 净化协议定义

修改 `stitcher-spec` 中的协议。

~~~~~act
patch_file
packages/stitcher-spec/src/stitcher/spec/managers.py
~~~~~
~~~~~python.old
    def reformat_docs_for_module(self, module: ModuleDef) -> bool: ...

    # Helper method used by PumpRunner to serialize for hash computation
    def _serialize_ir(self, ir: DocstringIR) -> Union[str, Dict[str, Any]]: ...

    # Accessor for the underlying adapter, used for raw dumps in PumpRunner
    @property
    def adapter(self) -> Any: ...


class SignatureManagerProtocol(Protocol):
    def load_composite_hashes(self, file_path: str) -> Dict[str, Fingerprint]: ...

    def save_composite_hashes(
        self, file_path: str, hashes: Dict[str, Fingerprint]
    ) -> None: ...

    def reformat_hashes_for_file(self, file_path: str) -> bool: ...

    # Used by PumpRunner for centralized serialization
    def serialize_hashes(
        self, file_path: str, hashes: Dict[str, Fingerprint]
    ) -> str: ...

    # Internal helper used by PumpRunner to delete files
    def _get_sig_path(self, file_path: str) -> Path: ...
~~~~~
~~~~~python.new
    def reformat_docs_for_module(self, module: ModuleDef) -> bool: ...

    def serialize_ir(self, ir: DocstringIR) -> Union[str, Dict[str, Any]]: ...

    def compute_ir_hash(self, ir: DocstringIR) -> str: ...

    def dump_data(self, data: Dict[str, Any]) -> str: ...


class SignatureManagerProtocol(Protocol):
    def load_composite_hashes(self, file_path: str) -> Dict[str, Fingerprint]: ...

    def save_composite_hashes(
        self, file_path: str, hashes: Dict[str, Fingerprint]
    ) -> None: ...

    def reformat_hashes_for_file(self, file_path: str) -> bool: ...

    # Used by PumpRunner for centralized serialization
    def serialize_hashes(
        self, file_path: str, hashes: Dict[str, Fingerprint]
    ) -> str: ...

    def get_signature_path(self, file_path: str) -> Path: ...
~~~~~

#### Acts 2: 更新 DocumentManager 实现

公开 `serialize_ir` 并实现新方法。

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/services/doc_manager.py
~~~~~
~~~~~python.old
    def _deserialize_ir(self, data: Union[str, Dict[str, Any]]) -> DocstringIR:
        return self.serializer.from_yaml(data)

    def _serialize_ir(self, ir: DocstringIR) -> Union[str, Dict[str, Any]]:
        return self.serializer.to_yaml(ir)

    def _extract_from_function(
~~~~~
~~~~~python.new
    def _deserialize_ir(self, data: Union[str, Dict[str, Any]]) -> DocstringIR:
        return self.serializer.from_yaml(data)

    def _serialize_ir(self, ir: DocstringIR) -> Union[str, Dict[str, Any]]:
        return self.serializer.to_yaml(ir)

    def serialize_ir(self, ir: DocstringIR) -> Union[str, Dict[str, Any]]:
        return self._serialize_ir(ir)

    def compute_ir_hash(self, ir: DocstringIR) -> str:
        serialized = self._serialize_ir(ir)
        return self.compute_yaml_content_hash(serialized)

    def dump_data(self, data: Dict[str, Any]) -> str:
        return self.adapter.dump(data)

    def _extract_from_function(
~~~~~

#### Acts 3: 更新 SignatureManager 实现

暴露 `get_signature_path`。

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/services/signature_manager.py
~~~~~
~~~~~python.old
    def _get_sig_path(self, file_path: str) -> Path:
        return self.resolver.get_signature_path(file_path)

    def serialize_hashes(self, file_path: str, hashes: Dict[str, Fingerprint]) -> str:
~~~~~
~~~~~python.new
    def _get_sig_path(self, file_path: str) -> Path:
        return self.resolver.get_signature_path(file_path)

    def get_signature_path(self, file_path: str) -> Path:
        return self._get_sig_path(file_path)

    def serialize_hashes(self, file_path: str, hashes: Dict[str, Fingerprint]) -> str:
~~~~~

#### Acts 4: 更新 PumpRunner

使用新的 API，不再访问私有成员。

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/runners/pump.py
~~~~~
~~~~~python.old
                if plan.update_doc_fingerprint:
                    if fqn in source_docs:
                        ir_to_save = new_yaml_docs.get(fqn)
                        if ir_to_save:
                            serialized = self.doc_manager._serialize_ir(ir_to_save)
                            doc_hash = self.doc_manager.compute_yaml_content_hash(
                                serialized
                            )
                            fp["baseline_yaml_content_hash"] = doc_hash
                            fqn_was_updated = True

                if fqn_was_updated:
                    new_hashes[fqn] = fp

                if (
                    fqn in decisions
                    and decisions[fqn] == ResolutionAction.HYDRATE_KEEP_EXISTING
                ):
                    reconciled_keys_in_file.append(fqn)

                if plan.strip_source_docstring:
                    strip_jobs[module.file_path].append(fqn)

                if fqn in source_docs and not plan.strip_source_docstring:
                    file_has_redundancy = True

            signatures_need_save = new_hashes != stored_hashes

            if not file_has_errors:
                if file_had_updates:
                    final_data = {
                        k: self.doc_manager._serialize_ir(v)
                        for k, v in new_yaml_docs.items()
                    }
                    module_path = self.root_path / module.file_path
                    doc_path = module_path.with_suffix(".stitcher.yaml")
                    yaml_content = self.doc_manager.adapter.dump(final_data)
                    tm.add_write(
                        str(doc_path.relative_to(self.root_path)), yaml_content
                    )

                if signatures_need_save:
                    sig_path = self.sig_manager._get_sig_path(module.file_path)
                    rel_sig_path = str(sig_path.relative_to(self.root_path))
~~~~~
~~~~~python.new
                if plan.update_doc_fingerprint:
                    if fqn in source_docs:
                        ir_to_save = new_yaml_docs.get(fqn)
                        if ir_to_save:
                            doc_hash = self.doc_manager.compute_ir_hash(ir_to_save)
                            fp["baseline_yaml_content_hash"] = doc_hash
                            fqn_was_updated = True

                if fqn_was_updated:
                    new_hashes[fqn] = fp

                if (
                    fqn in decisions
                    and decisions[fqn] == ResolutionAction.HYDRATE_KEEP_EXISTING
                ):
                    reconciled_keys_in_file.append(fqn)

                if plan.strip_source_docstring:
                    strip_jobs[module.file_path].append(fqn)

                if fqn in source_docs and not plan.strip_source_docstring:
                    file_has_redundancy = True

            signatures_need_save = new_hashes != stored_hashes

            if not file_has_errors:
                if file_had_updates:
                    final_data = {
                        k: self.doc_manager.serialize_ir(v)
                        for k, v in new_yaml_docs.items()
                    }
                    module_path = self.root_path / module.file_path
                    doc_path = module_path.with_suffix(".stitcher.yaml")
                    yaml_content = self.doc_manager.dump_data(final_data)
                    tm.add_write(
                        str(doc_path.relative_to(self.root_path)), yaml_content
                    )

                if signatures_need_save:
                    sig_path = self.sig_manager.get_signature_path(module.file_path)
                    rel_sig_path = str(sig_path.relative_to(self.root_path))
~~~~~

### 下一步建议
完成此净化后，可以继续进行 `IndexStore` 协议的净化，或着手解决 Runner 中硬编码实例化子组件的问题。这将为完全的依赖注入和单元测试铺平道路。
