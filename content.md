这确实是一个典型的**抽象泄漏**和**命名冲突**导致的 Bug。

在 `main.py` 的猴子补丁逻辑中：
```python
def render_to_string_patch(self, msg_id, **kwargs):
    template = L.needle.get(msg_id)  # <--- 错误发生在这里
    return template.format(**kwargs)
```

1.  **冲突原因**: `L` 是 `SemanticPointer` 的根对象。根据它的设计，任何属性访问（如 `.needle` 或 `.get`）都会返回一个新的 `SemanticPointer` 实例。因此 `L.needle.get` 返回的是一个路径为 `"needle.get"` 的指针对象，而不是调用方法。
2.  **冗余逻辑**: `stitcher-common` 中的 `MessageBus` 其实已经正确实现了 `render_to_string` 方法，且它内部正确导入并使用了 `needle` 运行时单例。我们在 `main.py` 中尝试重新实现它，不仅写错了，而且完全没必要。

删除 `main.py` 中冗余且错误的猴子补丁。`bus.render_to_string` 将自动回退到其在 `stitcher-common` 中的原生正确实现。

---

## [WIP] fix: 修复 MessageBus 渲染补丁中的抽象泄漏 Bug

### 错误分析
在 `stitcher-cli` 的 `main.py` 中，错误地通过 `SemanticPointer` (L) 去尝试调用 `needle` 运行时的 `get` 方法。由于 `L` 的属性访问总是返回指针，导致 `L.needle.get` 变成了一个不可调用的对象，触发了 `TypeError`。

### 用户需求
修复 `stitcher strip` 和 `stitcher eject` 命令在触发确认弹窗时导致的程序崩溃。

### 评论
这个补丁是早期版本的遗留物。既然 `MessageBus` 已经在底层通过 `needle` 运行时正确实现了 `render_to_string`，我们应该遵循“唯一事实来源”原则，移除 CLI 层的重复实现。

### 目标
1.  从 `packages/stitcher-cli/src/stitcher/cli/main.py` 中移除 `render_to_string_patch` 及其关联的赋值逻辑。

### 基本原理
直接利用 `stitcher-common` 中 `MessageBus` 类内置的 `render_to_string` 方法，它已经包含了正确的 `needle.get(msg_id)` 调用和异常处理。

### 标签
#intent/fix #flow/ready #priority/critical #comp/cli #concept/parser #scope/ux #ai/instruct #task/domain/cli #task/object/message-rendering #task/action/bug-fix #task/state/begin

---

### Script

#### Acts 1: 移除错误的补丁代码

~~~~~act
patch_file
packages/stitcher-cli/src/stitcher/cli/main.py
~~~~~
~~~~~python.old
    project_root = Path.cwd()
    app_instance = StitcherApp(root_path=project_root)
    success = app_instance.run_hydrate(strip=strip, force=force, reconcile=reconcile)
    if not success:
        raise typer.Exit(code=1)


# Helper needed for typer.confirm, as it prints directly
# We need to render message to a string first
def render_to_string_patch(self, msg_id, **kwargs):
    template = L.needle.get(msg_id)
    return template.format(**kwargs)


bus.render_to_string = render_to_string_patch.__get__(bus)


if __name__ == "__main__":
~~~~~
~~~~~python.new
    project_root = Path.cwd()
    app_instance = StitcherApp(root_path=project_root)
    success = app_instance.run_hydrate(strip=strip, force=force, reconcile=reconcile)
    if not success:
        raise typer.Exit(code=1)


if __name__ == "__main__":
~~~~~

### 下一步建议
- **执行验证**: 再次运行 `stitcher strip` 确保确认弹窗能正常显示文案。
- **全局检查**: 检查是否有其他地方误用了 `L` 对象来尝试访问运行时方法。记住：`L` 仅用于构建身份指针，`needle` 才是用于获取内容的运行时。
