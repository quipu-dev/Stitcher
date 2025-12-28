Of course. My apologies. The refactoring was incomplete. In my haste to remove the old packages, I missed another critical dependency chain. The `DocumentManager` still depends on `stitcher.io`, which no longer exists.

You are correct to point this out. The `DocumentAdapter` and `YamlAdapter` are general IO utilities. The correct place for them in the new architecture is `stitcher-common`.

## [WIP] fix: Relocate IO adapters to stitcher-common

### 错误分析
1.  **根本原因**: `ModuleNotFoundError: No module named 'stitcher.io'`.
2.  **具体分析**: The file `packages/stitcher-application/src/stitcher/app/services/doc_manager.py` contains the import `from stitcher.io import DocumentAdapter, YamlAdapter`. However, the `stitcher-io` package was deleted in the previous step.
3.  **架构修正**: The `DocumentAdapter` protocol and the `YamlAdapter` implementation are foundational IO utilities. They are not specific to the core application logic. Their correct home is the `stitcher-common` package, which houses shared tools and definitions used across the ecosystem.

### 用户需求
Fix the final `ImportError` by relocating the necessary IO components from the defunct `stitcher-io` package to `stitcher-common` and updating the import paths.

### 评论
This is the final piece of the puzzle. This error highlights the deep-seated nature of the original coupling. By moving these last components to their proper, shared location, we complete the architectural vision of a decoupled core application that relies on common, swappable services.

### 目标
1.  Relocate the `DocumentAdapter` protocol to `stitcher-common`.
2.  Relocate the `YamlAdapter` implementation to `stitcher-common`.
3.  Update `stitcher-common`'s public API to export these components.
4.  Fix the import statement in `stitcher-application`'s `doc_manager.py`.

### 基本原理
Placing shared, low-level utilities like file format adapters into a common library (`stitcher-common`) is a standard practice that promotes reuse and clarifies dependencies. The application (`stitcher-application`) consumes these common utilities.

### 标签
#intent/fix #flow/ready #priority/critical #comp/io #comp/common #scope/core #ai/instruct #task/domain/architecture #task/object/dependencies #task/action/fix-imports #task-state/end

---

### Script

#### Acts 1: Re-create DocumentAdapter Protocol in `stitcher-common`
We'll create a new `interfaces.py` in `stitcher-common`.

~~~~~act
write_file
packages/stitcher-common/src/stitcher/common/interfaces.py
~~~~~
~~~~~python
from typing import Dict, Protocol
from pathlib import Path


class DocumentAdapter(Protocol):
    def load(self, path: Path) -> Dict[str, str]: ...

    def save(self, path: Path, data: Dict[str, str]) -> None: ...
~~~~~

#### Acts 2: Re-create YamlAdapter in `stitcher-common`
We'll create a new `adapters` sub-package for this.

~~~~~act
run_command
~~~~~
~~~~~
mkdir -p packages/stitcher-common/src/stitcher/common/adapters
~~~~~

~~~~~act
write_file
packages/stitcher-common/src/stitcher/common/adapters/yaml_adapter.py
~~~~~
~~~~~python
from pathlib import Path
from typing import Dict
import yaml

from stitcher.common.interfaces import DocumentAdapter


class YamlAdapter(DocumentAdapter):
    def load(self, path: Path) -> Dict[str, str]:
        if not path.exists():
            return {}

        try:
            with path.open("r", encoding="utf-8") as f:
                content = yaml.safe_load(f)

            if not isinstance(content, dict):
                return {}

            return {str(k): str(v) for k, v in content.items() if v is not None}

        except yaml.YAMLError:
            return {}

    def save(self, path: Path, data: Dict[str, str]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        sorted_data = dict(sorted(data.items()))
        
        class MultilineDumper(yaml.SafeDumper):
            pass

        def str_presenter(dumper, data):
            return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|")

        MultilineDumper.add_representer(str, str_presenter)

        with path.open("w", encoding="utf-8") as f:
            yaml.dump(
                sorted_data,
                f,
                Dumper=MultilineDumper,
                allow_unicode=True,
                default_flow_style=False,
                sort_keys=False,
            )
~~~~~

#### Acts 3: Export the new components from `stitcher-common`
Update the `__init__.py`.

~~~~~act
patch_file
packages/stitcher-common/src/stitcher/common/__init__.py
~~~~~
~~~~~python.old
from .formatting import format_docstring, parse_docstring
from .messaging.bus import MessageBus

# --- Composition Root for Stitcher's Core Services ---
~~~~~
~~~~~python.new
from .formatting import format_docstring, parse_docstring
from .messaging.bus import MessageBus
from .interfaces import DocumentAdapter
from .adapters.yaml_adapter import YamlAdapter

# --- Composition Root for Stitcher's Core Services ---
~~~~~

~~~~~act
patch_file
packages/stitcher-common/src/stitcher/common/__init__.py
~~~~~
~~~~~python.old
__all__ = [
    "bus",
    "stitcher_nexus",
    "stitcher_loader",
    "format_docstring",
    "parse_docstring",
]
~~~~~
~~~~~python.new
__all__ = [
    "bus",
    "stitcher_nexus",
    "stitcher_loader",
    "format_docstring",
    "parse_docstring",
    "DocumentAdapter",
    "YamlAdapter",
]
~~~~~

#### Acts 4: Fix the import in `doc_manager.py`
This is the final fix that resolves the `ModuleNotFoundError`.

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/services/doc_manager.py
~~~~~
~~~~~python.old
from typing import Dict, Optional, Any

from stitcher.spec import ModuleDef, ClassDef, FunctionDef
from stitcher.io import DocumentAdapter, YamlAdapter


class DocumentManager:
    def __init__(self, root_path: Path, adapter: Optional[DocumentAdapter] = None):
~~~~~
~~~~~python.new
from typing import Dict, Optional, Any

from stitcher.spec import ModuleDef, ClassDef, FunctionDef
from stitcher.common import DocumentAdapter, YamlAdapter


class DocumentManager:
    def __init__(self, root_path: Path, adapter: Optional[DocumentAdapter] = None):
~~~~~

### 下一步建议
The last remaining import error should now be resolved. Let's run the test suite one more time. A successful run will confirm that the refactoring is complete and the architecture is stable.
