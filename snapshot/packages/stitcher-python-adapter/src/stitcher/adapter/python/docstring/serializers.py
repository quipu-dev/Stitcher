from typing import Dict, Any, Union
from stitcher.spec import (
    DocstringIR,
    DocstringSection,
    DocstringItem,
    DocstringSerializerProtocol,
    SectionKind,
)


class BaseSerializer(DocstringSerializerProtocol):
    def _extract_addons(self, data: Dict[str, Any]) -> Dict[str, Any]:
        return {k: v for k, v in data.items() if k.startswith("Addon.")}

    def _encode_item_value(self, item: DocstringItem) -> str:
        return item.description or ""

    def _decode_item_value(self, value: str) -> dict:
        return {"annotation": None, "description": value}

    def to_yaml(self, ir: DocstringIR) -> Union[str, Dict[str, Any]]:
        raise NotImplementedError

    def from_yaml(self, data: Union[str, Dict[str, Any]]) -> DocstringIR:
        raise NotImplementedError


class RawSerializer(BaseSerializer):
    def to_yaml(self, ir: DocstringIR) -> Union[str, Dict[str, Any]]:
        summary = ir.summary or ""
        if ir.addons:
            data = {"Raw": summary}
            data.update(ir.addons)
            return data
        return summary

    def from_yaml(self, data: Union[str, Dict[str, Any]]) -> DocstringIR:
        if isinstance(data, str):
            return DocstringIR(summary=data)

        ir = DocstringIR()
        if isinstance(data, dict):
            ir.summary = data.get("Raw", "")
            ir.addons = self._extract_addons(data)
        return ir


class StructuredSerializer(BaseSerializer):
    # Maps SectionKind -> YAML Key (e.g. PARAMETERS -> Args)
    KIND_TO_KEY: Dict[str, str] = {}
    # Maps YAML Key -> SectionKind (e.g. Args -> PARAMETERS)
    KEY_TO_KIND: Dict[str, str] = {}

    def __init__(self):
        # Build reverse mapping automatically
        self.KEY_TO_KIND = {v: k for k, v in self.KIND_TO_KEY.items()}

    def to_yaml(self, ir: DocstringIR) -> Dict[str, Any]:
        data = {}

        if ir.summary:
            data["Summary"] = ir.summary

        if ir.extended:
            data["Extended"] = ir.extended

        for section in ir.sections:
            key = self.KIND_TO_KEY.get(section.kind)
            if not key:
                # Fallback for unknown sections: use title or capitalized kind
                key = section.title or section.kind.capitalize()

            if isinstance(section.content, str):
                data[key] = section.content
            elif isinstance(section.content, list):
                # Dict[name, encoded_value]
                section_data = {}
                for item in section.content:
                    # If item has no name (e.g. Returns/Raises), we need a strategy.
                    # For Returns/Raises, Google/NumPy style often puts type as name or key.
                    # We use item.annotation as key if name is missing?
                    # Or just a list? YAML dicts are better.

                    k = item.name
                    if not k:
                        # Fallback for return/raises where name might be empty but annotation exists
                        k = item.annotation or "return"  # Fallback key

                    section_data[k] = self._encode_item_value(item)

                data[key] = section_data

        if ir.addons:
            data.update(ir.addons)

        return data

    def from_yaml(self, data: Union[str, Dict[str, Any]]) -> DocstringIR:
        # Graceful fallback if data is just a string (User switched from Raw to Structured)
        if isinstance(data, str):
            return DocstringIR(summary=data)

        ir = DocstringIR()
        ir.addons = self._extract_addons(data)

        ir.summary = data.get("Summary")
        ir.extended = data.get("Extended")

        for key, value in data.items():
            if key in ["Summary", "Extended"] or key.startswith("Addon."):
                continue

            kind = self.KEY_TO_KIND.get(
                key, SectionKind.TEXT
            )  # Default to text if unknown key

            # Heuristic: If it's a dict, parse as items. If string, parse as text content.
            if isinstance(value, dict):
                items = []
                for name, content in value.items():
                    decoded = self._decode_item_value(str(content))

                    # Reconstruction logic
                    item = DocstringItem(description=decoded["description"])

                    if kind in [
                        SectionKind.RETURNS,
                        SectionKind.YIELDS,
                        SectionKind.RAISES,
                    ]:
                        # For these, the 'key' in YAML usually represents the Type/Exception
                        # We stored it as 'name' in section_data above for persistence
                        # But semantically it maps to annotation for Returns/Raises
                        item.annotation = name
                        # item.name remains None
                    else:
                        item.name = name
                        if decoded["annotation"]:
                            item.annotation = decoded["annotation"]

                    items.append(item)

                ir.sections.append(DocstringSection(kind=kind, content=items))

            elif isinstance(value, str):
                ir.sections.append(DocstringSection(kind=kind, content=value))

        return ir


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
