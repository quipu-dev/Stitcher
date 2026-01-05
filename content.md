您完全正确。我对此表示歉意。

我之前的实现是错误的，存在两个严重问题：
1.  **错误的 `bus` 调用**：我使用了 `bus.debug(L.debug.log, msg="...")` 这种形式，这是无效的。`bus` 系统要求为每个独特的、需要国际化的消息创建一个专门的语义指针，并使用与该指针模板中定义的占位符相匹配的关键字参数。我试图用一个通用的指针和任意的关键字参数，这违反了系统的核心设计原则。
2.  **非结构化日志**：直接在代码中嵌入 f-string 形式的日志内容，破坏了国际化能力，并且使得日志消息本身难以管理和维护。

感谢您的指正。我将立即纠正这个错误，并按照您的要求，实现一个结构化的、符合国际化标准的日志系统。

## [WIP] fix(cli): 为 refactor 命令实现结构化和国际化的调试日志

### 错误分析
我上次提交的计划中，对 `refactor.py` 的修改是错误的。它没有遵循 `pyneedle` 和 `MessageBus` 的既定协议，即：
1.  每一个需要被 `bus` 发送的消息，都应该有一个唯一的、定义在 `JSON` 资源文件中的语义 ID。
2.  调用 `bus` 的方法时，必须使用与消息模板中占位符完全同名的关键字参数来传递数据。

我违反了这两条规则，导致 `bus` 无法正确解析和渲染日志消息，从而输出了无意义的 `debug.log` 字符串。

### 用户需求
用户要求我删除之前错误的日志代码，并用一种正确的方式来替换它：
1.  在 `needle` 资源文件中定义新的、结构化的日志消息 ID。
2.  确保这些 ID 同时存在于英文和中文的资源文件中，以实现国际化。
3.  修改 `refactor.py` 代码，使用这些新的语义指针和正确的关键字参数来调用 `bus.debug`。

### 评论
这是一个至关重要的纠正。它不仅修复了当前的 bug，更重要的是，它强化了项目对于代码质量、可维护性和国际化的承诺。将调试信息也纳入结构化、可翻译的框架中，是构建专业级 CLI 工具的正确做法。

### 目标
1.  在 `en/debug/log.json` 中为 `refactor` 命令添加一组专用的、带占位符的调试日志消息。
2.  在 `zh/debug/log.json` 中添加这些消息的中文翻译。
3.  使用 `patch_file` 更新 `refactor.py`，使其调用这些新创建的、结构化的日志消息。

### 基本原理
我们将首先扩展 `pyneedle` 的词汇表，为 `refactor` 命令的每个调试步骤定义一个清晰的语义ID。然后，我们将用这些新的、精确的 `L` 指针替换掉 `refactor.py` 中之前错误的 `bus.debug` 调用。这将确保日志消息能够被正确地查找、格式化、国际化，并最终由 `CliRenderer` 在 verbose 模式下正确显示。

### 标签
#intent/fix #flow/ready #priority/critical #comp/cli #comp/common #concept/ui #scope/dx #ai/refine #task/domain/core-abstractions #task/object/message-bus #task/action/rename #task/state/continue

---

### Script

#### Acts 1: 定义英文版调试日志
我们将在 `en/debug/log.json` 文件中追加 `refactor` 命令专用的日志条目。

~~~~~act
patch_file
packages/stitcher-common/src/stitcher/common/assets/needle/en/debug/log.json
~~~~~
~~~~~json.old
{
  "msg": "🔍 {msg}",
  "scan_path": "🔍 Scanning path: {path}",
  "file_found": "🔍 Found file: {path}",
  "file_ignored": "🔍 Ignored file: {path} ({reason})"
}
~~~~~
~~~~~json.new
{
  "msg": "🔍 {msg}",
  "scan_path": "🔍 Scanning path: {path}",
  "file_found": "🔍 Found file: {path}",
  "file_ignored": "🔍 Ignored file: {path} ({reason})",
  "refactor_workspace_paths": "🔍 Workspace search paths: {paths}",
  "refactor_discovered_packages": "🔍 Discovered packages to load: {packages}",
  "refactor_loading_package": "🔍 Loading package '{package}' into graph...",
  "refactor_symbol_usage_count": "🔍 Found {count} usages for '{fqn}'",
  "refactor_planned_ops_count": "🔍 Planner generated {count} file operations."
}
~~~~~

