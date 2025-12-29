You are absolutely right. The traceback and your `ripgrep` output clearly show the problem. The `NexusProtocol` has been purged from the `needle.spec` package, but the top-level `pyneedle` package, which serves as the public facade for the entire library, is still trying to import and re-export this ghost symbol.

This is a direct and expected consequence of our ongoing "scorched earth" policy against the old Nexus architecture. We must now clean up these dangling references to finalize this stage of the refactoring.

I will generate a plan to remove the obsolete `NexusProtocol` and `ResourceLoaderProtocol` from the public API of `pyneedle`.

## [WIP] fix(pyneedle): Remove obsolete Nexus/Loader protocol exports from public API

### 错误分析

The `stitcher --help` command fails with an `ImportError` because `packages/pyneedle/src/needle/__init__.py` is attempting to import `NexusProtocol` from `needle.spec`. This protocol no longer exists, as it was a core part of the now-removed Nexus architecture. The `ResourceLoaderProtocol` is also part of this obsolete architecture and should be removed at the same time for consistency.

This error is happening because the public API of the `pyneedle` package has not yet been updated to reflect the deep architectural changes from the Nexus model to the Operator model.

### 用户需求

Fix the `ImportError` by removing all references to the obsolete `NexusProtocol` and `ResourceLoaderProtocol` from the main `pyneedle` package's `__init__.py`, allowing the CLI to start.

### 评论

This cleanup is a crucial final step in the refactoring process. It purifies the public API of the `pyneedle` library, ensuring it accurately reflects the new, simpler "Operator-only" model. This prevents future confusion for developers and other systems consuming the library and makes the architecture self-consistent.

### 目标

Modify `packages/pyneedle/src/needle/__init__.py` to:
1.  Stop importing `NexusProtocol` and `ResourceLoaderProtocol`.
2.  Start importing the new `OperatorProtocol`.
3.  Update the `__all__` list to reflect these changes.

### 基本原理

As part of the migration to a functional Operator model, `NexusProtocol` and `ResourceLoaderProtocol` have been superseded by the unified `OperatorProtocol`. The fix requires updating the main package entry point to stop exporting the old protocols and start exporting the new one, bringing the public API in line with the implementation. I will use two precise `patch_file` operations to achieve this.

### 标签

#intent/fix #flow/ready #priority/critical #comp/build #concept/api #scope/core #ai/instruct #task/domain/refactor #task/object/overlay-nexus #task/action/remove #task/state/continue

---

### Script

#### Acts 1: Update protocol imports in the main pyneedle package

First, I'll fix the import statement itself, replacing the obsolete protocols with the new `OperatorProtocol`.

~~~~~act
patch_file
packages/pyneedle/src/needle/__init__.py
~~~~~
~~~~~python
from needle.spec import (
    NexusProtocol,
    ResourceLoaderProtocol,
    SemanticPointerProtocol,
    PointerSetProtocol,
)
~~~~~
~~~~~python
from needle.spec import (
    OperatorProtocol,
    SemanticPointerProtocol,
    PointerSetProtocol,
)
~~~~~

#### Acts 2: Update the `__all__` export list

Next, I'll update the `__all__` list to remove the old protocol names and add the new one, ensuring the package's public API is correct.

~~~~~act
patch_file
packages/pyneedle/src/needle/__init__.py
~~~~~
~~~~~python
__all__ = [
    "L",
    "SemanticPointer",
    "PointerSet",
    "nexus",
    "NexusProtocol",
    "ResourceLoaderProtocol",
    "SemanticPointerProtocol",
    "PointerSetProtocol",
]
~~~~~
~~~~~python
__all__ = [
    "L",
    "SemanticPointer",
    "PointerSet",
    "nexus",
    "OperatorProtocol",
    "SemanticPointerProtocol",
    "PointerSetProtocol",
]
~~~~~

### 下一步建议
With this, the `pyneedle` package itself should now be internally consistent. Please run `stitcher --help` again. It's possible we will now uncover an error in a downstream package like `stitcher-cli` that was explicitly importing `stitcher_nexus`. If so, we will address that next.
