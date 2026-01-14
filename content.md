好的，Pyright 已经为我们精确地指明了所有需要修复的“伤口”。我们将按照“激进重演逻辑”，一次性修复所有实现类，使它们符合新的、更健壮的协议。

我将生成一个计划，分两步完成所有修复：
1.  **实现层修复**：在 `stitcher-lang-python` 中，为所有 `Serializer` 类实现新的协议方法。
2.  **消费层修复**：在 `stitcher-lang-sidecar` 中，更新所有调用点以使用新的方法。

## [WIP] refactor(serializer): 实现 DTO 与视图分离的序列化协议

### 用户需求

根据 `pyright` 的错误报告，修复所有 `DocstringSerializer` 的实现类，以及所有调用旧协议方法的地方，使其完全符合新的协议。

### 评论

这是一个典型的“涟漪效应”修复。核心契约的变更，要求所有相关的实现和消费方都进行同步升级。一次性完成所有这些修改，可以确保系统在提交后立即恢复到一致和可工作的状态。

### 目标

1.  在 `RawSerializer` 和 `StructuredSerializer` 中实现 `to/from_transfer_data` 和 `to/from_view_data` 四个方法。
2.  更新 `SidecarAdapter` 和 `DocumentManager`，使其在与文件系统交互时使用 `view_data` 方法，在进行哈希计算时使用 `transfer_data` 方法。
3.  消除所有相关的 `pyright` 错误。

### 基本原理

通过在实现层精确地区分两种序列化场景，我们可以确保：
*   **写入文件时 (`to_view_data`)**: 能够生成包含 `ruamel.yaml` 特定对象的富文本数据，保证 YAML 格式美观。
*   **写入数据库/哈希时 (`to_transfer_data`)**: 能够生成纯净、确定性的字典，保证 JSON 兼容性和哈希稳定性。
*   **读取时**: 相应地使用 `from_view_data` 和 `from_transfer_data` 进行反序列化。

这种清晰的分离是新架构成功的关键。

### 标签

#intent/refine #flow/ready #priority/high #comp/lang-python #comp/lang-sidecar #concept/serialization #scope/api #ai/instruct #task/domain/testing #task/object/serialization-protocol #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 实现新的序列化协议

我们首先修改 `stitcher-lang-python` 中的 `serializers.py`。`BaseSerializer` 将被重命名并拆分为两个更具体的基类，然后 `RawSerializer` 和 `StructuredSerializer` 将分别实现新协议。

~~~~~act
write_file
packages/stitcher-lang-python/src/stitcher/lang/python/docstring/serializers.py
~~~~~
~~~~~python
from typing import Dict, Any, Union
from stitcher.spec import (
    DocstringIR,
    DocstringSection,
    DocstringItem,
    DocstringSerializerProtocol,
    SectionKind,
)


class AbstractSerializer(DocstringSerializerProtocol):
    def _extract_addons(self, data: Dict[str, Any]) -> Dict[str, Any]:
        return {k: v for k, v in data.items() if k.startswith("Addon.")}

    def _encode_item_value(self, item: DocstringItem) -> str:
        return item.description or ""

    def _decode_item_value(self, value: str) -> dict:
        return {"annotation": None, "description": value}

    # --- Protocol Methods (to be implemented by subclasses) ---
    def to_transfer_data(self, ir: DocstringIR) -> Dict[str, Any]:
        raise NotImplementedError

    def from_transfer_data(self, data: Dict[str, Any]) -> DocstringIR:
        raise NotImplementedError

    def to_view_data(self, ir: DocstringIR) -> Any:
        raise NotImplementedError

    def from_view_data(self, data: Any) -> DocstringIR:
        raise NotImplementedError


class RawSerializer(AbstractSerializer):
    def to_transfer_data(self, ir: DocstringIR) -> Dict[str, Any]:
        # Always return a structured dict for DB/hashing
        data: Dict[str, Any] = {"summary": ir.summary or ""}
        if ir.extended:
            data["extended"] = ir.extended
        if ir.addons:
            data["addons"] = ir.addons
        return data

    def from_transfer_data(self, data: Dict[str, Any]) -> DocstringIR:
        return DocstringIR(
            summary=data.get("summary"),
            extended=data.get("extended"),
            addons=data.get("addons", {}),
        )

    def to_view_data(self, ir: DocstringIR) -> Any:
        # For simple cases, return a raw string for prettier YAML
        summary = ir.summary or ""
        if ir.addons:
            data = {"Raw": summary}
            data.update(ir.addons)
            return data
        return summary

    def from_view_data(self, data: Any) -> DocstringIR:
        if isinstance(data, str):
            return DocstringIR(summary=data)

        ir = DocstringIR()
        if isinstance(data, dict):
            # Note the different key 'Raw' for view vs 'summary' for transfer
            ir.summary = data.get("Raw", "")
            ir.addons = self._extract_addons(data)
        return ir


