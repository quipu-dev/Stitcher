简要回答
好的，我明白了。Pyright 报告的 "possibly unbound" 错误是由于 `_apply_resolutions` 方法中的缩进逻辑错误导致的：后续的 `if action == ...` 块错误地跳出了 `if fqn in new_hashes:` 的作用域，导致在变量未定义的路径上尝试访问它们。

通过修正缩进，将逻辑块正确嵌套，这些 "unbound" 错误将自然解决。同时，对于 `str | None` 赋值错误，我也将通过显式的 `str()` 转换来解决。

## [WIP] fix: 修复 core.py 中的缩进逻辑错误与类型问题

### 错误分析
1.  **缩进错误 (Indentation Error)**: `_apply_resolutions` 方法中，处理 `ResolutionAction` 的逻辑块（`if action == ...`）意外地脱离了 `if fqn in new_hashes:` 的保护范围。这导致 `current_code_hash` 和 `fp` 在尚未赋值的情况下可能被访问。
2.  **类型不匹配**: Pyright 认为 `current_yaml_map[fqn]` 可能返回 `None`（尽管逻辑上似乎保证了是 `str`）。为了满足静态检查，显式转换为 `str` 是最安全的做法。

### 用户需求
修复 `stitcher-application` 中的逻辑错误和类型检查失败。

### 评论
缩进错误在 Python 中是致命的逻辑错误，Pyright 在这里起到了很好的防错作用。

### 目标
1.  调整 `_apply_resolutions` 中的代码块缩进。
2.  为 `current_yaml_map` 的值添加 `str()` 转换。

### 基本原理
- **Scope Safety**: 变量的使用必须在其定义的作用域内。
- **Type Safety**: 显式转换消除类型歧义。

### 标签
#intent/fix #flow/ready #priority/high
#comp/runtime #task/domain/testing #task/object/type-safety #task/action/fix-indentation
#task/state/continue

---

### Script

#### Acts 1: 修复缩进和类型转换
我们将重写 `_apply_resolutions` 中的循环体，修正缩进并添加类型转换。

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/core.py
~~~~~
~~~~~python.old
            for fqn, action in fqn_actions:
                if fqn in new_hashes:
                    fp = new_hashes[fqn]
                    current_fp = computed_fingerprints.get(fqn, Fingerprint())
                    current_code_hash = current_fp.get("current_code_structure_hash")

                if action == ResolutionAction.RELINK:
                    if current_code_hash:
                        fp["baseline_code_structure_hash"] = str(current_code_hash)
                elif action == ResolutionAction.RECONCILE:
                    if current_code_hash:
                        fp["baseline_code_structure_hash"] = str(current_code_hash)
                        if fqn in current_yaml_map:
                            fp["baseline_yaml_content_hash"] = current_yaml_map[fqn]
~~~~~
~~~~~python.new
            for fqn, action in fqn_actions:
                if fqn in new_hashes:
                    fp = new_hashes[fqn]
                    current_fp = computed_fingerprints.get(fqn, Fingerprint())
                    current_code_hash = current_fp.get("current_code_structure_hash")

                    if action == ResolutionAction.RELINK:
                        if current_code_hash:
                            fp["baseline_code_structure_hash"] = str(current_code_hash)
                    elif action == ResolutionAction.RECONCILE:
                        if current_code_hash:
                            fp["baseline_code_structure_hash"] = str(current_code_hash)
                        if fqn in current_yaml_map:
                            fp["baseline_yaml_content_hash"] = str(
                                current_yaml_map[fqn]
                            )
~~~~~

### 下一步建议
运行 `pyright`，应该能看到所有错误都已清零。之后可以运行完整的测试套件确保没有引入回归问题。
