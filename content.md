You've correctly identified the failures. My apologies, my previous implementation of the `SidecarUpdateMixin` was flawed in two critical ways:
1.  **Logical Error**: The `_calculate_fragments` method was too simplistic, incorrectly stripping parent context from nested symbols (like methods), which caused the `AssertionError` in the integration test.
2.  **Implementation Error**: The unit tests for the mixin were not updated to match the new method signature, nor were they rewritten to test the new SURI/Fragment-based logic, leading to a cascade of `TypeError` failures.

This is a failure to maintain "Architectural Incorruptibility". The tests have done their job by highlighting this flaw. I will now correct it.

## [WIP] fix: Correct SURI fragment logic and repair sidecar update tests

### 錯誤分析

1.  **Incorrect Fragment Calculation**: The primary logic error lies in `_calculate_fragments`. When renaming a method like `MyClass.old_method` to `MyClass.new_method`, my previous logic incorrectly calculated the new fragment as just `new_method` instead of the correct `MyClass.new_method`. This caused the SURI to be malformed and the integration test to fail.
2.  **Obsolete Unit Tests**: The unit tests for `SidecarUpdateMixin` were a relic of the old FQN-based system. They were calling the new method with an incorrect signature and asserting outdated logic. They must be completely rewritten to validate the new, bifurcated SURI vs. Fragment update strategies.

### 用户需求

Fix the failing tests by correcting the SURI generation logic for nested symbols and rewriting the unit tests for `SidecarUpdateMixin` to accurately reflect and validate the new identifier ontology.

### 评论

This is a perfect example of tests serving as an architectural safety net. The failures clearly pinpoint the logical gap in the implementation. By fixing the core fragment logic and rewriting the unit tests to be specifications for the *desired* SURI/Fragment behavior, we are not just patching an error; we are solidifying the new ontology and ensuring the refactoring engine's correctness.

### 目标

1.  **Fix Core Logic**: Correct the implementation of `_calculate_fragments` in `SidecarUpdateMixin` to properly handle nested symbols (e.g., `Class.method`).
2.  **Rewrite Unit Tests**: Replace the entire obsolete test file (`test_sidecar_update_mixin.py`) with a new set of tests that specifically validate:
    *   SURI key updates in JSON for symbol renames (including nested ones).
    *   SURI key updates in JSON for file moves.
    *   Fragment key updates in YAML for symbol renames.
    *   The **absence** of key changes in YAML for pure file moves.

### 基本原理

First, I will provide a new, correct implementation for `operations/base.py` using `write_file` for clarity. The new `_calculate_fragments` will correctly derive the full fragment (e.g., `MyClass.new_method`) by stripping the module prefix from the full FQN, rather than naively taking the last part of the name.

Second, I will completely replace the old unit test file with a new one. This new test file will be structured with distinct classes for testing JSON (SURI) updates and YAML (Fragment) updates, covering all critical rename and move scenarios. This ensures our test suite is no longer just "passing" but is actively enforcing the architectural principles we've established.

### 标签

#intent/fix #flow/ready #priority/critical #comp/engine #comp/tests #concept/state #scope/core #ai/instruct #task/domain/testing #task/object/identifier-ontology #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: Correct the `SidecarUpdateMixin` Logic

We will replace the entire `base.py` file with the corrected logic for fragment calculation.

~~~~~act
write_file
packages/stitcher-refactor/src/stitcher/refactor/operations/base.py
~~~~~
~~~~~python
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path

from stitcher.lang.python.analysis.utils import path_to_logical_fqn
from stitcher.lang.python.uri import SURIGenerator
from stitcher.refactor.engine.context import RefactorContext
from stitcher.refactor.engine.intent import RefactorIntent


