from pathlib import Path
from typing import Dict
import yaml

from stitcher.io.interfaces import DocumentAdapter


class YamlAdapter(DocumentAdapter):
    def load(self, path: Path) -> Dict[str, str]:
        if not path.exists():
            return {}

        try:
            with path.open("r", encoding="utf-8") as f:
                content = yaml.safe_load(f)

            if not isinstance(content, dict):
                # If file exists but is empty or list, return empty dict
                return {}

            # Ensure all values are strings
            return {str(k): str(v) for k, v in content.items() if v is not None}

        except yaml.YAMLError:
            # We might want to log this, but for the adapter contract,
            # returning empty or raising are options.
            # Given this is IO layer, letting exception bubble or wrapping it
            # would be better, but let's stick to simple contract for now:
            # If we can't read it, it's effectively empty/corrupt.
            # Rationale: 'stitcher check' will complain about missing docs anyway.
            return {}

    def save(self, path: Path, data: Dict[str, str]) -> None:
        if not data:
            # If data is empty, we don't necessarily need to create an empty file,
            # but if the file existed, we might want to clear it?
            # Let's decide to do nothing if data is empty to avoid cluttering fs?
            # No, 'save' implies persistence. If data is empty, file should be empty dict.
            pass

        # Ensure directory exists
        path.parent.mkdir(parents=True, exist_ok=True)

        # Sort keys for deterministic output
        sorted_data = dict(sorted(data.items()))

        # Custom Dumper to enforce literal block style for multiline strings
        class MultilineDumper(yaml.SafeDumper):
            pass

        def str_presenter(dumper, data):
            # Force literal block style for ALL strings to ensure consistency
            # and readability for documentation assets.
            return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|")

        MultilineDumper.add_representer(str, str_presenter)

        with path.open("w", encoding="utf-8") as f:
            # allow_unicode=True is essential for i18n
            # default_flow_style=False ensures block style (easier to read)
            # We use yaml.dump with our custom Dumper which inherits from SafeDumper
            yaml.dump(
                sorted_data,
                f,
                Dumper=MultilineDumper,
                allow_unicode=True,
                default_flow_style=False,
                sort_keys=False,  # We already sorted
            )
