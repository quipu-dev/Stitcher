执行。简要回答

通过修改 `SidecarTransformer` 以支持 `stitcher.lock` 的嵌套结构并规范化路径比较逻辑，修复了 SURI 在重构操作中未被更新的问题。

## [WIP] fix: 支持 stitcher.lock 结构并在 SURI 转换时规范化路径

### 错误分析
测试失败主要集中在 refactor 操作（重命名、移动）后，`stitcher.lock` 文件（存储在 JSON 格式的签名）中的 SURI 没有被更新。

1.  **结构不匹配**: `stitcher.lock` 文件使用了 `{ "version": "...", "fingerprints": { ... } }` 的嵌套结构。而 `SidecarTransformer` 的 `_transform_json_data` 方法直接遍历根字典的 keys，期望它们是 SURI。这导致 `fingerprints` 字典被完全忽略，SURI 从未被处理。
2.  **路径匹配脆弱**: SURI 解析出的路径可能带有前导斜杠（取决于 `SURIGenerator` 的实现细节），而 `RefactorContext` 中提供的路径通常是相对路径（无前导斜杠）。直接字符串比较导致路径匹配失败，从而导致移动文件操作中的 SURI 路径未更新。

### 用户需求
修复 `SidecarTransformer` 以正确处理 `stitcher.lock` 文件结构，并确保 SURI 更新逻辑的鲁棒性。

### 评论
这是一个关键的修复，确保重构操作能够保持签名数据库的一致性。

### 目标
1.  修改 `SidecarTransformer._transform_json_data` 以递归处理 `fingerprints` 字段。
2.  在比较 SURI 路径和上下文路径时，进行规范化（去除前导斜杠）。

### 基本原理
通过递归检查 `fingerprints` 键，我们可以透明地支持扁平的 JSON 文件（旧格式或测试数据）和新的 `stitcher.lock` 格式。规范化路径比较可以消除由于 URI 格式差异导致的匹配错误。

### 标签
#intent/fix #flow/ready #priority/high #comp/runtime #concept/refactor #scope/core #ai/instruct #task/domain/refactoring #task/object/sidecar-transformer #task/action/fix-lock-file-update #task/state/begin

---

### Script

#### Acts 1: 修复 SidecarTransformer 的 JSON 处理逻辑

~~~~~act
patch_file
packages/stitcher-lang-sidecar/src/stitcher/lang/sidecar/transform.py
~~~~~
~~~~~python.old
    def _transform_json_data(
        self,
        data: Dict[str, Any],
        old_file_path: Optional[str],
        new_file_path: Optional[str],
        old_fragment: Optional[str],
        new_fragment: Optional[str],
    ) -> Dict[str, Any]:
        new_data = {}
        modified = False

        for key, value in data.items():
            if not key.startswith("py://"):
                new_data[key] = value
                continue

            try:
                path, fragment = SURIGenerator.parse(key)
            except ValueError:
                new_data[key] = value
                continue

            original_path, original_fragment = path, fragment
            current_path, current_fragment = path, fragment

            if old_file_path and new_file_path and current_path == old_file_path:
                current_path = new_file_path

            if (
                old_fragment is not None
                and new_fragment is not None
                and current_fragment is not None
            ):
                if current_fragment == old_fragment:
                    current_fragment = new_fragment
                elif current_fragment.startswith(old_fragment + "."):
                    suffix = current_fragment[len(old_fragment) :]
                    current_fragment = new_fragment + suffix

            if current_path != original_path or current_fragment != original_fragment:
                new_key = (
                    SURIGenerator.for_symbol(current_path, current_fragment)
                    if current_fragment
                    else SURIGenerator.for_file(current_path)
                )
                new_data[new_key] = value
                modified = True
            else:
                new_data[key] = value

        return new_data if modified else data
~~~~~
~~~~~python.new
    def _transform_json_data(
        self,
        data: Dict[str, Any],
        old_file_path: Optional[str],
        new_file_path: Optional[str],
        old_fragment: Optional[str],
        new_fragment: Optional[str],
    ) -> Dict[str, Any]:
        # Handle stitcher.lock format (nested fingerprints)
        if "fingerprints" in data and isinstance(data["fingerprints"], dict):
            new_fingerprints = self._transform_json_data(
                data["fingerprints"],
                old_file_path,
                new_file_path,
                old_fragment,
                new_fragment,
            )
            if new_fingerprints is not data["fingerprints"]:
                new_data = data.copy()
                new_data["fingerprints"] = new_fingerprints
                return new_data
            return data

        new_data = {}
        modified = False

        for key, value in data.items():
            if not key.startswith("py://"):
                new_data[key] = value
                continue

            try:
                path, fragment = SURIGenerator.parse(key)
            except ValueError:
                new_data[key] = value
                continue

            original_path, original_fragment = path, fragment
            current_path, current_fragment = path, fragment

            # Normalize paths for comparison (remove potential leading slashes from SURI parsing)
            # We assume old_file_path/new_file_path provided by context are relative/normalized.
            norm_current_path = current_path.lstrip("/")

            if (
                old_file_path
                and new_file_path
                and norm_current_path == old_file_path.lstrip("/")
            ):
                current_path = new_file_path

            if (
                old_fragment is not None
                and new_fragment is not None
                and current_fragment is not None
            ):
                if current_fragment == old_fragment:
                    current_fragment = new_fragment
                elif current_fragment.startswith(old_fragment + "."):
                    suffix = current_fragment[len(old_fragment) :]
                    current_fragment = new_fragment + suffix

            if current_path != original_path or current_fragment != original_fragment:
                new_key = (
                    SURIGenerator.for_symbol(current_path, current_fragment)
                    if current_fragment
                    else SURIGenerator.for_file(current_path)
                )
                new_data[new_key] = value
                modified = True
            else:
                new_data[key] = value

        return new_data if modified else data
~~~~~

### 下一步建议

运行测试以验证修复：
`pytest packages/stitcher-lang-sidecar/tests/unit/test_transform.py packages/stitcher-refactor/tests/integration/`
