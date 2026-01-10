好的，我将添加中文翻译并为 `index` 命令组及其子命令添加完整的 `help` 文档。

## [WIP] tune(cli): 为 index 命令添加国际化支持

### 用户需求
`stitcher index` 命令及其子命令缺少 `help` 文档和中文日志。需要补充这些内容以提升用户体验。

### 评论
这是一个简单的润色任务，但对于 CLI 工具的可用性至关重要。

### 目标
1.  创建中文版的 `index/run.json` 资源文件。
2.  更新中文版的 `cli/command.json`，添加 `index` 和 `index_build` 的帮助文本。

### 基本原理
利用 Needle 的 I18N 机制，通过添加 JSON 资源文件来提供多语言支持。CLI 代码已经使用了 `nexus(L...)` 结构，因此无需修改 Python 代码。

### 标签
#intent/tune #flow/ready #priority/low #comp/cli #concept/ui #scope/ux #ai/instruct

---

### Script

#### Acts 1: 添加中文日志资源

~~~~~act
write_file
packages/stitcher-common/src/stitcher/common/assets/needle/zh/index/run.json
~~~~~
~~~~~json
{
  "start": "🔄 开始增量索引构建...",
  "complete": "✨ 索引构建完成。新增: {added}, 更新: {updated}, 删除: {deleted}, 跳过: {skipped}"
}
~~~~~

#### Acts 2: 添加中文 CLI 帮助文本

~~~~~act
patch_file
packages/stitcher-common/src/stitcher/common/assets/needle/zh/cli/command.json
~~~~~
~~~~~json.old
  "refactor_apply": {
    "help": "从迁移脚本应用自动化代码重构。"
  },
  "not_implemented": "ℹ️  命令 '{command}' 尚未实现。"
}
~~~~~
~~~~~json.new
  "refactor_apply": {
    "help": "从迁移脚本应用自动化代码重构。"
  },
  "index": {
    "help": "管理语义索引。"
  },
  "index_build": {
    "help": "增量式构建或更新语义索引。"
  },
  "not_implemented": "ℹ️  命令 '{command}' 尚未实现。"
}
~~~~~

### 下一步建议
现在，你可以重新运行 `stitcher --help` 和 `stitcher index --help` (在 `STITCHER_LANG=zh` 或系统语言为中文的环境下)，应该能看到更新后的帮助文档。

如果你确认无误，我们可以将此调整提交。
