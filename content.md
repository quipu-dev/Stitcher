检测到“确定性缺失”违例，由于 `PumpRunner` 和 `CheckRunner` 在处理基准存档时未能统一遵循 SURI 协议，导致数据在不同命令间发生“格式腐蚀”。根据 **ADAP v1.0** 和 **HFEA v1.0** 协议，我们必须首先修复这一架构缺陷。

## [WIP] fix: 统一全系统基准存档的 SURI 迁移与持久化逻辑

### 错误分析
1.  **加载逻辑过严 (`SignatureManager`)**: `load_composite_hashes` 目前仅接受 SURI 格式的键。遇到旧版的短键（如 `func`）时，`SURIGenerator.parse` 会抛出异常，导致旧数据被直接忽略。这使得 `check` 命令无法识别旧版存档，从而无法执行升级。
2.  **持久化逻辑越权 (`PumpRunner`)**: `PumpRunner` 目前绕过了 `SignatureManager` 的封装，在自己的代码中手动进行 JSON 序列化，且错误地使用了 `fqn` 作为键。这直接导致了协议违规，将已升级的 SURI 键重新覆盖为旧的短键。

### 用户需求
统一全链路的签名文件处理：让系统能够向后兼容加载旧格式，并确保任何写回操作（不管是 `init`、`check` 还是 `pump`）都强制统一为 SURI 格式。

### 评论
“平庸是比错误更严重的失败”。我们不应该在各处散布 SURI 转换逻辑。`SignatureManager` 应该作为基准存档的唯一权威门户，负责处理从旧格式到新格式的透明迁移。

### 目标
1.  **兼容性加载**: 增强 `SignatureManager.load_composite_hashes`，使其能识别并回退到解析旧版短键。
2.  **统一持久化**:
    *   在 `SignatureManager` 中提取出 `serialize_hashes` 工具方法。
    *   重构 `PumpRunner`，使其不再手动构造 JSON，而是调用 `SignatureManager` 的逻辑生成符合协议的内容。
3.  **修复 Check 迁移**: 既然加载逻辑现在能看到旧键，`check --force-relink` 触发的保存操作将通过 `SignatureManager` 自动将这些键升级为 SURI。

### 基本原理
-   **SSoT (真理单一来源)**: 所有的 SURI 生成必须通过 `SignatureManager` 控制。
-   **透明迁移**: 当 Manager 发现一个非 SURI 格式的键时，将其视为 `fragment`。这样，旧数据被加载到内存中，下一次保存时由于 Manager 强制调用 `for_symbol`，它会自然而然地被“洗”成 SURI。

### 标签
#intent/fix #flow/ready #priority/critical #comp/application #concept/state #scope/core #ai/instruct #task/domain/storage #task/object/signature-archive #task/action/unify-protocol #task/state/continue

---

### Script

#### Acts 1: 增强 SignatureManager 的兼容性与工具化

修改 `SignatureManager`：
1. 使 `load_composite_hashes` 支持旧版短键。
2. 暴露 `serialize_hashes` 方法，供需要通过 TransactionManager 写入的 Runner 使用。

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/services/signature_manager.py
~~~~~
~~~~~python.old
    def save_composite_hashes(
        self, file_path: str, hashes: Dict[str, Fingerprint]
    ) -> None:
        if not hashes:
            sig_path = self._get_sig_path(file_path)
            if sig_path.exists():
                sig_path.unlink()
            return

        sig_path = self._get_sig_path(file_path)
        sig_path.parent.mkdir(parents=True, exist_ok=True)

        serialized_data = {
            SURIGenerator.for_symbol(file_path, fqn): fp.to_dict()
            for fqn, fp in hashes.items()
        }

        with sig_path.open("w", encoding="utf-8") as f:
            json.dump(serialized_data, f, indent=2, sort_keys=True)

    def load_composite_hashes(self, file_path: str) -> Dict[str, Fingerprint]:
        sig_path = self._get_sig_path(file_path)
        if not sig_path.exists():
            return {}
        try:
            with sig_path.open("r", encoding="utf-8") as f:
                data = json.load(f)
                if not isinstance(data, dict):
                    return {}
                result = {}
                for suri, fp_data in data.items():
                    try:
                        _path, fragment = SURIGenerator.parse(suri)
                        if fragment:
                            result[fragment] = Fingerprint.from_dict(fp_data)
                    except (ValueError, InvalidFingerprintKeyError):
                        # Gracefully skip malformed SURIs or invalid fingerprint data
                        continue
                return result
        except (json.JSONDecodeError, OSError):
            return {}