class SidecarUpdateMixin:
    def _path_to_fqn(self, path: Path, search_paths: List[Path]) -> Optional[str]:
        base_path = None
        for sp in sorted(search_paths, key=lambda p: len(p.parts), reverse=True):
            try:
                path.relative_to(sp)
                base_path = sp
                break
            except ValueError:
                continue

        if base_path is None:
            return None

        rel_path = path.relative_to(base_path)
        return path_to_logical_fqn(rel_path.as_posix())

    def _calculate_fragments(
        self, module_fqn: Optional[str], old_fqn: str, new_fqn: str
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        Derives symbol fragments by stripping the module FQN prefix.
        """
        old_fragment = None
        if module_fqn and old_fqn.startswith(module_fqn + "."):
            old_fragment = old_fqn[len(module_fqn) + 1 :]
        elif module_fqn and old_fqn == module_fqn:
            old_fragment = None # Represents the module itself
        else:
            old_fragment = old_fqn # Fallback for non-nested names


        new_fragment = None
        # To calculate the new fragment, we need to know the *new* module FQN.
        # In a simple rename, it's the same. In a move, it's different.
        # Let's assume the new_fqn is correctly structured.
        new_module_prefix = ".".join(new_fqn.split(".")[:-1])
        if new_fqn.startswith(new_module_prefix + "."):
             new_fragment = ".".join(new_fqn.split(".")[1:]) if "." in new_fqn else new_fqn
             # This logic is still tricky. Let's simplify.
             # The FQN is composed of module + fragment.
             if module_fqn and new_fqn.startswith(module_fqn + "."):
                 new_fragment = new_fqn[len(module_fqn) + 1:]
             else:
                 # It might have been moved. The last part is a good guess for the new symbol name.
                 # But the parent part is also needed.
                 if old_fragment and "." in old_fragment: # e.g. Class.method
                     new_parent = ".".join(new_fqn.split(".")[:-1])
                     new_base_name = new_fqn.split(".")[-1]
                     old_base_name = old_fqn.split(".")[-1]

                     if new_base_name != old_base_name: # method rename
                        new_fragment = old_fragment.replace(old_base_name, new_base_name)
                     else: # class rename
                        new_fragment = new_fqn[len(module_fqn or "") + 1 :]

                 else:
                    if module_fqn and new_fqn.startswith(module_fqn + "."):
                         new_fragment = new_fqn[len(module_fqn)+1:]
                    else:
                         new_fragment = new_fqn

        # Corrected Logic: Strip the common prefix (module) to get the fragment.
        # This handles nested fragments correctly.
        if module_fqn:
             if old_fqn.startswith(module_fqn + "."):
                 old_fragment = old_fqn.split(module_fqn + ".", 1)[1]
             else:
                 old_fragment = old_fqn
             
             if new_fqn.startswith(module_fqn + "."):
                 new_fragment = new_fqn.split(module_fqn + ".", 1)[1]
             else:
                 new_fragment = new_fqn
        else: # No module context, treat FQNs as fragments
            old_fragment = old_fqn
            new_fragment = new_fqn


        return old_fragment, new_fragment


    def _update_sidecar_data(
        self,
        data: Dict[str, Any],
        sidecar_path: Path,
        module_fqn: Optional[str],
        old_fqn: str,
        new_fqn: str,
        old_file_path: Optional[str] = None,
        new_file_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Dispatcher for sidecar updates based on file type.
        """
        old_fragment, new_fragment = self._calculate_fragments(
            module_fqn, old_fqn, new_fqn
        )

        if sidecar_path.suffix == ".json":
            return self._update_json_data(
                data, old_file_path, new_file_path, old_fragment, new_fragment
            )
        elif sidecar_path.suffix in (".yaml", ".yml"):
            return self._update_yaml_data(data, old_fragment, new_fragment)

        return data

    def _update_json_data(
        self,
        data: Dict[str, Any],
        old_file_path: Optional[str],
        new_file_path: Optional[str],
        old_fragment: Optional[str],
        new_fragment: Optional[str],
    ) -> Dict[str, Any]:
        """
        Updates Signature JSON data where keys are SURIs (py://path#fragment).
        """
        new_data = {}
        modified = False

        for key, value in data.items():
            if not key.startswith("py://"):
                new_data[key] = value
                continue

            try:
                path, fragment = SURIGenerator.parse(key)
            except ValueError:
                new_data[key] = value
                continue

            path_changed = False
            fragment_changed = False

            if old_file_path and new_file_path and path == old_file_path:
                path = new_file_path
                path_changed = True

            if old_fragment and new_fragment and fragment:
                if fragment == old_fragment:
                    fragment = new_fragment
                    fragment_changed = True
                elif fragment.startswith(old_fragment + "."):
                    suffix = fragment[len(old_fragment) :]
                    fragment = new_fragment + suffix
                    fragment_changed = True

            if path_changed or fragment_changed:
                new_key = (
                    SURIGenerator.for_symbol(path, fragment)
                    if fragment
                    else SURIGenerator.for_file(path)
                )
                new_data[new_key] = value
                modified = True
            else:
                new_data[key] = value

        return new_data if modified else data

    def _update_yaml_data(
        self,
        data: Dict[str, Any],
        old_fragment: Optional[str],
        new_fragment: Optional[str],
    ) -> Dict[str, Any]:
        """
        Updates Doc YAML data where keys are Fragments (Short Names).
        """
        if not old_fragment or not new_fragment or old_fragment == new_fragment:
            return data

        new_data = {}
        modified = False

        for key, value in data.items():
            if key == old_fragment:
                new_data[new_fragment] = value
                modified = True
            elif key.startswith(old_fragment + "."):
                suffix = key[len(old_fragment) :]
                new_key = new_fragment + suffix
                new_data[new_key] = value
                modified = True
            else:
                new_data[key] = value

        return new_data if modified else data


class AbstractOperation(ABC):
    @abstractmethod
    def collect_intents(self, ctx: RefactorContext) -> List[RefactorIntent]:
        pass


~~~~~
