简要回答
好的，我们现在将“混合解析器模式”从架构设计转化为 `stitcher-cli` 的实际代码。我们将修改工厂函数以支持解析器选择，并根据命令的性质（分析型 vs 转换型）配置相应的解析器。

## [WIP] feat(cli): 实施混合解析器架构 (CST/Griffe)

### 用户需求
在 `stitcher-cli` 中实现命令驱动的解析器选择策略：
1.  **纯分析命令** (`generate`, `check`)：使用 **Griffe** 解析器，以获得更强的语义理解能力。
2.  **转换/混合命令** (`init`, `pump`, `strip`, `inject`)：保持使用 **LibCST** 解析器 (CST)，以确保代码修改的无损性和格式保留。

### 评论
**注意**：目前的 `GriffePythonParser` 实现尚处于 MVP 阶段，尚未包含完整的 Import 语句提取逻辑。这意味着 `stitcher generate` 在本次变更后生成的 `.pyi` 文件可能会暂时缺少导入语句。这是一个已知的过渡状态，我们将在此架构变更完成后，立即在下一阶段完善 Griffe 解析器的 Import 处理逻辑。

### 目标
1.  修改 `packages/stitcher-cli/src/stitcher/cli/factories.py`：扩展 `make_app` 函数，增加 `parser_type` 参数 (支持 "cst" 和 "griffe")。
2.  修改 `packages/stitcher-cli/src/stitcher/cli/commands/basics.py`：将 `generate` 切换为 Griffe，`init`, `strip`, `inject` 明确锁定为 CST。
3.  修改 `packages/stitcher-cli/src/stitcher/cli/commands/check.py`：将 `check` 切换为 Griffe。
4.  修改 `packages/stitcher-cli/src/stitcher/cli/commands/pump.py`：将 `pump` 明确锁定为 CST。

### 基本原理
通过在 Composition Root（即 CLI 命令层）进行依赖注入的配置，我们实现了策略模式，使得底层的 `StitcherApp` 依然保持对具体解析器的无感知（只依赖 `LanguageParserProtocol`），同时又能针对不同任务特性选择最优工具。

### 标签
#intent/refine #flow/ready #priority/high #comp/cli #concept/parser #scope/core #ai/instruct
#task/domain/architecture #task/object/hybrid-parser-strategy #task/action/integration #task/state/continue

---

### Script

#### Acts 1: 更新工厂函数以支持解析器选择

首先，更新 `make_app` 工厂，使其能够根据参数实例化不同的解析器。

~~~~~act
patch_file
packages/stitcher-cli/src/stitcher/cli/factories.py
~~~~~
~~~~~python.old
from stitcher.common import stitcher_operator as nexus
from stitcher.adapter.python import (
    PythonParser,
    PythonTransformer,
    PythonStubGenerator,
    PythonFingerprintStrategy,
)

from .handlers import TyperInteractionHandler
~~~~~
~~~~~python.new
from stitcher.common import stitcher_operator as nexus
from stitcher.adapter.python import (
    PythonParser,
    GriffePythonParser,
    PythonTransformer,
    PythonStubGenerator,
    PythonFingerprintStrategy,
)

from .handlers import TyperInteractionHandler
~~~~~

~~~~~act
patch_file
packages/stitcher-cli/src/stitcher/cli/factories.py
~~~~~
~~~~~python.old
def make_app(handler: Optional[InteractionHandler] = None) -> StitcherApp:
    # Composition Root: Assemble the dependencies
    parser = PythonParser()
    transformer = PythonTransformer()
    generator = PythonStubGenerator()
    strategy = PythonFingerprintStrategy()

    return StitcherApp(
        root_path=get_project_root(),
        parser=parser,
        transformer=transformer,
        stub_generator=generator,
        fingerprint_strategy=strategy,
        interaction_handler=handler,
    )
~~~~~
~~~~~python.new
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
    generator = PythonStubGenerator()
    strategy = PythonFingerprintStrategy()

    return StitcherApp(
        root_path=get_project_root(),
        parser=parser,
        transformer=transformer,
        stub_generator=generator,
        fingerprint_strategy=strategy,
        interaction_handler=handler,
    )
~~~~~

#### Acts 2: 配置基础命令 (Generate, Init, Strip, Inject)

将 `generate` 切换到 Griffe，其他保持 CST。

~~~~~act
patch_file
packages/stitcher-cli/src/stitcher/cli/commands/basics.py
~~~~~
~~~~~python.old
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
~~~~~python.new
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

#### Acts 3: 配置 Check 命令

将 `check` 切换到 Griffe，因为它主要依赖读取能力进行状态比对。

~~~~~act
patch_file
packages/stitcher-cli/src/stitcher/cli/commands/check.py
~~~~~
~~~~~python.old
    # Use factory to decide if we need an interaction handler
    handler = make_interaction_handler(
        non_interactive=non_interactive,
        auto_resolve_mode=(force_relink or reconcile),
    )

    app_instance = make_app(handler)
    success = app_instance.run_check(force_relink=force_relink, reconcile=reconcile)
    if not success:
~~~~~
~~~~~python.new
    # Use factory to decide if we need an interaction handler
    handler = make_interaction_handler(
        non_interactive=non_interactive,
        auto_resolve_mode=(force_relink or reconcile),
    )

    app_instance = make_app(handler, parser_type="griffe")
    success = app_instance.run_check(force_relink=force_relink, reconcile=reconcile)
    if not success:
~~~~~

#### Acts 4: 配置 Pump 命令

将 `pump` 明确配置为使用 CST，因为它可能涉及 `--strip` 操作，需要 CST 的支持。

~~~~~act
patch_file
packages/stitcher-cli/src/stitcher/cli/commands/pump.py
~~~~~
~~~~~python.old
    # Use factory logic
    handler = make_interaction_handler(
        non_interactive=non_interactive,
        auto_resolve_mode=(force or reconcile),
    )

    app_instance = make_app(handler)

    # 1. Run Pump
    result = app_instance.run_pump(strip=strip, force=force, reconcile=reconcile)
~~~~~
~~~~~python.new
    # Use factory logic
    handler = make_interaction_handler(
        non_interactive=non_interactive,
        auto_resolve_mode=(force or reconcile),
    )

    app_instance = make_app(handler, parser_type="cst")

    # 1. Run Pump
    result = app_instance.run_pump(strip=strip, force=force, reconcile=reconcile)
~~~~~

### 下一步建议
架构迁移已完成。现在，任何运行 `generate` 或 `check` 的操作都将使用 Griffe 解析器。

接下来的当务之急是**完善 Griffe 解析器的能力**，特别是实现 `imports` 语句的提取和映射。如果没有这个，生成的 `.pyi` 文件将无法正确引用导入的类型，导致 stub 文件不可用。我们应该立即创建一个修复计划来解决这个问题。
