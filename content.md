简要回答：
完全同意。使用系统标准的 `LANG` 环境变量（如 `zh_CN.UTF-8`）是符合 Unix 哲学且对用户最友好的做法。

我将更新计划，在 `stitcher-needle` 的运行时中增加对 `LANG` 的解析逻辑，自动提取前缀（如将 `zh_CN.UTF-8` 转换为 `zh`），并同时提供 `stitcher-cli` 的中文语言包。

## [WIP] refactor(needle): 基于系统标准 LANG 变量实现通用语言自动检测

### 用户需求
1.  **通用性**: 不再仅依赖自定义的 `STITCHER_LANG`，而是优先适配系统标准的 `LANG` 环境变量。
2.  **解析**: 能够正确处理 `zh_CN.UTF-8` 这样的复合字符串，将其映射到 `zh` 资源目录。
3.  **汉化实施**: 提供 CLI 帮助文档的中文资源文件。

### 评论
使用 `LANG` 是 CLI 工具走向成熟的标志。通过解析系统语言设置，Stitcher 可以实现“零配置”的开箱即用汉化。同时保留 `STITCHER_LANG` 作为显式覆盖选项，兼顾了灵活性。

### 目标
1.  修改 `stitcher-needle` 的 `Needle.get` 逻辑：
    *   解析 `STITCHER_LANG` (最高优先级)。
    *   解析 `LANG`（处理 `zh_CN.UTF-8` -> `zh`）。
    *   默认回退到 `en`。
2.  创建 `packages/stitcher-cli/src/stitcher/cli/assets/needle/zh/commands.json`。

### 基本原理
在 Unix 系统中，`LANG` 的格式通常为 `language_territory.codeset`。我们通过简单的字符串分割（以 `_` 或 `.` 为界）即可提取出核心语言代码。将此逻辑封装在 `Needle` 运行时内，可以确保所有基于 Needle 的组件（CLI, App, Web）都能共享这一智能检测机制。

### 标签
#intent/refine #flow/ready #priority/high #comp/needle #comp/cli #concept/i18n #ai/instruct #task/domain/i18n #task/object/language-detection #task/action/standardization #task/state/continue

---

### Script

#### Acts 1: 更新 Needle 语言检测逻辑

我们将修改 `Needle` 类的 `get` 方法，使其能够智能解析系统环境变量。

~~~~~act
patch_file
packages/stitcher-needle/src/stitcher/needle/runtime.py
~~~~~
~~~~~python.old
    def get(
        self, pointer: Union[SemanticPointer, str], lang: Optional[str] = None
    ) -> str:
        """
        Resolves a semantic pointer to a string value with graceful fallback.

        Lookup Order:
        1. Target Language
        2. Default Language (en)
        3. Identity (the key itself)
        """
        key = str(pointer)
        target_lang = lang or os.getenv("STITCHER_LANG", self.default_lang)

        # 1. Try target language
~~~~~
~~~~~python.new
    def _resolve_lang(self, explicit_lang: Optional[str] = None) -> str:
        """
        Determines the current language based on hierarchy:
        1. Explicitly passed 'lang' argument.
        2. STITCHER_LANG environment variable.
        3. System LANG environment variable (e.g., zh_CN.UTF-8 -> zh).
        4. Default (en).
        """
        if explicit_lang:
            return explicit_lang

        # Explicit override
        stitcher_lang = os.getenv("STITCHER_LANG")
        if stitcher_lang:
            return stitcher_lang

        # System standard
        system_lang = os.getenv("LANG")
        if system_lang:
            # Handle formats like zh_CN.UTF-8, en_US, etc.
            # Split by '_' or '.' and take the first part.
            return system_lang.split("_")[0].split(".")[0].lower()

        return self.default_lang

    def get(
        self, pointer: Union[SemanticPointer, str], lang: Optional[str] = None
    ) -> str:
        """
        Resolves a semantic pointer to a string value with graceful fallback.

        Lookup Order:
        1. Target Language (resolved via _resolve_lang)
        2. Default Language (en)
        3. Identity (the key itself)
        """
        key = str(pointer)
        target_lang = self._resolve_lang(lang)

        # 1. Try target language
~~~~~

#### Acts 2: 提供 CLI 中文资源文件 (Chinese Assets)

现在我们创建中文语言包，实现 CLI 帮助界面的汉化。

~~~~~act
write_file
packages/stitcher-cli/src/stitcher/cli/assets/needle/zh/commands.json
~~~~~
~~~~~json
{
    "cli.app.description": "Stitcher-Python: 缝合动态代码与静态分析之间的鸿沟。",
    "cli.command.generate.help": "根据 pyproject.toml 配置生成 .pyi 存根文件。",
    "cli.command.init.help": "在当前项目中初始化 Stitcher。",
    "cli.command.check.help": "验证代码结构与文档的一致性。",
    "cli.command.strip.help": "从源代码中移除文档字符串。",
    "cli.command.eject.help": "将 .stitcher.yaml 中的文档重新注入源代码。",
    "cli.command.hydrate.help": "从源代码提取新文档并合并至 .stitcher.yaml。",
    "cli.option.strip.help": "在补水后立即从源码中移除文档字符串。",
    "cli.option.force.help": "代码优先：如果内容不一致，覆盖 YAML 内容。",
    "cli.option.reconcile.help": "YAML 优先：忽略与现有 YAML 冲突的源码文档。"
}
~~~~~

### 下一步建议
1.  **测试验证**: 在终端执行 `LANG=zh_CN.UTF-8 stitcher --help`。你应该能看到完整的中文命令说明。
2.  **错误信息汉化**: 目前 `stitcher-common` 中还有一些错误消息（如 `check.file.fail`）只有英文。建议在 `stitcher-common` 下也创建 `zh` 资源目录进行补全。
3.  **多区域支持**: 现在的逻辑会将 `zh_CN` 和 `zh_TW` 都映射到 `zh`。如果未来需要区分简繁体，只需将 `_resolve_lang` 改为返回 `zh_CN`，并在资源目录中对应创建文件夹即可。
