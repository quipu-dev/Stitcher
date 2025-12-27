当然，这是一个合理的重构步骤，遵循了 DRY 原则。删除冗余的 `stitcher-needle` 包并统一使用 `pyneedle` 可以使项目更清晰、更易于维护。

我将为您生成一个详细的计划，该计划将分步完成代码迁移、配置更新和最后的目录清理。

## [WIP] refactor: 移除 stitcher-needle 并迁移至 pyneedle

### 用户需求
用户要求删除 `packages/stitcher-needle` 目录及其在项目中的所有引用，并将所有相关功能的使用迁移到新的 `pyneedle` 系列包中，以遵循 DRY 原则。

### 评论
这是一个关键的重构步骤，可以消除代码重复，降低维护成本，并统一项目的依赖关系图。将专用的 `stitcher-needle` 迁移到一个通用的 `pyneedle` 实现，也为未来将 `needle` 运行时用于其他项目奠定了基础。

### 目标
1.  **代码迁移**: 更新所有 `stitcher` 包中的 Python 代码，将对 `stitcher.needle` 的导入和使用，改为对 `needle` 或 `needle.pointer` 的导入和使用。
2.  **依赖更新**: 修改所有 `pyproject.toml` 文件，移除对 `stitcher-needle` 的依赖。
3.  **配置清理**: 更新项目根目录的 `pyproject.toml` 和 `pyrightconfig.json`，移除与 `stitcher-needle` 相关的路径配置。
4.  **物理删除**: 完全删除 `packages/stitcher-needle` 目录。

### 基本原理
此计划将采用一个安全、分步的策略：
1.  **重构代码**：首先修改所有应用代码，使其不再依赖于即将被删除的包。我们将 `stitcher.needle` 的引用系统地替换为 `pyneedle` 提供的等效功能（例如 `from needle.pointer import L`, `from needle import nexus`）。
2.  **清理配置**：在代码层面解耦后，我们安全地从所有配置文件（构建系统、测试配置、静态分析工具）中移除对旧包的引用。
3.  **最终删除**：当前两个步骤完成后，旧包已成为孤立的代码，此时可以安全地将其从文件系统中删除，而不会破坏任何功能。

这种方法确保了在整个重构过程的每个阶段，项目都处于一个可验证的、一致的状态。

### 标签
#intent/refine #flow/ready #priority/high #comp/build #comp/cli #comp/common #comp/application #comp/tests #scope/dx #ai/instruct #task/domain/build #task/object/stitcher-needle #task/action/removal #task/state/begin

---

### Script

#### Acts 1: 更新应用和测试代码中的导入语句和 API 调用

首先，我们将修改所有 Python 源代码，将对 `stitcher.needle` 的引用切换到新的 `pyneedle` 包。

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/core.py
~~~~~
~~~~~python.old
from stitcher.needle import L
~~~~~
~~~~~python.new
from needle.pointer import L
~~~~~
~~~~~act
patch_file
packages/stitcher-cli/src/stitcher/cli/__init__.py
~~~~~
~~~~~python.old
from stitcher.needle import needle

# --- Auto-register CLI assets ---
try:
    _assets_path = Path(__file__).parent / "assets"
    if _assets_path.is_dir():
        needle.add_root(_assets_path)
~~~~~
~~~~~python.new
from needle import nexus

# --- Auto-register CLI assets ---
try:
    _assets_path = Path(__file__).parent / "assets"
    if _assets_path.is_dir():
        nexus.add_root(_assets_path)
~~~~~
~~~~~act
patch_file
packages/stitcher-cli/src/stitcher/cli/main.py
~~~~~
~~~~~python.old
from stitcher.app import StitcherApp
from stitcher.common import bus
from stitcher.needle import L, needle
from .rendering import CliRenderer

app = typer.Typer(
    name="stitcher",
    help=needle.get(L.cli.app.description),
    no_args_is_help=True,
)
~~~~~
~~~~~python.new
from stitcher.app import StitcherApp
from stitcher.common import bus
from needle.pointer import L
from needle import nexus
from .rendering import CliRenderer

