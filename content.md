好的，我们开始执行。

根据我们达成的共识，我将生成一个计划，将 Griffe 指定为所有命令中唯一的代码分析器，以从根本上解决签名不一致的问题。

## [WIP] refactor(app): 统一解析器为 Griffe 以解决签名不一致问题

### 用户需求
`stitcher check` 命令在使用 `stitcher pump` 或 `stitcher init` 后，会报告大量的伪“签名漂移”错误。根本原因是 `pump`/`init` 使用基于 LibCST 的解析器，而 `check` 使用 Griffe，两者对函数签名的字符串表示存在细微差异（如引号、默认参数等），导致基线哈希与当前哈希永远无法匹配。

### 评论
这是一个至关重要的架构统一性重构。将所有代码分析和签名计算的职责统一到 Griffe，可以一劳永逸地解决因解析器不一致性引发的所有问题。这不仅修复了当前的 bug，还提升了 `pump` 和 `init` 的潜在性能，并使整个系统的行为更加可预测和健壮。

### 目标
1.  修改位于 `stitcher-cli` 中的核心工厂函数 `make_app`，使其不再接收 `parser_type` 参数，并硬编码使用 `GriffePythonParser` 作为唯一的解析器。
2.  更新 `stitcher-cli` 的所有命令 (`basics.py`, `check.py`, `pump.py`) 中对 `make_app` 的调用，移除已废弃的 `parser_type` 参数。

### 基本原理
我们将指定 Griffe 为所有**读取和分析**操作的“单一事实来源”。Griffe 专为静态分析而设计，其解析结果更稳定且性能更优。同时，我们保留 LibCST (`PythonTransformer`) 用于所有**代码转换和写入**操作（如 `strip` 和 `inject`），因为它在代码修改方面表现出色。这种清晰的职责划分（Griffe for Read, LibCST for Write）创建了一个更健壮、更易于维护的架构。

### 标签
#intent/refine #flow/ready #priority/high #comp/cli #comp/application #concept/parser #scope/dx #ai/brainstorm #task/domain/architecture #task/object/parser-consistency #task/action/unification #task/state/begin

---
### Script

#### Acts 1: 统一应用工厂，强制使用 Griffe 解析器

我们将修改核心的 `make_app` 函数，移除对解析器的动态选择，并将其固定为 `GriffePythonParser`。

~~~~~act
patch_file
packages/stitcher-cli/src/stitcher/cli/factories.py
~~~~~
~~~~~python.old
def make_app(
    handler: Optional[InteractionHandler] = None,
    parser_type: str = "cst",
) -> StitcherApp:
    # Composition Root: Assemble the dependencies
    if parser_type == "griffe":
        parser = GriffePythonParser()
    else:
        parser = PythonParser()

    transformer = PythonTransformer()
~~~~~
~~~~~python.new
def make_app(
    handler: Optional[InteractionHandler] = None,
) -> StitcherApp:
    # Composition Root: Assemble the dependencies
    # UNIFIED: Always use Griffe for analysis
    parser = GriffePythonParser()

    transformer = PythonTransformer()
~~~~~

#### Acts 2: 更新 `basics.py` 中的 `make_app` 调用

移除 `basics.py` 中所有命令对 `parser_type` 参数的传递。

~~~~~act
patch_file
packages/stitcher-cli/src/stitcher/cli/commands/basics.py
~~~~~
~~~~~python.old
def generate_command():
    app_instance = make_app(parser_type="griffe")
    app_instance.run_from_config()


def init_command():
    app_instance = make_app(parser_type="cst")
    app_instance.run_init()


def strip_command():
    if not typer.confirm(bus.render_to_string(L.strip.run.confirm)):
        bus.warning(L.strip.run.aborted)
        raise typer.Abort()

    app_instance = make_app(parser_type="cst")
    app_instance.run_strip()


def inject_command():
    if not typer.confirm(bus.render_to_string(L.inject.run.confirm)):
        bus.warning(L.inject.run.aborted)
        raise typer.Abort()

    app_instance = make_app(parser_type="cst")
    app_instance.run_inject()
~~~~~
~~~~~python.new
def generate_command():
    app_instance = make_app()
    app_instance.run_from_config()


def init_command():
    app_instance = make_app()
    app_instance.run_init()


def strip_command():
    if not typer.confirm(bus.render_to_string(L.strip.run.confirm)):
        bus.warning(L.strip.run.aborted)
        raise typer.Abort()

    app_instance = make_app()
    app_instance.run_strip()


def inject_command():
    if not typer.confirm(bus.render_to_string(L.inject.run.confirm)):
        bus.warning(L.inject.run.aborted)
        raise typer.Abort()

    app_instance = make_app()
    app_instance.run_inject()
~~~~~

#### Acts 3: 更新 `check.py` 中的 `make_app` 调用

移除 `check_command` 中对 `parser_type` 参数的传递。

~~~~~act
patch_file
packages/stitcher-cli/src/stitcher/cli/commands/check.py
~~~~~
~~~~~python.old
    app_instance = make_app(handler, parser_type="griffe")
    success = app_instance.run_check(force_relink=force_relink, reconcile=reconcile)
~~~~~
~~~~~python.new
    app_instance = make_app(handler)
    success = app_instance.run_check(force_relink=force_relink, reconcile=reconcile)
~~~~~

#### Acts 4: 更新 `pump.py` 中的 `make_app` 调用

移除 `pump_command` 中对 `parser_type` 参数的传递。

~~~~~act
patch_file
packages/stitcher-cli/src/stitcher/cli/commands/pump.py
~~~~~
~~~~~python.old
    app_instance = make_app(handler, parser_type="cst")

    # 1. Run Pump
~~~~~
~~~~~python.new
    app_instance = make_app(handler)

    # 1. Run Pump
~~~~~

### 下一步建议
1.  **执行计划**: 在你确认后，请执行此计划以应用修改。
2.  **重新初始化签名**: 执行 `stitcher init`。这将使用统一的 Griffe 解析器重新生成所有 `.stitcher/signatures` 文件，创建新的、一致的基线。
3.  **验证**: 再次运行 `stitcher check`。现在应该不会再出现由解析器不一致性导致的“签名漂移”错误了。
