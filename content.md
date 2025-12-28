## [WIP] refactor: 使用测试工厂方法重构测试套件

### 用户需求
为了适配 `StitcherApp` 新的依赖注入构造函数，需要创建一个测试工厂方法 `create_test_app`，并批量重构所有测试用例，将直接的 `StitcherApp(...)` 实例化替换为对该工厂方法的调用。

### 评论
这是本次重构中最具侵入性的一步。通过引入 `create_test_app`，我们不仅修复了当前的破坏性变更，还为未来在测试中统一配置 App（例如默认注入某些 Mock）提供了中心化入口。
为了安全高效地处理大量文件，我们将编写一个一次性的 Python 脚本来执行代码替换。

### 目标
1.  更新 `stitcher-test-utils`，使其依赖 `stitcher-application` 和 `stitcher-python-adapter`。
2.  在 `stitcher-test-utils` 中实现 `create_test_app` 工厂函数。
3.  使用脚本批量将测试代码中的 `from stitcher.app import StitcherApp` 和 `StitcherApp(...)` 替换为新的工厂调用。

### 基本原理
测试代码不应关心 `StitcherApp` 的复杂构造细节（如 Parser、Adapter 的装配）。工厂模式将这些细节封装起来，使得测试代码只需关注“创建一个 App 并运行”这一高层意图。

### 标签
#intent/refine #flow/ready #priority/high #comp/tests #scope/core #ai/instruct #task/domain/architecture #task/object/test-suite #task/action/refactor-tests #task/state/end

---

### Script

#### Acts 1: 更新 stitcher-test-utils 依赖
首先，让测试工具包能够访问应用和适配器。

~~~~~act
patch_file
packages/stitcher-test-utils/pyproject.toml
~~~~~
~~~~~toml.old
dependencies = [
    "pyneedle",
    "PyYAML",
    "tomli-w",
]

[tool.hatch.build.targets.wheel]
packages = ["src/stitcher"]

[tool.uv.sources]
pyneedle = { workspace = true }
~~~~~
~~~~~toml.new
dependencies = [
    "pyneedle",
    "PyYAML",
    "tomli-w",
    "stitcher-application",
    "stitcher-python-adapter",
]

[tool.hatch.build.targets.wheel]
packages = ["src/stitcher"]

[tool.uv.sources]
pyneedle = { workspace = true }
stitcher-application = { workspace = true }
stitcher-python-adapter = { workspace = true }
~~~~~

#### Acts 2: 实现 create_test_app 工厂
在 `helpers.py` 中添加工厂函数。

~~~~~act
patch_file
packages/stitcher-test-utils/src/stitcher/test_utils/helpers.py
~~~~~
~~~~~python.old
import json
from pathlib import Path


def get_stored_hashes(project_root: Path, file_path: str) -> dict:
~~~~~
~~~~~python.new
import json
from pathlib import Path
from typing import Optional

from stitcher.app import StitcherApp
from stitcher.app.protocols import InteractionHandler
from stitcher.adapter.python import (
    PythonParser,
    PythonTransformer,
    PythonStubGenerator,
    PythonFingerprintStrategy,
)


def create_test_app(
    root_path: Path, interaction_handler: Optional[InteractionHandler] = None
) -> StitcherApp:
    """
    Factory to create a StitcherApp instance with Python adapters pre-configured for testing.
    """
    return StitcherApp(
        root_path=root_path,
        parser=PythonParser(),
        transformer=PythonTransformer(),
        stub_generator=PythonStubGenerator(),
        fingerprint_strategy=PythonFingerprintStrategy(),
        interaction_handler=interaction_handler,
    )


def get_stored_hashes(project_root: Path, file_path: str) -> dict:
~~~~~

~~~~~act
patch_file
packages/stitcher-test-utils/src/stitcher/test_utils/helpers.stitcher.yaml
~~~~~
~~~~~yaml.old
"get_stored_hashes": |-
  Test helper to load the composite hashes for a given source file from the
  .stitcher/signatures directory.
~~~~~
~~~~~yaml.new
"create_test_app": |-
  Factory function to create a fully assembled StitcherApp for testing purposes.
  Automatically injects Python language adapters.
"get_stored_hashes": |-
  Test helper to load the composite hashes for a given source file from the
  .stitcher/signatures directory.
~~~~~

#### Acts 3: 导出工厂函数
更新 `__init__.py`。

~~~~~act
patch_file
packages/stitcher-test-utils/src/stitcher/test_utils/__init__.py
~~~~~
~~~~~python.old
from .workspace import WorkspaceFactory
from .harness import VenvHarness
from .helpers import get_stored_hashes

__all__ = [
    "SpyBus",
    "MockNexus",
    "WorkspaceFactory",
    "VenvHarness",
    "get_stored_hashes",
]
~~~~~
~~~~~python.new
from .workspace import WorkspaceFactory
from .harness import VenvHarness
from .helpers import get_stored_hashes, create_test_app

__all__ = [
    "SpyBus",
    "MockNexus",
    "WorkspaceFactory",
    "VenvHarness",
    "get_stored_hashes",
    "create_test_app",
]
~~~~~

#### Acts 4: 执行批量重构脚本
我们将编写并运行一个脚本，该脚本会遍历所有测试文件并替换导入和调用。
该脚本通过 `find` 命令获取文件列表，然后逐个处理。

~~~~~act
run_command
~~~~~
~~~~~
cat << 'EOF' > refactor_tests.py
import os
import sys

def process_file(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Skip files that don't use StitcherApp
    if "StitcherApp" not in content:
        return

    original_content = content
    
    # Replace import
    # This naive replacement assumes "from stitcher.app import StitcherApp" is on its own line
    # or at least easily replaceable.
    content = content.replace(
        "from stitcher.app import StitcherApp", 
        "from stitcher.test_utils import create_test_app"
    )
    
    # Replace instantiation
    content = content.replace("StitcherApp(", "create_test_app(")
    
    if content != original_content:
        print(f"Refactoring {file_path}")
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)

def main():
    # Targets: "tests" and "packages/*/tests"
    targets = ["tests"]
    packages_dir = "packages"
    if os.path.exists(packages_dir):
        for pkg in os.listdir(packages_dir):
            pkg_tests = os.path.join(packages_dir, pkg, "tests")
            if os.path.exists(pkg_tests):
                targets.append(pkg_tests)

    print(f"Scanning targets: {targets}")

    for target in targets:
        for root, dirs, files in os.walk(target):
            for file in files:
                if file.endswith(".py"):
                    process_file(os.path.join(root, file))

if __name__ == "__main__":
    main()
EOF

python3 refactor_tests.py
rm refactor_tests.py
~~~~~

### 下一步建议
重构脚本执行完毕后，所有测试用例应该已经适配了新的工厂方法。接下来的关键步骤是运行整个测试套件，验证重构的正确性，并确保没有因为依赖注入引入新的回归问题。这之后，我们就可以安全地删除 `stitcher-scanner` 和 `stitcher-io` 中被废弃的代码（或者保留它们作为 Adapter 的底层实现，但不再被 Application 直接引用）。
