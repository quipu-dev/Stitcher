好的。既然分析和测试证明 `Planner` 已经正确处理了跨包迁移，那行过时的 `TODO` 和相关的犹豫性注释确实应当移除。

我将生成一个计划来清理 `move_file.py` 中的这些注释，并将其替换为对当前正确机制的简要说明。

## [WIP] refactor: 移除 move_file.py 中关于跨包迁移的过时 TODO

### 用户需求

删除 `packages/stitcher-refactor/src/stitcher/refactor/operations/move_file.py` 中关于跨包 lock 文件迁移的冗余和误导性注释及 `TODO`。

### 评论

这些注释是在开发早期对 `Planner` 的处理能力不确定时留下的。经过验证，`Planner` 已经能够通过独立解析路径所属包的方式，优雅地处理跨包的指纹数据迁移。移除这些陈旧信息不仅能使代码库更整洁，还能避免其他开发者在阅读代码时产生不必要的疑虑。

### 目标

1.  定位到 `packages/stitcher-refactor/src/stitcher/refactor/operations/move_file.py` 中的相关注释块。
2.  移除包含 `TODO: Handle Cross-Package Lock Migration.` 的整个说明段落。
3.  替换为一行简洁的说明，确认 `Planner` 负责处理跨包迁移。

### 基本原理

根据 **高保真工程公理 (HFEA)** 中的“架构不可腐蚀性”原则，任何形式的误导性信息或已经解决但仍然存在的“虚假”缺陷都被视为架构异味。及时铲除这些异味是维护系统“本体论正确性”的必要步骤。

### 标签

#intent/refine #flow/ready #priority/low #comp/refactor #concept/state #scope/dx #ai/instruct #task/domain/refactor #task/object/move-file-op #task/action/refactor #task/state/begin

---

### Script

#### Acts 1: 清理 `move_file.py` 中的冗余注释

我们将移除 `move_file.py` 中关于跨包迁移的过时说明，因为它描述的限制早已被 `Planner` 解决。

~~~~~act
patch_file
packages/stitcher-refactor/src/stitcher/refactor/operations/move_file.py
~~~~~
~~~~~python.old
        # 3. Declare Lock Update Intent (Mass update SURIs)
        # Note: We need to update SURIs in the OLD package's lock file.
        # If the file moves across packages, we technically need to move entries from one lock to another.
        # LockPathUpdateIntent handles updating the path prefix.
        # But if package_root changes, we need to handle migration?
        # For simplicity in this phase, we assume LockPathUpdateIntent updates paths within the same lock context
        # OR Planner is smart enough to handle cross-package moves if we provide enough info.
        # Current simplified strategy: Update SURIs in the source package's lock.
        # If it moves to a new package, the entries in the old lock will point to a path outside the old package root.
        # This is valid for SURI (workspace relative), but 'stitcher.lock' usually scopes to the package.
        # TODO: Handle Cross-Package Lock Migration.
        # For now, we just emit the intent on the source package.

        owning_package = ctx.workspace.find_owning_package(src_path)
~~~~~
~~~~~python.new
        # 3. Declare Lock Update Intent (Mass update SURIs)
        # Planner is responsible for detecting cross-package moves and migrating
        # fingerprints between stitcher.lock files if necessary.

        owning_package = ctx.workspace.find_owning_package(src_path)
~~~~~

### 下一步建议

清理工作已完成。目前我们已经：
1.  完成了核心组件的依赖注入。
2.  增强了 Workspace 根目录判定的确定性。
3.  通过新的集成测试验证了跨包重构的健壮性。

建议下一步回顾 **“3. 强化 CST Visitor”**。目前的 CST 访问器对于 Python 的赋值语句解析依然非常原始（仅支持单变量赋值），这限制了索引器处理解包赋值（Unpacking Assignment）的能力。我们可以先为该功能编写一个失败的测试用例。
