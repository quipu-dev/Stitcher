好的，我们来完成应用层的迁移。这标志着 `stitcher-needle` 的核心思想正式在业务代码中落地。

我将生成一个计划，使用 `patch_file` 精确地替换所有硬编码的消息 ID，并添加必要的 `L` 对象导入。

## [WIP] feat: 迁移应用与 CLI 层至 SemanticPointer (L)

### 用户需求
根据 `rg` 的输出结果，将 `stitcher-application` 和 `stitcher-cli` 中所有对 `bus` 的调用，从使用硬编码的字符串消息 ID，迁移为使用 `L` 语义指针。

### 评论
这是一个里程碑式的重构。虽然代码改动量不大，但它在概念上完成了从“基于字符串的脆弱约定”到“基于对象的类型安全引用”的转变。这将极大地提升开发者体验（DX），并为未来基于 `L` 对象的静态分析和自动补全打下基础。

### 目标
1.  在 `stitcher.cli.main` 中，将 `bus.info("...")` 调用替换为 `bus.info(L....)`。
2.  在 `stitcher.app.core` 中，将所有 `bus.error`, `bus.success`, `bus.warning` 调用替换为使用 `L` 对象。
3.  在上述两个文件中添加 `from stitcher.common import L` 的导入语句。

### 基本原理
我们将使用多个精确的 `patch_file` 操作来执行替换，确保每次修改都具有足够的上下文，避免误操作。为每个文件添加导入是完成迁移的必要步骤，使其能够正确解析 `L` 对象。

### 标签
#intent/refine #flow/ready #priority/high #comp/cli #comp/application #scope/core #scope/dx #ai/instruct #task/domain/runtime #task/object/needle-kernel #task/action/implementation #task/state/continue

---
### Script

#### Acts 1: 更新 `stitcher-cli`

首先，我们修改 CLI 入口文件，添加导入并替换消息 ID。

~~~~~act
patch_file
packages/stitcher-cli/src/stitcher/cli/main.py
~~~~~
~~~~~python.old
from pathlib import Path
import typer

from stitcher.app import StitcherApp
from stitcher.common import bus
from .rendering import CliRenderer
~~~~~
~~~~~python.new
from pathlib import Path
import typer

from stitcher.app import StitcherApp
from stitcher.common import L, bus
from .rendering import CliRenderer
~~~~~

~~~~~act
patch_file
packages/stitcher-cli/src/stitcher/cli/main.py
~~~~~
~~~~~python.old
@app.command()
def init():
    """Initialize Stitcher in the current project."""
    bus.info("cli.command.not_implemented", command="init")

@app.command()
def check():
    """Verify consistency between code and docs."""
    bus.info("cli.command.not_implemented", command="check")
~~~~~
~~~~~python.new
@app.command()
def init():
    """Initialize Stitcher in the current project."""
    bus.info(L.cli.command.not_implemented, command="init")

@app.command()
def check():
    """Verify consistency between code and docs."""
    bus.info(L.cli.command.not_implemented, command="check")
~~~~~

#### Acts 2: 更新 `stitcher-application`

接着，我们对应用核心逻辑进行相同的迁移操作。

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/core.py
~~~~~
~~~~~python.old
from stitcher.io import StubGenerator
from stitcher.spec import ModuleDef, FunctionDef
from stitcher.common import bus
from stitcher.config import load_config_from_path
~~~~~
~~~~~python.new
from stitcher.io import StubGenerator
from stitcher.spec import ModuleDef, FunctionDef
from stitcher.common import L, bus
from stitcher.config import load_config_from_path
~~~~~

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/core.py
~~~~~
~~~~~python.old
                module_def = parse_source_code(content, file_path=relative_path)
                modules.append(module_def)
            except Exception as e:
                bus.error("error.generic", error=e)
        return modules
~~~~~
~~~~~python.new
                module_def = parse_source_code(content, file_path=relative_path)
                modules.append(module_def)
            except Exception as e:
                bus.error(L.error.generic, error=e)
        return modules
~~~~~

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/core.py
~~~~~
~~~~~python.old
                virtual_modules[func_path].functions.append(func_def)

            except InspectionError as e:
                bus.error("error.plugin.inspection", error=e)

        return list(virtual_modules.values())
~~~~~
~~~~~python.new
                virtual_modules[func_path].functions.append(func_def)

            except InspectionError as e:
                bus.error(L.error.plugin.inspection, error=e)

        return list(virtual_modules.values())
~~~~~

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/core.py
~~~~~
~~~~~python.old
            output_path.write_text(pyi_content, encoding="utf-8")
            
            relative_path = output_path.relative_to(self.root_path)
            bus.success("generate.file.success", path=relative_path)
            generated_files.append(output_path)
        return generated_files
~~~~~
~~~~~python.new
            output_path.write_text(pyi_content, encoding="utf-8")
            
            relative_path = output_path.relative_to(self.root_path)
            bus.success(L.generate.file.success, path=relative_path)
            generated_files.append(output_path)
        return generated_files
~~~~~

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/core.py
~~~~~
~~~~~python.old
        all_modules = source_modules + plugin_modules
        if not all_modules:
            bus.warning("warning.no_files_or_plugins_found")
            return []

        generated_files = self._generate_stubs(all_modules)
        
        if generated_files:
            bus.success("generate.run.complete", count=len(generated_files))

        return generated_files
~~~~~
~~~~~python.new
        all_modules = source_modules + plugin_modules
        if not all_modules:
            bus.warning(L.warning.no_files_or_plugins_found)
            return []

        generated_files = self._generate_stubs(all_modules)
        
        if generated_files:
            bus.success(L.generate.run.complete, count=len(generated_files))

        return generated_files
~~~~~