#### Acts 2: 定义中文版调试日志
相应地，我们在 `zh/debug/log.json` 文件中添加中文翻译。

~~~~~act
patch_file
packages/stitcher-common/src/stitcher/common/assets/needle/zh/debug/log.json
~~~~~
~~~~~json.old
{
  "msg": "🔍 {msg}",
  "scan_path": "🔍 扫描路径: {path}",
  "file_found": "🔍 发现文件: {path}",
  "file_ignored": "🔍 忽略文件: {path} ({reason})"
}
~~~~~
~~~~~json.new
{
  "msg": "🔍 {msg}",
  "scan_path": "🔍 扫描路径: {path}",
  "file_found": "🔍 发现文件: {path}",
  "file_ignored": "🔍 忽略文件: {path} ({reason})",
  "refactor_workspace_paths": "🔍 工作区搜索路径: {paths}",
  "refactor_discovered_packages": "🔍 发现待加载的包: {packages}",
  "refactor_loading_package": "🔍 正在加载 '{package}' 到语义图谱...",
  "refactor_symbol_usage_count": "🔍 发现 '{fqn}' 的 {count} 处用法",
  "refactor_planned_ops_count": "🔍 计划器生成了 {count} 个文件操作。"
}
~~~~~

#### Acts 3: 更新 `refactor` 命令以使用新的日志指针
现在，我们修正 `refactor.py` 中的代码，让它使用我们刚刚创建的结构化日志。

~~~~~act
patch_file
packages/stitcher-cli/src/stitcher/cli/commands/refactor.py
~~~~~
~~~~~python.old
    try:
        # 1. Bootstrap services
        bus.info(L.refactor.run.loading_graph)
        workspace = Workspace(root_path)
        sidecar_manager = SidecarManager(root_path)
        graph = SemanticGraph(workspace)

        # Load all packages discovered by the workspace
        for pkg_name in workspace.import_to_source_dirs.keys():
            graph.load(pkg_name)

        ctx = RefactorContext(
            workspace=workspace, graph=graph, sidecar_manager=sidecar_manager
        )

        # 2. Load and plan the migration
        bus.info(L.refactor.run.planning)
        loader = MigrationLoader()
        spec = loader.load_from_path(migration_script)

        planner = Planner()
        file_ops = planner.plan(spec, ctx)

        if not file_ops:
            bus.success(L.refactor.run.no_ops)
            return
~~~~~
~~~~~python.new
    try:
        # 1. Bootstrap services
        bus.info(L.refactor.run.loading_graph)
        workspace = Workspace(root_path)
        bus.debug(
            L.debug.log.refactor_workspace_paths, paths=workspace.get_search_paths()
        )
        sidecar_manager = SidecarManager(root_path)
        graph = SemanticGraph(workspace)

        # Load all packages discovered by the workspace
        pkg_names = list(workspace.import_to_source_dirs.keys())
        bus.debug(L.debug.log.refactor_discovered_packages, packages=pkg_names)
        for pkg_name in pkg_names:
            bus.debug(L.debug.log.refactor_loading_package, package=pkg_name)
            graph.load(pkg_name)

        ctx = RefactorContext(
            workspace=workspace, graph=graph, sidecar_manager=sidecar_manager
        )

        # 2. Load and plan the migration
        bus.info(L.refactor.run.planning)
        loader = MigrationLoader()
        spec = loader.load_from_path(migration_script)

        # --- DEBUG ---
        for op in spec.operations:
            if op.__class__.__name__ == "RenameSymbolOperation":
                target_fqn = op.old_fqn
                usages = graph.registry.get_usages(target_fqn)
                bus.debug(
                    L.debug.log.refactor_symbol_usage_count,
                    count=len(usages),
                    fqn=target_fqn,
                )
        # --- END DEBUG ---

        planner = Planner()
        file_ops = planner.plan(spec, ctx)
        bus.debug(
            L.debug.log.refactor_planned_ops_count, count=len(file_ops)
        )

        if not file_ops:
            bus.success(L.refactor.run.no_ops)
            return
~~~~~

### 下一步建议
日志系统现已正确实现。请再次运行带有 `-v` 标志的命令：

```bash
stitcher -v refactor apply 001_rename_message_bus.py --yes
```

现在我们应该能看到结构化的、有意义的调试输出了。请将结果反馈给我，以便我们继续诊断。
