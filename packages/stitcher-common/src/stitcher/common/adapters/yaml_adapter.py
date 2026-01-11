from pathlib import Path
from typing import Dict, Any
import yaml

from stitcher.common.interfaces import DocumentAdapter


class YamlAdapter(DocumentAdapter):
    def load(self, path: Path) -> Dict[str, Any]:
        if not path.exists():
            return {}

        try:
            with path.open("r", encoding="utf-8") as f:
                content = yaml.safe_load(f)

            if not isinstance(content, dict):
                return {}

            # Allow values to be dicts or strings
            return {str(k): v for k, v in content.items() if v is not None}

        except yaml.YAMLError:
            return {}

    def dump(self, data: Dict[str, Any]) -> str:
        sorted_data = dict(sorted(data.items()))

        class MultilineDumper(yaml.SafeDumper):
            pass

        def str_presenter(dumper, data):
            return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|")

        MultilineDumper.add_representer(str, str_presenter)

        return yaml.dump(
            sorted_data,
            Dumper=MultilineDumper,
            allow_unicode=True,
            default_flow_style=False,
            sort_keys=False,
        )

    def save(self, path: Path, data: Dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        sorted_data = dict(sorted(data.items()))

        class MultilineDumper(yaml.SafeDumper):
            pass

        def str_presenter(dumper, data):
            return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|")

        MultilineDumper.add_representer(str, str_presenter)

        new_content = yaml.dump(
            sorted_data,
            Dumper=MultilineDumper,
            allow_unicode=True,
            default_flow_style=False,
            sort_keys=False,
        )

        if path.exists():
            try:
                old_content = path.read_text(encoding="utf-8")
                if old_content == new_content:
                    return
            except (OSError, UnicodeDecodeError):
                # If we can't read it or it's not text, assume we need to overwrite
                pass

        with path.open("w", encoding="utf-8") as f:
            f.write(new_content)
