好的，这是一个非常合理且重要的补充。

引入一个明确的 `--non-interactive` 标志是 CLI 设计的最佳实践。它消除了行为的模糊性，让用户（尤其是编写脚本的用户）能够显式地控制程序的行为，而不是依赖于对 TTY 环境的隐式检测。

我将为你生成一个计划来实现这个功能。

## [WIP] feat: 为 `check` 命令添加 `--non-interactive` 标志

### 用户需求
为 `stitcher check` 命令添加一个 `--non-interactive` 标志。当使用此标志时，即使在交互式终端（TTY）中，命令也应采取非交互式行为，即在遇到需要决策的冲突时直接报错退出，而不是启动交互式向导。

### 评论
这是一个出色的可用性改进。它将先前隐式的行为（依赖于 TTY 和其他标志）变为显式的用户选择，这对于自动化脚本和要求行为确定性的高级用户来说至关重要。这使得 `check` 命令的行为更加健壮和可预测。

### 目标
1.  在 `stitcher.cli.main` 的 `check` 命令定义中，添加一个新的 `typer.Option` 用于 `--non-interactive`。
2.  更新 `check` 命令的逻辑，将此标志作为启动交互式处理器的首要否决条件。
3.  更新相关的帮助文档（英文和中文），以反映新选项并阐明 `force-relink` 和 `reconcile` 标志主要用于非交互模式。
4.  更新 `main.stitcher.yaml` 中的内部文档。

### 基本原理
我们将在 `check` 命令的入口处修改决策逻辑。启动 `TyperInteractionHandler` 的条件将从 `isatty()` 变为 `isatty() and not non_interactive`。这确保了用户可以通过一个简单的标志完全控制交互行为，而无需改变任何核心应用层的代码，完美体现了表现层与应用层解耦的优势。

### 标签
#intent/build #flow/ready #priority/medium #comp/cli #scope/ux #scope/dx #ai/instruct #task/domain/cli #task/object/interactive-check #task/action/implementation #task/state/continue

---

### Script

#### Acts 1: 更新 `check` 命令以包含新标志和逻辑

我们将修改 `packages/stitcher-cli/src/stitcher/cli/main.py` 中的 `check` 函数。

~~~~~act
patch_file
packages/stitcher-cli/src/stitcher/cli/main.py
~~~~~
~~~~~python.old
@app.command(help=nexus.get(L.cli.command.check.help))
def check(
    force_relink: bool = typer.Option(
        False,
        "--force-relink",
        help="[Non-interactive] For 'Signature Drift' errors, forces relinking.",
    ),
    reconcile: bool = typer.Option(
        False,
        "--reconcile",
        help="[Non-interactive] For 'Co-evolution' errors, accepts both changes.",
    ),
):
    if force_relink and reconcile:
        bus.error("Cannot use --force-relink and --reconcile simultaneously.")
        raise typer.Exit(code=1)

    project_root = Path.cwd()
    
    handler = None
    if sys.stdin.isatty() and not force_relink and not reconcile:
        handler = TyperInteractionHandler()

    app_instance = StitcherApp(root_path=project_root, interaction_handler=handler)
    success = app_instance.run_check(force_relink=force_relink, reconcile=reconcile)
    if not success:
        raise typer.Exit(code=1)
~~~~~
~~~~~python.new
@app.command(help=nexus.get(L.cli.command.check.help))
def check(
    force_relink: bool = typer.Option(
        False,
        "--force-relink",
        help="[Non-interactive] For 'Signature Drift' errors, forces relinking.",
    ),
    reconcile: bool = typer.Option(
        False,
        "--reconcile",
        help="[Non-interactive] For 'Co-evolution' errors, accepts both changes.",
    ),
    non_interactive: bool = typer.Option(
        False,
        "--non-interactive",
        help="Force non-interactive mode, failing on unresolved conflicts.",
    ),
):
    if force_relink and reconcile:
        bus.error("Cannot use --force-relink and --reconcile simultaneously.")
        raise typer.Exit(code=1)

    project_root = Path.cwd()
    
    handler = None
    # Interactive mode is the default in a TTY, unless explicitly disabled.
    if sys.stdin.isatty() and not non_interactive and not force_relink and not reconcile:
        handler = TyperInteractionHandler()

    app_instance = StitcherApp(root_path=project_root, interaction_handler=handler)
    success = app_instance.run_check(force_relink=force_relink, reconcile=reconcile)
    if not success:
        raise typer.Exit(code=1)
