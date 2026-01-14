Excellent, thank you for providing the necessary file contents. I will now generate the plan to update the remaining import paths and finalize the `DocumentManager` migration.

This is the second step in our refactoring task, focusing on updating the logical references after the physical files have been moved.

## [WIP] refactor(arch): Finalize DocumentManager migration by updating imports

### 用户需求

Update all import paths for `DocumentManager` and `DocstringMerger` across the test suite and the `stitcher-stubgen` package to reflect their new location in the `stitcher-lang-sidecar` package.

### 评论

This is the final and crucial step for the component migration. Correcting these import paths ensures the codebase remains consistent and functional after the structural refactoring. It solidifies the new architectural boundary we've established.

### 目标

1.  Patch all affected test files in `stitcher-application/tests/unit/` to use the new import paths.
2.  Patch the source files in `stitcher-stubgen/src/stitcher/stubgen/` to use the new import paths.
3.  Complete the `DocumentManager` migration task, leaving the codebase in a consistent and compilable state.

### 基本原理

The previous plan moved the physical files. This plan updates the logical references (the `import` statements) to those files. This two-phase approach (physical move, then logical update) is a standard refactoring pattern that allows for clear, atomic changes. By completing this step, we ensure the system's dependency graph correctly reflects the intended architecture.

### 标签

#intent/refine #flow/ready #priority/high #comp/application #comp/lang-sidecar #comp/stubgen #comp/tests #concept/dependency #scope/core #ai/instruct #task/domain/architecture #task/object/component-relocation #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: Update Test File Imports

First, we'll patch the test files within `stitcher-application` to point to `stitcher.lang.sidecar`.

Updating `test_execution_planner.py`:
~~~~~act
patch_file
packages/stitcher-application/tests/unit/test_execution_planner.py
~~~~~
~~~~~python.old
from stitcher.services import DocumentManager, DocstringMerger
~~~~~
~~~~~python.new
from stitcher.lang.sidecar import DocumentManager, DocstringMerger
~~~~~

Updating `test_docstring_hybrid.py`:
~~~~~act
patch_file
packages/stitcher-application/tests/unit/test_docstring_hybrid.py
~~~~~
~~~~~python.old
from stitcher.services import DocumentManager
~~~~~
~~~~~python.new
from stitcher.lang.sidecar import DocumentManager
~~~~~

Updating `test_doc_manager_strategies.py`:
~~~~~act
patch_file
packages/stitcher-application/tests/unit/test_doc_manager_strategies.py
~~~~~
~~~~~python.old
from stitcher.services import DocumentManager
~~~~~
~~~~~python.new
from stitcher.lang.sidecar import DocumentManager
~~~~~

Updating `test_doc_manager.py`:
~~~~~act
patch_file
packages/stitcher-application/tests/unit/test_doc_manager.py
~~~~~
~~~~~python.old
from stitcher.services import DocumentManager
~~~~~
~~~~~python.new
from stitcher.lang.sidecar import DocumentManager
~~~~~

Updating `test_doc_overlay.py`:
~~~~~act
patch_file
packages/stitcher-application/tests/unit/test_doc_overlay.py
~~~~~
~~~~~python.old
from stitcher.services import DocumentManager
~~~~~
~~~~~python.new
from stitcher.lang.sidecar import DocumentManager
~~~~~

#### Acts 2: Update Stubgen Package Imports

Next, we'll update the imports within the `stitcher-stubgen` package.

Updating `runners.py`:
~~~~~act
patch_file
packages/stitcher-stubgen/src/stitcher/stubgen/runners.py
~~~~~
~~~~~python.old
from stitcher.services import (
    DocumentManager,
    ScannerService,
)
~~~~~
~~~~~python.new
from stitcher.services import (
    ScannerService,
)
from stitcher.lang.sidecar import DocumentManager
~~~~~

Updating `__init__.py`:
~~~~~act
patch_file
packages/stitcher-stubgen/src/stitcher/stubgen/__init__.py
~~~~~
~~~~~python.old
from stitcher.services import (
    ScannerService,
    DocumentManager,
)
~~~~~
~~~~~python.new
from stitcher.services import (
    ScannerService,
)
from stitcher.lang.sidecar import DocumentManager
~~~~~

### 下一步建议

The migration of `DocumentManager` is now complete. We have successfully relocated the component and updated all its call sites, strengthening the project's architecture.

The next logical step, as outlined in our analysis, is to **begin integrating Sidecar files into the indexing system**. This will involve:
1.  **Extending the database schema** to include a `doc_entries` table.
2.  **Implementing a new `LanguageAdapter`** within `stitcher-lang-sidecar` that can parse `.stitcher.yaml` files and populate this new table.
3.  **Updating the `FileIndexer`** to recognize and use this new adapter.

This will pave the way for the Zero-IO Path optimization in the `check` command. If you're ready, we can start by designing and implementing the schema change.
