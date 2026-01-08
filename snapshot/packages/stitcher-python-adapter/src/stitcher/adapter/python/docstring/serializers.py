import re
from typing import Dict, Any, Union, List, Optional
from stitcher.spec import (
    DocstringIR,
    DocstringSection,
    DocstringItem,
    DocstringSerializerProtocol,
    SectionKind,
)


class BaseSerializer(DocstringSerializerProtocol):
    """
    Base serializer that handles Addon preservation and common utilities.
    """

    def _extract_addons(self, data: Dict[str, Any]) -> Dict[str, Any]:
        return {k: v for k, v in data.items() if k.startswith("Addon.")}

    def _encode_item_value(self, item: DocstringItem) -> str:
        """
        Encodes DocstringItem into a string format: "(type) description".
        """
        desc = item.description or ""
        if item.annotation:
            return f"({item.annotation}) {desc}"
        return desc

    def _decode_item_value(self, value: str) -> dict:
        """
        Decodes string format "(type) description" into parts.
        """
        # Simple regex to catch (type) at the start
        match = re.match(r"^\((.+?)\)\s*(.*)", value, re.DOTALL)
        if match:
            return {"annotation": match.group(1), "description": match.group(2)}
        return {"annotation": None, "description": value}

    def to_yaml(self, ir: DocstringIR) -> Dict[str, Any]:
        raise NotImplementedError

    def from_yaml(self, data: Union[str, Dict[str, Any]]) -> DocstringIR:
        raise NotImplementedError


class RawSerializer(BaseSerializer):
    """
    Legacy serializer.
    Format:
        "summary string"
    OR
        {"Raw": "summary string", "Addon...": ...}
    """

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
    """
    Base class for Google/NumPy serializers.
    """
    
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
                    k = item.name
                    if not k:
                        # Fallback for return/raises where name might be empty but annotation exists
                        k = item.annotation or "return"  # Fallback key
                    
                    # For sections where the key IS the type, value is just the description.
                    if section.kind in [
                        SectionKind.RETURNS,
                        SectionKind.YIELDS,
                        SectionKind.RAISES,
                    ]:
                        section_data[k] = item.description or ""
                    else:
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
            
            kind = self.KEY_TO_KIND.get(key, SectionKind.TEXT) # Default to text if unknown key
            
            # Heuristic: If it's a dict, parse as items. If string, parse as text content.
            if isinstance(value, dict):
                items = []
                for name, content in value.items():
                    decoded = self._decode_item_value(str(content))
                    
                    # Reconstruction logic
                    item = DocstringItem(description=decoded["description"])
                    
                    # The `name` variable here is the key from the YAML dict.
                    if kind in [SectionKind.RETURNS, SectionKind.YIELDS, SectionKind.RAISES]:
                        # For these kinds, the key is the annotation.
                        item.annotation = name
                        item.name = None
                    else:
                        # For parameters/attributes, the key is the name.
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