app = typer.Typer(
    name="stitcher",
    help=nexus.get(L.cli.app.description),
    no_args_is_help=True,
)
~~~~~
~~~~~act
patch_file
packages/stitcher-cli/src/stitcher/cli/main.py
~~~~~
~~~~~python.old
@app.command(help=needle.get(L.cli.command.generate.help))
def generate():
~~~~~
~~~~~python.new
@app.command(help=nexus.get(L.cli.command.generate.help))
def generate():
~~~~~
~~~~~act
patch_file
packages/stitcher-cli/src/stitcher/cli/main.py
~~~~~
~~~~~python.old
@app.command(help=needle.get(L.cli.command.init.help))
def init():
~~~~~
~~~~~python.new
@app.command(help=nexus.get(L.cli.command.init.help))
def init():
~~~~~
~~~~~act
patch_file
packages/stitcher-cli/src/stitcher/cli/main.py
~~~~~
~~~~~python.old
@app.command(help=needle.get(L.cli.command.check.help))
def check():
~~~~~
~~~~~python.new
@app.command(help=nexus.get(L.cli.command.check.help))
def check():
~~~~~
~~~~~act
patch_file
packages/stitcher-cli/src/stitcher/cli/main.py
~~~~~
~~~~~python.old
@app.command(help=needle.get(L.cli.command.strip.help))
def strip():
~~~~~
~~~~~python.new
@app.command(help=nexus.get(L.cli.command.strip.help))
def strip():
~~~~~
~~~~~act
patch_file
packages/stitcher-cli/src/stitcher/cli/main.py
~~~~~
~~~~~python.old
@app.command(help=needle.get(L.cli.command.eject.help))
def eject():
~~~~~
~~~~~python.new
@app.command(help=nexus.get(L.cli.command.eject.help))
def eject():
~~~~~
~~~~~act
patch_file
packages/stitcher-cli/src/stitcher/cli/main.py
~~~~~
~~~~~python.old
@app.command(help=needle.get(L.cli.command.hydrate.help))
def hydrate(
    strip: bool = typer.Option(
        False, "--strip", help=needle.get(L.cli.option.strip.help)
    ),
    force: bool = typer.Option(
        False,
        "--force",
        help=needle.get(L.cli.option.force.help),
    ),
    reconcile: bool = typer.Option(
        False,
        "--reconcile",
        help=needle.get(L.cli.option.reconcile.help),
    ),
):
~~~~~
~~~~~python.new
@app.command(help=nexus.get(L.cli.command.hydrate.help))
def hydrate(
    strip: bool = typer.Option(
        False, "--strip", help=nexus.get(L.cli.option.strip.help)
    ),
    force: bool = typer.Option(
        False,
        "--force",
        help=nexus.get(L.cli.option.force.help),
    ),
    reconcile: bool = typer.Option(
        False,
        "--reconcile",
        help=nexus.get(L.cli.option.reconcile.help),
    ),
):
~~~~~
~~~~~act
patch_file
packages/stitcher-common/src/stitcher/common/__init__.py
~~~~~
~~~~~python.old
# Make core singletons easily accessible
from .messaging.bus import bus
from stitcher.needle import needle
from pathlib import Path

# --- Auto-register built-in assets ---
# Find the path to our packaged assets directory and register it with Needle.
# This makes default translations and messages available out-of-the-box.
try:
    # __file__ gives the path to this __init__.py file
    _assets_path = Path(__file__).parent / "assets"
    if _assets_path.is_dir():
        needle.add_root(_assets_path)
~~~~~
~~~~~python.new
# Make core singletons easily accessible
from .messaging.bus import bus
from needle import nexus
from pathlib import Path

# --- Auto-register built-in assets ---
# Find the path to our packaged assets directory and register it with Needle.
# This makes default translations and messages available out-of-the-box.
try:
    # __file__ gives the path to this __init__.py file
    _assets_path = Path(__file__).parent / "assets"
    if _assets_path.is_dir():
        nexus.add_root(_assets_path)
~~~~~
~~~~~act
patch_file
packages/stitcher-common/src/stitcher/common/messaging/bus.py
~~~~~
~~~~~python.old
from typing import Any, Optional, Union

from stitcher.needle import SemanticPointer, needle
from .protocols import Renderer


class MessageBus:
~~~~~
~~~~~python.new
from typing import Any, Optional, Union

from needle.pointer import SemanticPointer
from needle import nexus
from .protocols import Renderer


class MessageBus:
~~~~~
~~~~~act
patch_file
packages/stitcher-common/src/stitcher/common/messaging/bus.py
~~~~~
~~~~~python.old
        # Resolve the pointer to a string template using the Needle runtime
        template = needle.get(msg_id)
~~~~~
~~~~~python.new
        # Resolve the pointer to a string template using the Needle runtime
        template = nexus.get(msg_id)
~~~~~
~~~~~act
patch_file
packages/stitcher-common/src/stitcher/common/messaging/bus.py
~~~~~
~~~~~python.old
    def render_to_string(
        self, msg_id: Union[str, SemanticPointer], **kwargs: Any
    ) -> str:
        template = needle.get(msg_id)
        try:
            return template.format(**kwargs)
~~~~~
~~~~~python.new
    def render_to_string(
        self, msg_id: Union[str, SemanticPointer], **kwargs: Any
    ) -> str:
        template = nexus.get(msg_id)
        try:
            return template.format(**kwargs)
