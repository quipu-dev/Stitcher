好的，Dogfooding 过程虽然波折，但它极大地帮助我们磨砺了工具的边缘。通过这次实战，我们不仅修复了命名空间遮蔽、符号导出和类型注入等关键缺陷，还确立了高质量的文档生成基准。

现在，我们将这些成果作为 Dogfooding 计划第一阶段的里程碑进行提交。

## [COMMIT] fix(engine): 修复符号导出与类型导入，并建立 Dogfooding 基线

### 错误分析

在执行 `stitcher init` 和 `generate` 的 Dogfooding 过程中，我们发现了以下影响项目可用性的核心缺陷：

1.  **私有导出问题**: 默认生成的 `.pyi` 文件中，导入被视为私有的。导致库使用者在 IDE 中看到大量的 `unknown import symbol`。
2.  **Any 导入缺失**: 当属性没有类型注解时，生成器会默认使用 `Any`，但解析器未能自动注入 `from typing import Any`，导致生成的存根语法无效。
3.  **命名空间遮蔽**: 根目录不当存在的 `__init__.py` 被生成了 `__init__.pyi`，导致 Python 3 隐式命名空间包机制失效，子包无法被解析。
4.  **YAML 可读性差**: 默认的 PyYAML 输出将多行文档字符串转义为单行，导致生成的文档资产难以手动维护。

### 用户需求
建立 `stitcher-python` 项目自身的文档管理基准，并确保生成的存根文件能被 IDE 正确识别且无语法错误。

### 评论
“吃自己的狗粮”是验证开发工具质量的最佳方式。这次提交不仅是代码的修复，更是项目基础设施的一次重大升级，它让 `stitcher` 从一个原型变成了一个真正可用的工具。

### 目标
1.  提交所有核心引擎的修复（`__all__` 解析、`Any` 注入、多行 YAML）。
2.  提交项目环境的优化配置（`pyrightconfig.json`, `py.typed`, `.gitignore`）。
3.  建立初始的 `.stitcher.yaml` 文档资产基准。

### 基本原理
我们将所有变更打包为一个逻辑单元。其中 `pyrightconfig.json` 和 `py.typed` 解决了 LSP 的解析路径问题；`StubGenerator` 和 `Parser` 的修改解决了 `.pyi` 文件的合法性和导出可见性问题；`YamlAdapter` 的优化保证了资产的可维护性。

### 标签
#intent/fix #flow/ready #priority/high #comp/engine #comp/build #ai/instruct 
#task/domain/dogfooding #task/object/baseline #task/action/commit #task/state/end #task/status/completed

---

### Script

#### Acts 1: 记录并提交所有 Dogfooding 成果

我们将所有修改添加到暂存区并进行提交。

~~~~~act
git_add
.
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
fix(engine): comprehensive fixes for stub generation and workspace DX

This commit marks the completion of the first Dogfooding phase, fixing several
critical issues found while applying Stitcher to its own codebase:

- Export Support: Added parsing of '__all__' in scanner and generation in
  StubGenerator. This ensures that symbols in .pyi files are treated as
  public exports by IDEs.
- Automatic Typing: The parser now proactively injects 'from typing import Any'
  when unannotated attributes are detected, preventing invalid .pyi files.
- YAML Formatting: Implemented a custom Dumper in YamlAdapter to force
  Literal Block Style (|) for multiline strings, significantly improving
  documentation maintainability.
- Namespace & IDE Fixes:
    - Removed incorrect root __init__.py files to restore proper PEP 420
      namespace package behavior.
    - Added 'py.typed' to all packages.
    - Created 'pyrightconfig.json' to standardize Monorepo path resolution
      for Pylance and other LSP servers.
- Dogfooding Baseline: Initialized .stitcher.yaml files for the entire
  workspace and updated .gitignore to exclude generated .pyi artifacts.
~~~~~

### 下一步建议
1.  **执行 Dogfooding 任务 2.1**: 现在基础设施已经稳固，你可以放心地再次运行 `stitcher generate`，生成的存根应该会立刻被你的 lvim 识别且不再报错。
2.  **清理多余文件**: 如果你觉得 `tests/` 目录下生成的 `.stitcher.yaml` 太多，可以考虑在 `pyproject.toml` 的 `scan_paths` 中将其更精细地限制为各包的 `src` 目录。
3.  **进入下一阶段**: Dogfooding 已经证明了 `init` 和 `generate` 的有效性。我们可以开始考虑“第三阶段：健壮性”中的功能，或者开始处理插件解析的高级场景。
