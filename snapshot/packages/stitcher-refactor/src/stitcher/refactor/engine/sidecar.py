from typing import Dict, Any
from ruamel.yaml import YAML
import json
from io import StringIO


class SidecarUpdater:
    def update_keys(
        self, content: str, rename_map: Dict[str, str], is_yaml: bool
    ) -> str:
        """
        Loads a sidecar file (YAML or JSON), renames top-level keys
        according to the rename_map, and returns the updated content.
        """
        if is_yaml:
            return self._update_yaml_keys(content, rename_map)
        else:
            return self._update_json_keys(content, rename_map)

    def _resolve_new_key(self, key: str, rename_map: Dict[str, str]) -> str:
        # 1. Exact match
        if key in rename_map:
            return rename_map[key]

        # 2. Prefix match (for children keys like Class.method)
        # We look for the longest matching prefix to handle nested renames correctly.
        # e.g. key="A.B.c", map={"A": "X", "A.B": "Y"} -> should become "Y.c"
        matched_prefix = None
        
        for old_fqn in rename_map:
            # Check if key starts with old_fqn + "."
            prefix = old_fqn + "."
            if key.startswith(prefix):
                if matched_prefix is None or len(old_fqn) > len(matched_prefix):
                    matched_prefix = old_fqn
        
        if matched_prefix:
            new_prefix = rename_map[matched_prefix]
            return new_prefix + key[len(matched_prefix):]
            
        return key

    def _update_yaml_keys(self, content: str, rename_map: Dict[str, str]) -> str:
        parser = YAML()
        data = parser.load(content)
        if not isinstance(data, dict):
            return content

        new_data = {}
        for k, v in data.items():
            new_key = self._resolve_new_key(k, rename_map)
            new_data[new_key] = v

        string_stream = StringIO()
        parser.dump(new_data, string_stream)
        return string_stream.getvalue()

    def _update_json_keys(self, content: str, rename_map: Dict[str, str]) -> str:
        try:
            data = json.loads(content)
            if not isinstance(data, dict):
                return content
        except json.JSONDecodeError:
            return content

        new_data = {}
        for k, v in data.items():
            new_key = self._resolve_new_key(k, rename_map)
            new_data[new_key] = v

        return json.dumps(new_data, indent=2, sort_keys=True)