~~~~~
~~~~~act
patch_file
packages/stitcher-common/tests/test_message_bus.py
~~~~~
~~~~~python.old
import pytest
from stitcher.common.messaging.bus import MessageBus
from stitcher.common.messaging.protocols import Renderer
from stitcher.needle import L
from stitcher.test_utils.needle import MockNeedle
~~~~~
~~~~~python.new
import pytest
from stitcher.common.messaging.bus import MessageBus
from stitcher.common.messaging.protocols import Renderer
from needle.pointer import L
from stitcher.test_utils.needle import MockNeedle
~~~~~
~~~~~act
patch_file
packages/stitcher-test-utils/src/stitcher/test_utils/bus.py
~~~~~
~~~~~python.old
from stitcher.common.messaging.bus import MessageBus
from stitcher.common.messaging.protocols import Renderer
from stitcher.needle import SemanticPointer
~~~~~
~~~~~python.new
from stitcher.common.messaging.bus import MessageBus
from stitcher.common.messaging.protocols import Renderer
from needle.pointer import SemanticPointer
~~~~~
~~~~~act
patch_file
packages/stitcher-test-utils/src/stitcher/test_utils/needle.py
~~~~~
~~~~~python.old
    def patch(self, monkeypatch: Any):
        # The target path must be where `needle` is used by the code under test.
        # In our case, MessageBus imports it.
        target_path = "stitcher.common.messaging.bus.needle.get"
        try:
            monkeypatch.setattr(target_path, self._mock_get)
~~~~~
~~~~~python.new
    def patch(self, monkeypatch: Any):
        # The target path must be where `nexus` is used by the code under test.
        # In our case, MessageBus imports it.
        target_path = "stitcher.common.messaging.bus.nexus.get"
        try:
            monkeypatch.setattr(target_path, self._mock_get)
~~~~~
~~~~~act
patch_file
tests/integration/test_check_command.py
~~~~~
~~~~~python.old
from stitcher.app import StitcherApp
from stitcher.needle import L
from stitcher.test_utils import SpyBus, WorkspaceFactory
~~~~~
~~~~~python.new
from stitcher.app import StitcherApp
from needle.pointer import L
from stitcher.test_utils import SpyBus, WorkspaceFactory
~~~~~
~~~~~act
patch_file
tests/integration/test_check_conflict.py
~~~~~
~~~~~python.old
from stitcher.app import StitcherApp
from stitcher.needle import L
from stitcher.test_utils import SpyBus, WorkspaceFactory
~~~~~
~~~~~python.new
from stitcher.app import StitcherApp
from needle.pointer import L
from stitcher.test_utils import SpyBus, WorkspaceFactory
~~~~~
~~~~~act
patch_file
tests/integration/test_check_policy.py
~~~~~
~~~~~python.old
from stitcher.app import StitcherApp
from stitcher.needle import L
from stitcher.test_utils import SpyBus, WorkspaceFactory
~~~~~
~~~~~python.new
from stitcher.app import StitcherApp
from needle.pointer import L
from stitcher.test_utils import SpyBus, WorkspaceFactory
~~~~~
~~~~~act
patch_file
tests/integration/test_check_signatures.py
~~~~~
~~~~~python.old
from stitcher.app import StitcherApp
from stitcher.needle import L
from stitcher.test_utils import SpyBus, WorkspaceFactory
~~~~~
~~~~~python.new
from stitcher.app import StitcherApp
from needle.pointer import L
from stitcher.test_utils import SpyBus, WorkspaceFactory
~~~~~
~~~~~act
patch_file
tests/integration/test_end_to_end.py
~~~~~
~~~~~python.old
import sys

from stitcher.app import StitcherApp
from stitcher.needle import L
from stitcher.test_utils import SpyBus, WorkspaceFactory
~~~~~
~~~~~python.new
import sys

from stitcher.app import StitcherApp
from needle.pointer import L
from stitcher.test_utils import SpyBus, WorkspaceFactory
~~~~~
~~~~~act
patch_file
tests/integration/test_hydrate_command.py
~~~~~
~~~~~python.old
import yaml
from stitcher.app import StitcherApp
from stitcher.needle import L
from stitcher.test_utils import SpyBus, WorkspaceFactory
~~~~~
~~~~~python.new
import yaml
from stitcher.app import StitcherApp
from needle.pointer import L
from stitcher.test_utils import SpyBus, WorkspaceFactory
~~~~~
~~~~~act
patch_file
tests/integration/test_init_command.py
~~~~~
~~~~~python.old
from stitcher.app import StitcherApp
from stitcher.needle import L
from stitcher.test_utils import SpyBus, WorkspaceFactory
~~~~~
~~~~~python.new
from stitcher.app import StitcherApp
from needle.pointer import L
from stitcher.test_utils import SpyBus, WorkspaceFactory
~~~~~
~~~~~act
patch_file
tests/integration/test_lifecycle_commands.py
~~~~~
~~~~~python.old
from textwrap import dedent
from stitcher.app import StitcherApp
from stitcher.needle import L
from stitcher.test_utils import SpyBus, WorkspaceFactory
~~~~~
~~~~~python.new
from textwrap import dedent
from stitcher.app import StitcherApp
from needle.pointer import L
from stitcher.test_utils import SpyBus, WorkspaceFactory
~~~~~
#### Acts 2: 更新包的依赖配置文件

