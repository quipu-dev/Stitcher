好的，我们将首先执行核心的协议定义变更。这是所有后续重构的基础。

## [WIP] refactor: Clarify DocstringSerializerProtocol semantics

### 用户需求

The user requires a refactoring of `DocstringSerializerProtocol` to clearly separate the concerns of high-fidelity, format-specific serialization (for `.yaml` files) from data-transfer-object serialization (for database storage and hashing).

### 评论

This is a high-impact architectural refinement that aligns with the High-Fidelity Engineering Axioms (HFEA). By renaming the methods in the protocol, we establish a strong, unambiguous contract for all implementing classes. This eliminates semantic ambiguity and makes the data flow in dependent components (`SidecarAdapter`, `IndexStore`) cleaner and more robust. It replaces reliance on implementation details with a clear, enforceable design.

### 目标

1.  Modify `stitcher.spec.protocols.DocstringSerializerProtocol` to replace the ambiguous `to_yaml`/`from_yaml` methods with two pairs of semantically precise methods:
    *   `to_serializable_dict` / `from_serializable_dict` for JSON-safe data transfer.
    *   `to_yaml_object` / `from_yaml_object` for high-fidelity YAML representation.
2.  Update all references to this protocol throughout the codebase to reflect the new method names.

### 基本原理

This is a cross-cutting change that affects the protocol definition and all its consumers. The plan will proceed with the following atomic `patch_file` operations:
1.  **Update the Spec**: The `DocstringSerializerProtocol` in `packages/stitcher-spec/src/stitcher/spec/protocols.py` will be modified first to establish the new contract.
2.  **Update Consumers**: All files that import and use `DocstringSerializerProtocol` will be updated to call the new, more specific methods. This includes `DocumentManager` in `stitcher-lang-sidecar` and the serializer implementations in `stitcher-lang-python`.

### 标签

#intent/refine #flow/ready #priority/high #comp/spec #comp/sidecar #comp/python #scope/api #ai/brainstorm #task/domain/storage #task/object/sidecar-index #task/action/implementation #task/state/continue #task/status/active

---

### Script

#### Acts 1: Refactor DocstringSerializerProtocol in stitcher-spec

We will redefine the protocol to have clear, distinct methods for DTO conversion and YAML object representation.

~~~~~act
patch_file
packages/stitcher-spec/src/stitcher/spec/protocols.py
~~~~~
~~~~~python.old
class DocstringSerializerProtocol(Protocol):
    def to_yaml(self, ir: DocstringIR) -> Union[str, Dict[str, Any]]: ...

    def from_yaml(self, data: Union[str, Dict[str, Any]]) -> DocstringIR: ...
~~~~~
~~~~~python.new
class DocstringSerializerProtocol(Protocol):
    # For data transfer, hashing, and database storage (must be JSON-safe and deterministic)
    def to_serializable_dict(self, ir: DocstringIR) -> Dict[str, Any]: ...
    def from_serializable_dict(self, data: Dict[str, Any]) -> DocstringIR: ...

    # For high-fidelity writing to .yaml files (may contain format-specific objects)
    def to_yaml_object(self, ir: DocstringIR) -> Union[str, Dict[str, Any]]: ...
    def from_yaml_object(self, data: Union[str, Dict[str, Any]]) -> DocstringIR: ...
~~~~~

#### Acts 2: Update stitcher-lang-sidecar consumers

Now we update `DocumentManager` and `SidecarAdapter` to use the new protocol methods.

~~~~~act
patch_file
packages/stitcher-lang-sidecar/src/stitcher/lang/sidecar/adapter.py
~~~~~
~~~~~python.old
    def load_doc_irs(
        self, path: Path, serializer: DocstringSerializerProtocol
    ) -> Dict[str, DocstringIR]:
        if not path.exists():
            return {}

        try:
            with path.open("r", encoding="utf-8") as f:
                raw_data = self._yaml.load(f)
            if not isinstance(raw_data, dict):
                return {}

            return {fqn: serializer.from_yaml(val) for fqn, val in raw_data.items()}
        except Exception:
            return {}

    def save_doc_irs(
        self,
        path: Path,
        irs: Dict[str, DocstringIR],
        serializer: DocstringSerializerProtocol,
    ) -> None:
