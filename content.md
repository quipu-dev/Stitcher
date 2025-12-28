My apologies. This is the last echo of the old architecture. While I fixed the main application code, I neglected to update the corresponding unit tests that also imported from the now-deleted `stitcher.io` package. You are right to catch this.

## [WIP] fix: Update test imports to reflect IO component relocation

### 错误分析
1.  **根本原因**: `ModuleNotFoundError: No module named 'stitcher.io'`.
2.  **具体分析**: The unit tests `test_doc_manager.py` and `test_doc_overlay.py` still contain import statements pointing to the old `stitcher.io` package for `DocumentAdapter` and `YamlAdapter`. These components were correctly moved to `stitcher-common`, but the tests were not updated.

### 用户需求
Fix the final `ImportError` in the test suite by updating the import paths in the affected unit test files.

### 评论
This is the final, necessary cleanup step. Aligning the test suite's imports with the new code structure will resolve these errors and allow the test suite to pass, validating the success of the entire refactoring effort.

### 目标
1.  Modify `packages/stitcher-application/tests/unit/test_doc_manager.py` to import `DocumentAdapter` from `stitcher.common`.
2.  Modify `packages/stitcher-application/tests/unit/test_doc_overlay.py` to import `YamlAdapter` from `stitcher.common`.

### 基本原理
Test code is production code for the development process. It must accurately reflect the dependency graph of the code it is testing.

### 标签
#intent/fix #flow/ready #priority/critical #comp/tests #comp/common #scope/core #ai/instruct #task/domain/architecture #task/object/dependencies #task/action/fix-imports #task/state/end

---

### Script

#### Acts 1: Fix import in test_doc_manager.py

~~~~~act
patch_file
packages/stitcher-application/tests/unit/test_doc_manager.py
~~~~~
~~~~~python.old
from stitcher.spec import ModuleDef, FunctionDef, ClassDef, Attribute
from stitcher.app.services import DocumentManager
from stitcher.io import DocumentAdapter


class MockAdapter(DocumentAdapter):
~~~~~
~~~~~python.new
from stitcher.spec import ModuleDef, FunctionDef, ClassDef, Attribute
from stitcher.app.services import DocumentManager
from stitcher.common import DocumentAdapter


class MockAdapter(DocumentAdapter):
~~~~~

#### Acts 2: Fix import in test_doc_overlay.py

~~~~~act
patch_file
packages/stitcher-application/tests/unit/test_doc_overlay.py
~~~~~
~~~~~python.old
from pathlib import Path
from stitcher.spec import ModuleDef, FunctionDef
from stitcher.app.services import DocumentManager
from stitcher.io import YamlAdapter


def test_apply_docs_overlay(tmp_path: Path):
~~~~~
~~~~~python.new
from pathlib import Path
from stitcher.spec import ModuleDef, FunctionDef
from stitcher.app.services import DocumentManager
from stitcher.common import YamlAdapter


def test_apply_docs_overlay(tmp_path: Path):
~~~~~

### 下一步建议
The test suite should now pass without any import errors. This concludes the significant architectural refactoring. I will now create a `[COMMIT]` plan to bundle all these changes into a single, logical unit of work.
