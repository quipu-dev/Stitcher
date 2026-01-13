from typing import Dict, Any, List, Tuple
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
            parser = YAML()
            data = parser.load(content)
        else:
            data = json.loads(content)

        if not isinstance(data, dict):
            return content

        new_data = {}
        for key, value in data.items():
            new_key = rename_map.get(key, key)
            new_data[new_key] = value

        if is_yaml:
            string_stream = StringIO()
            parser.dump(new_data, string_stream)
            return string_stream.getvalue()
        else:
            return json.dumps(new_data, indent=2, sort_keys=True)