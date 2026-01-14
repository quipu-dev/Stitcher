这是一个针对 Foreign Key 约束失败问题的修复计划。

## [WIP] fix: 修复 Sidecar 索引时的外键约束冲突

### 错误分析
多个集成测试失败，错误信息为 `sqlite3.OperationalError: FOREIGN KEY constraint failed`。
原因在于 `SidecarIndexerAdapter` 在创建 `ReferenceRecord` 时，直接生成了 Python 文件的 SURI 并赋值给了 `target_id`。
在数据库 Schema 中，`references.target_id` 是一个指向 `symbols.id` 的外键。
如果 `.stitcher.yaml` 文件在对应的 `.py` 文件之前被索引（或者两者在同一批次中但 Python 符号尚未提交），数据库中就不存在对应的 Python 符号记录，从而导致外键约束检查失败。

### 用户需求
修复测试中的数据库错误，确保 Sidecar 文件可以被正常索引，而不受文件索引顺序的影响。

### 评论
这是“分布式”或“乱序”索引系统中常见的问题。正确的解法是**延迟链接（Late Binding）**。我们不应该在解析阶段（Parse Phase）强行绑定 ID，而应该记录“意图”（即 `target_fqn`），并让链接器（Linker）在所有符号都入库后，统一解决引用关系。这正是 Stitcher 架构的设计初衷。

### 目标
1.  修改 `SidecarIndexerAdapter`，不再直接设置 `target_id`。
2.  引入 `path_to_logical_fqn` 工具，计算目标 Python 符号的逻辑全名（FQN），并将其存入 `target_fqn`。
3.  依赖现有的 `Linker` 机制在索引后期自动填充 `target_id`。

### 基本原理
通过只存储 `target_fqn`，我们解耦了 Sidecar 索引和 Python 索引的依赖关系。无论哪个文件先被处理，`references` 表都能成功写入。当所有文件处理完毕后，`Linker` 会运行 SQL 语句，根据 `target_fqn` 查找对应的 `symbols` 表记录，并回填 `target_id`，从而建立强连接。

### 标签
#intent/fix #flow/ready #priority/critical #comp/indexer #comp/sidecar #concept/linking #scope/core #ai/instruct #task/domain/indexing #task/object/adapter #task/action/fix-foreign-key #task/state/end

---

### Script

#### Acts 1: Modify `SidecarIndexerAdapter` to use Late Binding
I will modify the adapter to compute the logical FQN of the target Python symbol instead of constructing its SURI directly.

~~~~~act
patch_file
packages/stitcher-lang-sidecar/src/stitcher/lang/sidecar/indexer.py
~~~~~
~~~~~python.old
from stitcher.spec import URIGeneratorProtocol, DocstringSerializerProtocol
from stitcher.spec.registry import LanguageAdapter
from stitcher.spec.index import SymbolRecord, ReferenceRecord
from stitcher.lang.sidecar.parser import parse_doc_references
from stitcher.lang.python.analysis.models import ReferenceType


class SidecarIndexerAdapter(LanguageAdapter):
~~~~~
~~~~~python.new
from stitcher.spec import URIGeneratorProtocol, DocstringSerializerProtocol
from stitcher.spec.registry import LanguageAdapter
from stitcher.spec.index import SymbolRecord, ReferenceRecord
from stitcher.lang.sidecar.parser import parse_doc_references
from stitcher.lang.python.analysis.models import ReferenceType
from stitcher.lang.python.analysis.utils import path_to_logical_fqn


class SidecarIndexerAdapter(LanguageAdapter):
~~~~~

~~~~~act
patch_file
packages/stitcher-lang-sidecar/src/stitcher/lang/sidecar/indexer.py
~~~~~
~~~~~python.old
        # 2. Determine paths
        # file_path passed here is relative to project root (physical path)
        # We need to determine the companion Python file path for references
        py_name = file_path.name.replace(".stitcher.yaml", ".py")
        py_path_rel = file_path.with_name(py_name)
        
        # 3. Parse references with location info using the helper
~~~~~
~~~~~python.new
        # 2. Determine paths
        # file_path passed here is relative to project root (physical path)
        # We need to determine the companion Python file path for references
        py_name = file_path.name.replace(".stitcher.yaml", ".py")
        py_path_rel = file_path.with_name(py_name)
        
        # Pre-calculate logical module FQN for linking
        logical_module_fqn = path_to_logical_fqn(py_path_rel.as_posix())

        # 3. Parse references with location info using the helper
~~~~~

~~~~~act
patch_file
packages/stitcher-lang-sidecar/src/stitcher/lang/sidecar/indexer.py
~~~~~
~~~~~python.old
            symbols.append(symbol)

            # --- Build Reference (Binding to Python) ---
            python_suri = f"py://{py_path_rel}#{fragment}"
            if fragment == "__doc__":
                python_suri = f"py://{py_path_rel}"
            
            ref = ReferenceRecord(
                source_file_id=None,
                target_fqn=None,
                target_id=python_suri,
                kind="doc_binding",
                lineno=lineno,
                col_offset=col_offset,
                end_lineno=lineno,
                end_col_offset=col_offset + len(fragment)
            )
            references.append(ref)

        return symbols, references
~~~~~
~~~~~python.new
            symbols.append(symbol)

            # --- Build Reference (Binding to Python) ---
            # Use Late Binding (FQN) instead of Early Binding (ID) to avoid Foreign Key constraint violations
            # if the Python file hasn't been indexed yet.
            target_fqn = f"{logical_module_fqn}.{fragment}"
            if fragment == "__doc__":
                target_fqn = logical_module_fqn
            
            ref = ReferenceRecord(
                source_file_id=None,
                target_fqn=target_fqn,
                target_id=None, # Leave NULL, let Linker resolve it
                kind="doc_binding",
                lineno=lineno,
                col_offset=col_offset,
                end_lineno=lineno,
                end_col_offset=col_offset + len(fragment)
            )
            references.append(ref)

        return symbols, references
~~~~~

### 下一步建议
This change should resolve the `FOREIGN KEY constraint failed` errors. I will re-run the tests to verify. Once the tests pass, the "Sidecar as First-Class Citizen" refactor will be complete and robust.