~~~~~
~~~~~python.new
    def serialize_hashes(self, file_path: str, hashes: Dict[str, Fingerprint]) -> str:
        """
        Serializes fingerprints into a JSON string using SURI as keys.
        """
        serialized_data = {
            SURIGenerator.for_symbol(file_path, fqn): fp.to_dict()
            for fqn, fp in hashes.items()
        }
        return json.dumps(serialized_data, indent=2, sort_keys=True)

    def save_composite_hashes(
        self, file_path: str, hashes: Dict[str, Fingerprint]
    ) -> None:
        if not hashes:
            sig_path = self._get_sig_path(file_path)
            if sig_path.exists():
                sig_path.unlink()
            return

        sig_path = self._get_sig_path(file_path)
        sig_path.parent.mkdir(parents=True, exist_ok=True)
        content = self.serialize_hashes(file_path, hashes)

        with sig_path.open("w", encoding="utf-8") as f:
            f.write(content)

    def load_composite_hashes(self, file_path: str) -> Dict[str, Fingerprint]:
        sig_path = self._get_sig_path(file_path)
        if not sig_path.exists():
            return {}
        try:
            with sig_path.open("r", encoding="utf-8") as f:
                data = json.load(f)
                if not isinstance(data, dict):
                    return {}
                result = {}
                for key, fp_data in data.items():
                    try:
                        # Protocol Check: If it's a SURI, parse it.
                        if key.startswith("py://"):
                            _path, fragment = SURIGenerator.parse(key)
                        else:
                            # Legacy Fallback: Treat key as direct fragment
                            fragment = key

                        if fragment:
                            result[fragment] = Fingerprint.from_dict(fp_data)
                    except (ValueError, InvalidFingerprintKeyError):
                        continue
                return result
        except (json.JSONDecodeError, OSError):
            return {}
~~~~~

#### Acts 2: 修正 PumpRunner 的非法写入

重构 `PumpRunner.run_batch`，确保其通过 `SignatureManager` 产生持久化内容。

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/runners/pump.py
~~~~~
~~~~~python.old
                if signatures_need_save:
                    if not new_hashes:
                        sig_path = self.sig_manager._get_sig_path(module.file_path)
                        if sig_path.exists():
                            tm.add_delete_file(
                                str(sig_path.relative_to(self.root_path))
                            )
                    else:
                        self.sig_manager.save_composite_hashes(
                            module.file_path, new_hashes
                        )
                        # The save logic is complex, let's defer to the manager.
                        # We need to write the content via the TM.
                        serialized_data = {
                            fqn: fp.to_dict() for fqn, fp in new_hashes.items()
                        }
                        sig_content = json.dumps(
                            serialized_data, indent=2, sort_keys=True
                        )
                        sig_path = self.sig_manager._get_sig_path(module.file_path)
                        tm.add_write(
                            str(sig_path.relative_to(self.root_path)), sig_content
                        )
~~~~~
~~~~~python.new
                if signatures_need_save:
                    sig_path = self.sig_manager._get_sig_path(module.file_path)
                    rel_sig_path = str(sig_path.relative_to(self.root_path))

                    if not new_hashes:
                        if sig_path.exists():
                            tm.add_delete_file(rel_sig_path)
                    else:
                        # Use centralized serialization to ensure SURI keys
                        sig_content = self.sig_manager.serialize_hashes(
                            module.file_path, new_hashes
                        )
                        tm.add_write(rel_sig_path, sig_content)
~~~~~

### 下一步建议

由于 `SignatureManager` 现在具备了向后兼容能力且强制了 SURI 持久化：
1. `pump` 操作现在会自动将原有的短键升级为 SURI 键。
2. `check --force-relink` 逻辑现在能正确“看到”旧键并将其“洗白”为 SURI。

请立即运行迁移测试：
`pytest packages/stitcher-application/tests/integration/test_signature_migration.py`

这些测试现在应该能够全部通过（GREEN）。完成后，我们才真正拥有了一个统一的数据底座，可以继续推进 `PumpRunner` 的 Query-First 重构。