~~~~~
~~~~~python.new
    def load_doc_irs(
        self, path: Path, serializer: DocstringSerializerProtocol
    ) -> Dict[str, DocstringIR]:
        if not path.exists():
            return {}

        try:
            with path.open("r", encoding="utf-8") as f:
                raw_data = self._yaml.load(f)
            if not isinstance(raw_data, dict):
                return {}

            return {fqn: serializer.from_yaml_object(val) for fqn, val in raw_data.items()}
        except Exception:
            return {}

    def save_doc_irs(
        self,
        path: Path,
        irs: Dict[str, DocstringIR],
        serializer: DocstringSerializerProtocol,
    ) -> None:
~~~~~

~~~~~act
patch_file
packages/stitcher-lang-sidecar/src/stitcher/lang/sidecar/adapter.py
~~~~~
~~~~~python.old
            # Update the loaded data with new/modified IRs.
            # NO SORTING is applied to preserve original key order.
            # New keys will be appended by ruamel.yaml.
            for fqn, ir in irs.items():
                yaml_val = serializer.to_yaml(ir)
                if isinstance(yaml_val, str):
                    formatted_val = LiteralScalarString(yaml_val)
~~~~~
~~~~~python.new
            # Update the loaded data with new/modified IRs.
            # NO SORTING is applied to preserve original key order.
            # New keys will be appended by ruamel.yaml.
            for fqn, ir in irs.items():
                yaml_val = serializer.to_yaml_object(ir)
                if isinstance(yaml_val, str):
                    formatted_val = LiteralScalarString(yaml_val)
~~~~~

~~~~~act
patch_file
packages/stitcher-lang-sidecar/src/stitcher/lang/sidecar/adapter.py
~~~~~
~~~~~python.old
            # --- CREATE PATH ---
            # For new files, create a clean, sorted baseline for predictability.
            sorted_irs = dict(sorted(irs.items()))
            yaml_data = {fqn: serializer.to_yaml(ir) for fqn, ir in sorted_irs.items()}
            formatted_data = self._to_literal_strings(yaml_data)
            string_stream = io.StringIO()
~~~~~
~~~~~python.new
            # --- CREATE PATH ---
            # For new files, create a clean, sorted baseline for predictability.
            sorted_irs = dict(sorted(irs.items()))
            yaml_data = {fqn: serializer.to_yaml_object(ir) for fqn, ir in sorted_irs.items()}
            formatted_data = self._to_literal_strings(yaml_data)
            string_stream = io.StringIO()
~~~~~

~~~~~act
patch_file
packages/stitcher-lang-sidecar/src/stitcher/lang/sidecar/manager.py
~~~~~
~~~~~python.old
    def _serialize_ir(self, ir: DocstringIR) -> Union[str, Dict[str, Any]]:
        return self._sidecar_adapter.serialize_ir(ir, self.serializer)

    def _deserialize_ir(self, data: Union[str, Dict[str, Any]]) -> DocstringIR:
        return self.serializer.from_yaml(data)

    def serialize_ir(self, ir: DocstringIR) -> Union[str, Dict[str, Any]]:
        return self._serialize_ir(ir)
~~~~~
~~~~~python.new
    def _serialize_ir(self, ir: DocstringIR) -> Union[str, Dict[str, Any]]:
        return self._sidecar_adapter.serialize_ir(ir, self.serializer)

    def _deserialize_ir(self, data: Union[str, Dict[str, Any]]) -> DocstringIR:
        return self.serializer.from_yaml_object(data)

    def serialize_ir(self, ir: DocstringIR) -> Union[str, Dict[str, Any]]:
        return self._serialize_ir(ir)
~~~~~

### 下一步建议
The contract is now clear. The next logical step is to implement this new contract in the concrete serializer classes within `stitcher-lang-python`: `RawSerializer`, `GoogleSerializer`, and `NumpySerializer`. I will generate a plan for that if you agree.