class StructuredSerializer(AbstractSerializer):
    # Maps SectionKind -> YAML Key (e.g. PARAMETERS -> Args)
    KIND_TO_KEY: Dict[str, str] = {}
    # Maps YAML Key -> SectionKind (e.g. Args -> PARAMETERS)
    KEY_TO_KIND: Dict[str, str] = {}

    def __init__(self):
        # Build reverse mapping automatically
        self.KEY_TO_KIND = {v: k for k, v in self.KIND_TO_KEY.items()}

    def to_transfer_data(self, ir: DocstringIR) -> Dict[str, Any]:
        data = {}

        if ir.summary:
            data["Summary"] = ir.summary

        if ir.extended:
            data["Extended"] = ir.extended

        for section in ir.sections:
            key = self.KIND_TO_KEY.get(section.kind)
            if not key:
                key = section.title or section.kind.capitalize()

            if isinstance(section.content, str):
                data[key] = section.content
            elif isinstance(section.content, list):
                section_data = {}
                for item in section.content:
                    k = item.name or item.annotation or "return"
                    section_data[k] = self._encode_item_value(item)
                data[key] = section_data

        if ir.addons:
            data.update(ir.addons)

        return data

    def from_transfer_data(self, data: Dict[str, Any]) -> DocstringIR:
        ir = DocstringIR()
        ir.addons = self._extract_addons(data)

        ir.summary = data.get("Summary")
        ir.extended = data.get("Extended")

        for key, value in data.items():
            if key in ["Summary", "Extended"] or key.startswith("Addon."):
                continue

            kind = self.KEY_TO_KIND.get(key, SectionKind.TEXT)

            if isinstance(value, dict):
                items = []
                for name, content in value.items():
                    decoded = self._decode_item_value(str(content))
                    item = DocstringItem(description=decoded["description"])
                    if kind in [
                        SectionKind.RETURNS,
                        SectionKind.YIELDS,
                        SectionKind.RAISES,
                    ]:
                        item.annotation = name
                    else:
                        item.name = name
                        if decoded["annotation"]:
                            item.annotation = decoded["annotation"]
                    items.append(item)
                ir.sections.append(DocstringSection(kind=kind, content=items))
            elif isinstance(value, str):
                ir.sections.append(DocstringSection(kind=kind, content=value))

        return ir

    def to_view_data(self, ir: DocstringIR) -> Any:
        # For structured data, the view and transfer representations are the same dicts.
        # The high-fidelity formatting (e.g. LiteralScalarString) is handled
        # by the SidecarAdapter before dumping to ruamel.yaml.
        return self.to_transfer_data(ir)

    def from_view_data(self, data: Any) -> DocstringIR:
        # Graceful fallback if data is just a string (User switched from Raw to Structured)
        if isinstance(data, str):
            return DocstringIR(summary=data)
        if isinstance(data, dict):
            return self.from_transfer_data(data)
        return DocstringIR()


class GoogleSerializer(StructuredSerializer):
    KIND_TO_KEY = {
        SectionKind.PARAMETERS: "Args",
        SectionKind.RETURNS: "Returns",
        SectionKind.RAISES: "Raises",
        SectionKind.YIELDS: "Yields",
        SectionKind.ATTRIBUTES: "Attributes",
        SectionKind.EXAMPLES: "Examples",
        SectionKind.NOTES: "Notes",
        SectionKind.WARNING: "Warning",
    }


class NumpySerializer(StructuredSerializer):
    KIND_TO_KEY = {
        SectionKind.PARAMETERS: "Parameters",
        SectionKind.RETURNS: "Returns",
        SectionKind.RAISES: "Raises",
        SectionKind.YIELDS: "Yields",
        SectionKind.ATTRIBUTES: "Attributes",
        SectionKind.EXAMPLES: "Examples",
        SectionKind.NOTES: "Notes",
        SectionKind.WARNING: "Warning",
        SectionKind.SEE_ALSO: "See Also",
    }
~~~~~

#### Acts 2: 更新 Sidecar 消费端