现在，代码已经不再引用 `stitcher-needle`，我们可以安全地从各个 `pyproject.toml` 文件中移除对它的依赖。

~~~~~act
patch_file
packages/stitcher-application/pyproject.toml
~~~~~
~~~~~toml.old
dependencies = [
    "stitcher-spec",
    "stitcher-common",
    "stitcher-scanner",
    "stitcher-io",
    "stitcher-config",
    "stitcher-needle",
]
~~~~~
~~~~~toml.new
dependencies = [
    "stitcher-spec",
    "stitcher-common",
    "stitcher-scanner",
    "stitcher-io",
    "stitcher-config",
    "pyneedle",
]
~~~~~
~~~~~act
patch_file
packages/stitcher-application/pyproject.toml
~~~~~
~~~~~toml.old
[tool.uv.sources]
stitcher-spec = { workspace = true }
stitcher-common = { workspace = true }
stitcher-scanner = { workspace = true }
stitcher-io = { workspace = true }
stitcher-config = { workspace = true }
stitcher-needle = { workspace = true }
~~~~~
~~~~~toml.new
[tool.uv.sources]
stitcher-spec = { workspace = true }
stitcher-common = { workspace = true }
stitcher-scanner = { workspace = true }
stitcher-io = { workspace = true }
stitcher-config = { workspace = true }
pyneedle = { workspace = true }
~~~~~
~~~~~act
patch_file
packages/stitcher-cli/pyproject.toml
~~~~~
~~~~~toml.old
dependencies = [
    "stitcher-application",
    "stitcher-needle",
    "typer",
]
~~~~~
~~~~~toml.new
dependencies = [
    "stitcher-application",
    "pyneedle",
    "typer",
]
~~~~~
~~~~~act
patch_file
packages/stitcher-cli/pyproject.toml
~~~~~
~~~~~toml.old
[tool.uv.sources]
stitcher-application = { workspace = true }
stitcher-needle = { workspace = true }
~~~~~
~~~~~toml.new
[tool.uv.sources]
stitcher-application = { workspace = true }
pyneedle = { workspace = true }
~~~~~
~~~~~act
patch_file
packages/stitcher-test-utils/pyproject.toml
~~~~~
~~~~~toml.old
dependencies = [
    "stitcher-needle",
    "PyYAML",
    "tomli-w",
]
~~~~~
~~~~~toml.new
dependencies = [
    "pyneedle",
    "PyYAML",
    "tomli-w",
]
~~~~~
~~~~~act
patch_file
packages/stitcher-test-utils/pyproject.toml
~~~~~
~~~~~toml.old
[tool.uv.sources]
stitcher-needle = { workspace = true }
~~~~~
~~~~~toml.new
[tool.uv.sources]
pyneedle = { workspace = true }
~~~~~
#### Acts 3: 更新项目根配置

清理根 `pyproject.toml` 和 `pyrightconfig.json` 中的所有相关路径和依赖项。

~~~~~act
patch_file
pyproject.toml
~~~~~
~~~~~toml.old
    "pyneedle-spec",
    "stitcher-cli",
    "stitcher-application",
    "stitcher-needle",
    "stitcher-test-utils",
]
~~~~~
~~~~~toml.new
    "pyneedle-spec",
    "stitcher-cli",
    "stitcher-application",
    "stitcher-test-utils",
]
~~~~~
~~~~~act
patch_file
pyproject.toml
~~~~~
~~~~~toml.old
stitcher-cli = { workspace = true }
stitcher-needle = { workspace = true }
stitcher-test-utils = { workspace = true }
~~~~~
~~~~~toml.new
stitcher-cli = { workspace = true }
stitcher-test-utils = { workspace = true }
~~~~~

然后，请手动删除
```
    "packages/stitcher-needle/src",
```

#### Acts 4: 物理删除 stitcher-needle 包

最后一步，删除整个 `stitcher-needle` 目录。

~~~~~act
run_command
~~~~~
~~~~~bash
rm -rf packages/stitcher-needle
~~~~~
