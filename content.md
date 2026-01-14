简要回答
执行单元测试修复，使其与“SURI 作为 FQN 存储”的架构变更保持一致。

## [WIP] test(sidecar): 更新 SidecarAdapter 测试以匹配 SURI-in-FQN 架构

### 错误分析
`test_sidecar_adapter.py` 中的测试失败是因为我们在上一步（Act 1）中修改了 `SidecarAdapter` 的行为——将 SURI 存储在 `target_fqn` 而非 `target_id`——但没有同步更新测试用例的断言逻辑。这导致了 `None != 'py://...'` 的断言错误。

### 用户需求
修复因架构变更导致的单元测试失败，确保测试套件如实反映当前的系统行为。

### 评论
这是标准的重构步骤：Red -> Green -> Refactor。我们在 Green 阶段（实现修复）打破了旧的测试（变为 Red），现在必须修复测试以使其变绿。

### 目标
1.  更新 `test_adapter_json_dispatch`，断言 `ref.target_fqn` 为 SURI，`ref.target_id` 为 None。
2.  更新 `test_adapter_yaml_suri_computation`，使用 `target_fqn` 构建查找表并进行断言。

### 基本原理
为了解决数据库 FK 约束问题，我们推迟了链接过程，将 SURI 暂时视为 FQN。单元测试必须验证这一“推迟”行为是否正确发生。

### 标签
#intent/fix #flow/ready #priority/high #comp/tests #scope/core #ai/instruct #task/domain/testing #task/object/unit-test #task/action/update #task/state/continue

---

### Script

#### Acts 1: 修复 test_sidecar_adapter.py

更新断言逻辑以匹配新的 `SidecarAdapter` 行为。

~~~~~act
patch_file
packages/stitcher-lang-sidecar/tests/unit/test_sidecar_adapter.py
~~~~~
~~~~~python.old
    ref = refs[0]
    assert ref.kind == ReferenceType.SIDECAR_ID.value
    assert ref.target_id == "py://foo#bar"
    assert ref.target_fqn is None


def test_adapter_yaml_suri_computation(tmp_path: Path):
    # 1. ARRANGE: Create a mock file system
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    py_file = src_dir / "module.py"
    py_file.touch()

    yaml_file = src_dir / "module.stitcher.yaml"
    yaml_content = dedent("""
    MyClass: hello
    my_func: world
    """)
    yaml_file.write_text(yaml_content)

    # 2. ACT
    adapter = SidecarAdapter(root_path=tmp_path, uri_generator=PythonURIGenerator())
    symbols, refs, doc_entries = adapter.parse(yaml_file, yaml_content)

    # 3. ASSERT
    assert len(symbols) == 0
    assert len(refs) == 2
    assert len(doc_entries) == 2

    refs_by_id = {ref.target_id: ref for ref in refs}
    doc_entries_by_id = {de.symbol_id: de for de in doc_entries}

    # Verify first reference
    suri1 = "py://src/module.py#MyClass"
    assert suri1 in refs_by_id
    ref1 = refs_by_id[suri1]
    assert ref1.kind == ReferenceType.SIDECAR_DOC_ID.value
    assert ref1.lineno == 2
    assert ref1.col_offset == 0

    # Verify second reference
    suri2 = "py://src/module.py#my_func"
    assert suri2 in refs_by_id
    ref2 = refs_by_id[suri2]
    assert ref2.kind == ReferenceType.SIDECAR_DOC_ID.value
    assert ref2.lineno == 4
    assert ref2.col_offset == 0
~~~~~
~~~~~python.new
    ref = refs[0]
    assert ref.kind == ReferenceType.SIDECAR_ID.value
    # SURI is now stored in target_fqn to defer linking/FK checks
    assert ref.target_fqn == "py://foo#bar"
    assert ref.target_id is None


def test_adapter_yaml_suri_computation(tmp_path: Path):
    # 1. ARRANGE: Create a mock file system
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    py_file = src_dir / "module.py"
    py_file.touch()

    yaml_file = src_dir / "module.stitcher.yaml"
    yaml_content = dedent("""
    MyClass: hello
    my_func: world
    """)
    yaml_file.write_text(yaml_content)

    # 2. ACT
    adapter = SidecarAdapter(root_path=tmp_path, uri_generator=PythonURIGenerator())
    symbols, refs, doc_entries = adapter.parse(yaml_file, yaml_content)

    # 3. ASSERT
    assert len(symbols) == 0
    assert len(refs) == 2
    assert len(doc_entries) == 2

    # Map using target_fqn as that's where SURI is stored now
    refs_by_fqn = {ref.target_fqn: ref for ref in refs}
    doc_entries_by_id = {de.symbol_id: de for de in doc_entries}

    # Verify first reference
    suri1 = "py://src/module.py#MyClass"
    assert suri1 in refs_by_fqn
    ref1 = refs_by_fqn[suri1]
    assert ref1.kind == ReferenceType.SIDECAR_DOC_ID.value
    assert ref1.lineno == 2
    assert ref1.col_offset == 0
    assert ref1.target_id is None  # Should be None until linked

    # Verify second reference
    suri2 = "py://src/module.py#my_func"
    assert suri2 in refs_by_fqn
    ref2 = refs_by_fqn[suri2]
    assert ref2.kind == ReferenceType.SIDECAR_DOC_ID.value
    assert ref2.lineno == 4
    assert ref2.col_offset == 0
~~~~~

### 下一步建议
运行测试。如果这些单元测试通过，而 `test_refactor_move_updates_suri_in_signatures` 仍然失败，我们应检查 Refactor 流程中是否有其他组件（如 Intent 生成器）也假设了 `target_id` 已被填充，或者是否 `LockManager` 的逻辑在无索引状态下有缺陷。
