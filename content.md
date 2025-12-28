## [WIP] fix: 修复配置遗漏并优化硬编码字符串

### 用户需求
1.  **核心修复**: 用户发现 `packages/pyneedle-runtime` 目录下的文件（包括用户示例中的测试文件所在的包）未被 `stitcher` 处理。
2.  **代码优化**: 用户指出 `main.py` 中 `--verbose` 选项的帮助文本存在硬编码，建议使用 `L` 对象进行国际化管理。

### 评论
经过对 `pyproject.toml` 和 Debug 日志的分析，根本原因已确认为**配置遗漏**。`tool.stitcher.targets.needle` 的 `scan_paths` 列表中缺少了核心包 `packages/pyneedle-runtime/src`。这将导致该包下的所有源文件（以及用户可能尝试包含的测试文件）都被完全忽略。

此外，采纳用户关于消除硬编码字符串的建议，符合我们“国际化优先”的架构原则。

### 目标
1.  **国际化**: 在 `option.json` 资产文件中添加 `verbose` 选项的说明，并在 `main.py` 中引用。
2.  **配置修复**: 将 `packages/pyneedle-runtime/src` 添加到 `pyproject.toml` 的扫描路径中。

### 基本原理
1.  **配置即真理**: `stitcher` 的行为完全由配置驱动。遗漏路径会导致不可见的静默失败。通过补充配置，我们将恢复对 `pyneedle-runtime` 的支持。
2.  **L 对象**: 统一使用 `nexus` 获取 UI 文本，确保 CLI 的多语言支持一致性。

### 标签
#intent/fix #flow/ready #priority/high #comp/cli #comp/build #scope/core #ai/instruct #task/domain/config #task/object/pyproject-toml #task/action/update #task/state/continue

---

### Script

#### Acts 1: 添加 Verbose 选项的国际化资源
在 `stitcher-cli` 的资产文件中添加 `verbose` 键。

~~~~~act
patch_file
packages/stitcher-cli/src/stitcher/cli/assets/needle/en/cli/option.json
~~~~~
~~~~~json.old
  "update_signatures": {
    "help": "Accept signature changes and update the stored fingerprints."
  }
}
~~~~~
~~~~~json.new
  "update_signatures": {
    "help": "Accept signature changes and update the stored fingerprints."
  },
  "verbose": {
    "help": "Enable debug logging."
  }
}
~~~~~

~~~~~act
patch_file
packages/stitcher-cli/src/stitcher/cli/assets/needle/zh/cli/option.json
~~~~~
~~~~~json.old
  "update_signatures": {
    "help": "接受签名变更并更新存储的指纹。"
  }
}
~~~~~
~~~~~json.new
  "update_signatures": {
    "help": "接受签名变更并更新存储的指纹。"
  },
  "verbose": {
    "help": "启用调试日志。"
  }
}
~~~~~

#### Acts 2: 替换 main.py 中的硬编码字符串
修改 CLI 入口，使用 `L.cli.option.verbose.help`。

~~~~~act
patch_file
packages/stitcher-cli/src/stitcher/cli/main.py
~~~~~
~~~~~python.old
@app.callback()
def main(
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Enable debug logging."
    ),
):
    # The CLI is the composition root. It decides *which* renderer to use.
~~~~~
~~~~~python.new
@app.callback()
def main(
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help=nexus.get(L.cli.option.verbose.help)
    ),
):
    # The CLI is the composition root. It decides *which* renderer to use.
~~~~~

#### Acts 3: 修复 pyproject.toml 配置
将遗漏的 `packages/pyneedle-runtime/src` 添加到 `needle` 目标的扫描路径中。

> **注意**: 默认配置仅扫描 `src` 目录。如果你希望 `stitcher` 处理 `tests` 目录下的文件（如你提到的 `test_fs_loader_fqn.py`），你需要显式地将测试目录也添加到 `scan_paths` 中（例如 `packages/pyneedle-runtime/tests`）。但在标准工作流中，我们通常只为源代码生成文档和存根。下面的修复首先确保核心源代码被包含。

~~~~~act
patch_file
pyproject.toml
~~~~~
~~~~~toml.old
[tool.stitcher.targets.needle]
scan_paths = [
    "packages/pyneedle-spec/src",
    "packages/pyneedle-pointer/src",
    "packages/pyneedle-nexus/src",
    "packages/pyneedle/src",
]
stub_package = "packages/needle-stubs"
~~~~~
~~~~~toml.new
[tool.stitcher.targets.needle]
scan_paths = [
    "packages/pyneedle-spec/src",
    "packages/pyneedle-pointer/src",
    "packages/pyneedle-nexus/src",
    "packages/pyneedle-runtime/src",
    "packages/pyneedle/src",
]
stub_package = "packages/needle-stubs"
~~~~~
