## Acts 1: 修复集成测试以适应 `ruamel.yaml` 的行为

这是非常敏锐的洞察。你发现了一个微妙但至关重要的架构冲突，它直接关系到 Stitcher 工具的**本体论（Ontology）**和用户体验。

我们来深入分析这个冲突：

### 1. 冲突的核心：两个互斥的“正确”原则

我们当前的目标被两个看似都正确、但实际上相互矛盾的原则撕裂了：

*   **原则 A：高保真原则 (The Preservation Principle)**
    *   **主张**：工具不应该破坏用户的劳动成果。如果用户精心调整了 YAML 的格式或添加了注释，系统在**更新**文件时必须无损地保留这一切。
    *   **动机**：这是我们选择 `ruamel.yaml` 的根本原因。一个会“格式化掉”用户注释的工具是具有破坏性的，会严重降低用户的信任感。

*   **原则 B：标准化原则 (The Standardization Principle)**
    *   **主张**：工具生成的产物应该是确定性的、一致的和可读的。所有由 `stitcher init` **创建**的新 Sidecar 文件都应该遵循统一的、最佳实践的格式（例如，使用 `|-` 来增强可读性）。
    *   **动机**：这确保了项目的整洁，使得新生成文件的 `git diff` 变得干净且易于审查。

**你发现的冲突点在于：我们之前的实现试图用“标准化原则”（强制 `|-`）去覆盖所有场景，这直接违反了在“更新”场景下更为重要的“高保真原则”。**

### 2. 你提出的解决方案及其深层风险

你的提议——“新提取的模块强制格式化，否则保留原始格式”——在直觉上是正确的，因为它试图区分**创建（Create）**和**更新（Update）**这两种不同的操作。

然而，正如你所怀疑的，“这或许太复杂”。其复杂性不在于 `if path.exists()` 这个判断，而在于它会引入一个更隐蔽的问题：**格式熵增（Format Entropy）**。

*   **场景模拟**：
    1.  **Day 1**：你运行 `stitcher init`，所有 `.stitcher.yaml` 文件都以我们定义的“标准格式 v1.0”创建。一切都很完美。
    2.  **Day 30**：你手动编辑了 `a.stitcher.yaml`，调整了某些长字符串的换行，并添加了重要的注释。
    3.  **Day 31**：你运行 `stitcher pump` 来同步一个新函数。根据“保留原始格式”的规则，`ruamel.yaml` 会加载 `a.stitcher.yaml`，保留你的所有自定义格式，然后追加新的内容。
    4.  **Day 60**：我们决定升级 Stitcher 的“标准格式”到 v2.0（比如改变缩进）。现在，当你 `init` 一个新模块时，它会使用 v2.0 格式。但是，所有旧文件（包括 `a.stitcher.yaml`）在 `pump` 时依然会保留其陈旧的 v1.0 格式或你的自定义格式。

*   **后果**：项目中的 Sidecar 文件将变成一个**格式的“混合博物馆”**，其风格取决于它被创建和修改的历史。这破坏了系统的确定性和一致性。

### 3. 公理化的解决方案：以操作意图为准绳

解决这个问题的关键，是回归到**操作的意图（Intent）**，并让 `SidecarAdapter` 的行为严格反映这个意图。

*   **公理1：CREATE 操作必须是标准化的。**
    *   当 `SidecarAdapter` 被要求**从零创建一个新文件**时（如 `init`），它**必须**使用内部定义的、最理想的标准化格式器来生成内容。这是它唯一的机会来建立一个干净的基线。

*   **公理2：UPDATE 操作必须是高保真的。**
    *   当 `SidecarAdapter` 被要求**修改一个已存在的文件**时（如 `pump` 一个新函数），它**必须**先加载现有文件的完整表示（包括格式和注释），然后在这个表示上进行修改，最后写回。`ruamel.yaml` 的圆整（Round-trip）能力就是为此而生的。

这不再是一个简单的 `if/else`，而是一个关于**状态转换的架构决策**。

### 结论与实施方案

你的分析是完全正确的，我们不能粗暴地强制格式化。我将废弃之前的实现，并采用这个新的、公理化的方法来重构 `SidecarAdapter`：

1.  **`save_doc_irs` 逻辑重构**：
    *   **创建路径 (CREATE)**：当目标 `path` 不存在时，`save_doc_irs` 将从纯 Python `dict` 构建 YAML 内容，并应用我们的标准化格式（包括强制使用 `LiteralScalarString`）。
    *   **更新路径 (UPDATE)**：当目标 `path` **存在**时，`save_doc_irs` 将首先用 `ruamel.yaml` **加载**该文件，在加载后的对象上进行数据更新，然后再将其**写回**。这将自动保留所有原始格式和注释。

2.  **测试用例更新**：
    *   `test_init_command` 的断言是正确的，因为它测试的是 **CREATE** 场景，所以必须验证其输出是标准化的（包含 `|-`，但不强制要求引号）。我会更新测试，使其不再检查引号。
    *   我们将添加一个新的集成测试，用于验证 **UPDATE** 场景，断言在 `pump` 操作后，一个手动添加的注释**没有丢失**。

我将立即开始实施这个更精确、更健壮的方案。首先，修复测试用例。

---
### Script

#### Acts 1: 修复集成测试以适应 `ruamel.yaml` 的行为

`ruamel.yaml` 足够智能，只在必要时为 YAML 键添加引号。我们的测试不应该依赖于这种脆弱的实现细节。我将更新测试，使其只关注核心的格式契约——即字符串值是否以块风格（`|-`）呈现。

~~~~~act
patch_file
packages/stitcher-application/tests/integration/test_init_command.py
~~~~~
~~~~~python.old
    content = expected_yaml.read_text()
    # Check for block style with quoted key
    assert '"my_func": |-' in content
    assert "  This is a docstring." in content
~~~~~
~~~~~python.new
    content = expected_yaml.read_text()
    # Check for block style. ruamel.yaml is smart and won't quote simple keys.
    assert "my_func: |-" in content
    assert "  This is a docstring." in content
~~~~~