~~~~~

#### Acts 2: 更新 CLI 的帮助文档

##### 2.1: 英文帮助文档

~~~~~act
patch_file
packages/stitcher-cli/src/stitcher/cli/assets/needle/en/commands.json
~~~~~
~~~~~json.old
    "cli.option.strip.help": "Remove docstrings from source code after hydration.",
    "cli.option.force.help": "Code-first: Overwrite YAML content if it differs from source code.",
    "cli.option.reconcile.help": "YAML-first: Ignore source docstrings if they conflict with existing YAML.",
    "cli.option.update_signatures.help": "Accept signature changes and update the stored fingerprints."
}
~~~~~
~~~~~json.new
    "cli.option.strip.help": "Remove docstrings from source code after hydration.",
    "cli.option.force.help": "Code-first: Overwrite YAML content if it differs from source code.",
    "cli.option.reconcile.help": "YAML-first: Ignore source docstrings if they conflict with existing YAML.",
    "cli.option.update_signatures.help": "Accept signature changes and update the stored fingerprints.",
    "cli.option.non_interactive.help": "Force non-interactive mode, failing on unresolved conflicts."
}
~~~~~

##### 2.2: 中文帮助文档

~~~~~act
patch_file
packages/stitcher-cli/src/stitcher/cli/assets/needle/zh/commands.json
~~~~~
~~~~~json.old
    "cli.option.strip.help": "在补水后立即从源码中移除文档字符串。",
    "cli.option.force.help": "代码优先：如果内容不一致，覆盖 YAML 内容。",
    "cli.option.reconcile.help": "YAML 优先：忽略与现有 YAML 冲突的源码文档。",
    "cli.option.update_signatures.help": "接受签名变更并更新存储的指纹。"
}
~~~~~
~~~~~json.new
    "cli.option.strip.help": "在补水后立即从源码中移除文档字符串。",
    "cli.option.force.help": "代码优先：如果内容不一致，覆盖 YAML 内容。",
    "cli.option.reconcile.help": "YAML 优先：忽略与现有 YAML 冲突的源码文档。",
    "cli.option.update_signatures.help": "接受签名变更并更新存储的指纹。",
    "cli.option.non_interactive.help": "强制使用非交互模式，在遇到无法解决的冲突时失败。"
}
~~~~~

#### Acts 3: 更新内部文档 (`main.stitcher.yaml`)

~~~~~act
patch_file
packages/stitcher-cli/src/stitcher/cli/main.stitcher.yaml
~~~~~
~~~~~yaml.old
"check": |-
  Verify consistency between code and docs.

  Args:
    update_signatures: Accept and update signature changes in the stored fingerprints.
~~~~~
~~~~~yaml.new
"check": |-
  Verify consistency between code and docs.

  Args:
    force_relink: [Non-interactive] For 'Signature Drift' errors, forces relinking.
    reconcile: [Non-interactive] For 'Co-evolution' errors, accepts both changes.
    non_interactive: Force non-interactive mode, failing on unresolved conflicts.
~~~~~

### 下一步建议
我们已经成功地为 `check` 命令添加了 `--non-interactive` 标志，并更新了所有相关文档。这标志着“交互式引导”这个宏大功能的开发工作已全部完成。

现在，我建议创建一个 `[COMMIT]` 计划，将自 `#task/state/begin` 以来的所有相关修改（领域模型、应用层重构、CLI 实现及修复）作为一个完整的、原子性的功能单元进行提交。
