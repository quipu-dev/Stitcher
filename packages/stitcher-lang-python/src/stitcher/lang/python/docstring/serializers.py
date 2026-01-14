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