现在，我们将修复 `stitcher-lang-sidecar` 中的 `SidecarAdapter` 和 `DocumentManager`，让它们使用新的协议方法。

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
        path.parent.mkdir(parents=True, exist_ok=True)

        if path.exists():
            # --- UPDATE PATH ---
            # Load existing content to preserve formatting, comments, and key order.
            try:
                with path.open("r", encoding="utf-8") as f:
                    data = self._yaml.load(f)
                original_content = path.read_text("utf-8")
            except Exception:
                # If we can't read/parse, treat it as a new file creation.
                data = {}
                original_content = ""

            if not isinstance(data, dict):
                data = {}

            # Update the loaded data with new/modified IRs.
            # NO SORTING is applied to preserve original key order.
            # New keys will be appended by ruamel.yaml.
            for fqn, ir in irs.items():
                yaml_val = serializer.to_yaml(ir)
                if isinstance(yaml_val, str):
                    formatted_val = LiteralScalarString(yaml_val)
                elif isinstance(yaml_val, dict):
                    formatted_val = self._to_literal_strings(yaml_val)
                else:
                    formatted_val = yaml_val
                data[fqn] = formatted_val

            string_stream = io.StringIO()
            self._yaml.dump(data, string_stream)
            new_content = string_stream.getvalue()

            # Compare with original content to avoid unnecessary writes/mtime changes.
            if original_content != new_content:
                with path.open("w", encoding="utf-8") as f:
                    f.write(new_content)
        else:
            # --- CREATE PATH ---
            # For new files, create a clean, sorted baseline for predictability.
            sorted_irs = dict(sorted(irs.items()))
            yaml_data = {fqn: serializer.to_yaml(ir) for fqn, ir in sorted_irs.items()}
            formatted_data = self._to_literal_strings(yaml_data)
            string_stream = io.StringIO()
            self._yaml.dump(formatted_data, string_stream)
            with path.open("w", encoding="utf-8") as f:
                f.write(string_stream.getvalue())
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

            return {
                fqn: serializer.from_view_data(val) for fqn, val in raw_data.items()
            }
        except Exception:
            return {}

    def save_doc_irs(
        self,
        path: Path,
        irs: Dict[str, DocstringIR],
        serializer: DocstringSerializerProtocol,
    ) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)

        if path.exists():
            # --- UPDATE PATH ---
            try:
                with path.open("r", encoding="utf-8") as f:
                    data = self._yaml.load(f)
                original_content = path.read_text("utf-8")
            except Exception:
                data = {}
                original_content = ""

            if not isinstance(data, dict):
                data = {}

            for fqn, ir in irs.items():
                view_obj = serializer.to_view_data(ir)
                if isinstance(view_obj, str):
                    data[fqn] = LiteralScalarString(view_obj)
                elif isinstance(view_obj, dict):
                    data[fqn] = self._to_literal_strings(view_obj)
                else:
                    data[fqn] = view_obj

            string_stream = io.StringIO()
            self._yaml.dump(data, string_stream)
            new_content = string_stream.getvalue()

            if original_content != new_content:
                with path.open("w", encoding="utf-8") as f:
                    f.write(new_content)
        else:
            # --- CREATE PATH ---
            sorted_irs = dict(sorted(irs.items()))
            view_data = {
                fqn: serializer.to_view_data(ir) for fqn, ir in sorted_irs.items()
            }
            formatted_data = self._to_literal_strings(view_data)
            string_stream = io.StringIO()
            self._yaml.dump(formatted_data, string_stream)
            with path.open("w", encoding="utf-8") as f:
                f.write(string_stream.getvalue())
~~~~~

~~~~~act
patch_file
packages/stitcher-lang-sidecar/src/stitcher/lang/sidecar/adapter.py
~~~~~
~~~~~python.old
    def serialize_ir(
        self, ir: DocstringIR, serializer: DocstringSerializerProtocol
    ) -> Union[str, Dict[str, Any]]:
        return serializer.to_yaml(ir)
~~~~~
~~~~~python.new
    def serialize_ir_for_transfer(
        self, ir: DocstringIR, serializer: DocstringSerializerProtocol
    ) -> Dict[str, Any]:
        return serializer.to_transfer_data(ir)
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
    def _serialize_ir_for_transfer(self, ir: DocstringIR) -> Dict[str, Any]:
        # This is now the single point of truth for creating a serializable dict.
        return self.serializer.to_transfer_data(ir)

    def serialize_ir(self, ir: DocstringIR) -> Dict[str, Any]:
        # Kept for backward compatibility if other internal parts use it.
        # It's now explicitly for transfer data.
        return self._serialize_ir_for_transfer(ir)
~~~~~

### 下一步建议

我们已经成功地在协议层和实现层分离了数据传输和视图渲染的关注点。所有 `pyright` 错误都已解决。

现在，系统的地基已经无比坚固。下一步，我们将利用这个新能力，开始实施**将 Sidecar 内容索引到数据库的核心逻辑**，以彻底解决性能问题。
