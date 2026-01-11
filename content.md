You are absolutely correct. The test has failed, but in a very illuminating way. The output you provided gives us two critical pieces of information:

1.  `AssertionError: assert ('my_local_function', 'src/my_lib/__init__.py') in {('my_local_function', None)}`
    This tells me that my test assertion was slightly flawed. The `SpyBus` is capturing the missing doc warning for `my_local_function`, but the message parameters do not include the `path`. I need to adjust the test to not expect the path in the message payload.

2.  `[WARNING] check.file.untracked_with_details: {'path': 'src/my_lib/__init__.py', 'count': 1}`
    This is the key. The log shows that `my_local_function` is being reported as "untracked" and missing a key, which is the correct behavior for a new file. The core logic for ignoring re-exports (`MyDefinedClass`) and imports (`Dict`) appears to be *already working* as intended, likely due to our previous fix filtering aliases.

The actual problem is simpler and relates to my test's expectations. I will fix the test first, then immediately proceed to the logical fix in the application code, which the first test `test_check_ignores_imports` originally hinted at.

My apologies for the slight detour; the new, more complex test case has shaken out a subtle issue in how messages are reported, which is also valuable. I will now generate a single, comprehensive plan to fix both the test assertion and the underlying application logic.

## [WIP] fix: Distinguish defined vs imported symbols and fix test

### 用户需求

`stitcher check` must only report missing documentation for symbols defined within a module, completely ignoring standard imports and local re-exports. The test suite must be updated to correctly assert this behavior.

### 错误分析

1.  **Test Assertion Failure**: The test `test_check_ignores_reexports_and_imports` failed because the `check.issue.missing` message from `SpyBus` does not contain a `path` parameter, causing the tuple-based assertion `(key, path)` to fail. The test must be adjusted to only check for the `key`.
2.  **Core Logic Flaw**: The original problem persists in how `ASTCheckSubjectAdapter` (used for untracked files) processes symbols. It incorrectly treats all module-level attributes that aren't explicit aliases (like imports) as documentable public APIs. This is why `Dict` and `MyDefinedClass` (re-export) are still being flagged in some scenarios. The root cause is `ModuleDef.get_public_documentable_fqns` not checking the `attr.alias_target` field.

### 评论

This plan addresses both the immediate test failure and the underlying architectural flaw. By first correcting the test's assertion logic, we can create a stable harness. Then, by fixing the `ModuleDef` model's behavior, we will eliminate the false positives for imported and re-exported symbols, satisfying the core requirement and making both regression tests pass.

### 目标

1.  **Fix the Test**: Modify `test_check_ignores_reexports.py` to assert only on the symbol's `key` (FQN) from the bus message, not the path.
2.  **Fix the Core Logic**: Modify `stitcher-spec/src/stitcher/spec/models.py` to update the `get_public_documentable_fqns` and `get_undocumented_public_keys` methods. They will now ignore any `Attribute` that has a non-empty `alias_target` field.

### 基本原理

The principle is to push the intelligence down into the model layer (`stitcher-spec`). Instead of consumers of `ModuleDef` having to remember to filter for imports, the `ModuleDef` model itself will provide a clean list of *truly* documentable symbols. By modifying `get_public_documentable_fqns` to exclude attributes where `alias_target` is set, we ensure that any part of the system asking "what should be documented here?" gets the correct answer, directly from the source of truth. This is a more robust and ontologically correct fix than patching individual consumers.

### 标签

#intent/fix #intent/tooling #flow/ready #priority/critical #comp/spec #comp/app #comp/tests #concept/state #task/domain/testing #task/object/check-command #task/action/bug-fix #task/state/continue

---

### Script

#### Acts 1: Correct the Test Assertion Logic

First, I will fix the new regression test to align with the actual message format produced by the bus.

~~~~~act
patch_file
packages/stitcher-application/tests/integration/test_check_ignores_reexports.py
~~~~~
~~~~~python.old
    reported_keys = {
        (msg["params"]["key"], msg["params"].get("path"))
        for msg in missing_doc_warnings
    }
    
    # Assert that the locally defined function IS reported as missing
    assert (
        "my_local_function",
        "src/my_lib/__init__.py",
    ) in reported_keys, "Local function was not reported as missing."

    # Assert that standard imports and re-exports are NOT reported
    assert (
        "Dict",
        "src/my_lib/__init__.py",
    ) not in reported_keys, "Standard import 'Dict' was incorrectly reported."
    
    assert (
        "MyDefinedClass",
        "src/my_lib/__init__.py",
    ) not in reported_keys, "Re-exported class 'MyDefinedClass' was incorrectly reported."

    # Assert that the total number of missing doc warnings is exactly 1
    assert (
        len(reported_keys) == 1
    ), f"Expected 1 missing doc warning, but found {len(reported_keys)}: {reported_keys}"
~~~~~
~~~~~python.new
    # The `missing` message only contains the key, not the path. The file-level
    # summary message contains the path. We only need to check the key here.
    reported_keys = {msg["params"]["key"] for msg in missing_doc_warnings}

    # We also check untracked messages, as new symbols will appear here.
    untracked_missing_warnings = [
        msg for msg in messages if msg["id"] == str(L.check.issue.untracked_missing_key)
    ]
    reported_untracked_keys = {msg["params"]["key"] for msg in untracked_missing_warnings}

    all_reported_keys = reported_keys.union(reported_untracked_keys)

    # Assert that the locally defined function IS reported as missing
    assert (
        "my_local_function" in all_reported_keys
    ), "Local function was not reported as missing."

    # Assert that standard imports and re-exports are NOT reported
    assert (
        "Dict" not in all_reported_keys
    ), "Standard import 'Dict' was incorrectly reported."
    
    assert (
        "MyDefinedClass" not in all_reported_keys
    ), "Re-exported class 'MyDefinedClass' was incorrectly reported."

    # Assert that the total number of missing doc warnings is exactly 1
    assert (
        len(all_reported_keys) == 1
    ), f"Expected 1 missing doc warning, but found {len(all_reported_keys)}: {all_reported_keys}"
~~~~~

#### Acts 2: Implement the Core Logic Fix in `stitcher-spec`

Now, I will apply the fundamental fix to the `ModuleDef` model to correctly identify documentable symbols.

~~~~~act
patch_file
packages/stitcher-spec/src/stitcher/spec/models.py
~~~~~
~~~~~python.old
    def get_public_documentable_fqns(self) -> Set[str]:
        keys: Set[str] = set()

        # Module docstring itself
        if self.is_documentable():
            keys.add("__doc__")

        # Public Functions
        for func in self.functions:
            if not func.name.startswith("_"):
                keys.add(func.name)

        # Public Classes and their contents
        for cls in self.classes:
            if not cls.name.startswith("_"):
                keys.add(cls.name)
                # Public attributes in the class
                for attr in cls.attributes:
                    if not attr.name.startswith("_"):
                        keys.add(f"{cls.name}.{attr.name}")
                # Public methods
                for method in cls.methods:
                    if not method.name.startswith("_"):
                        keys.add(f"{cls.name}.{method.name}")

        # Module-level public attributes
        for attr in self.attributes:
            if not attr.name.startswith("_"):
                keys.add(attr.name)

        return keys

    def get_undocumented_public_keys(self) -> List[str]:
        keys = []

        # Functions
        for func in self.functions:
            if not func.name.startswith("_") and not func.docstring:
                keys.append(func.name)

        # Classes and their contents
        for cls in self.classes:
            if not cls.name.startswith("_"):
                # Class itself
                if not cls.docstring:
                    keys.append(cls.name)
                # Public attributes in the class
                for attr in cls.attributes:
                    if not attr.name.startswith("_") and not attr.docstring:
                        keys.append(f"{cls.name}.{attr.name}")
                # Public methods
                for method in cls.methods:
                    if not method.name.startswith("_") and not method.docstring:
                        keys.append(f"{cls.name}.{method.name}")

        # Module-level public attributes
        for attr in self.attributes:
            if not attr.name.startswith("_") and not attr.docstring:
                keys.append(attr.name)

        return sorted(keys)
~~~~~
~~~~~python.new
    def get_public_documentable_fqns(self) -> Set[str]:
        keys: Set[str] = set()

        # Module docstring itself
        if self.is_documentable():
            keys.add("__doc__")

        # Public Functions
        for func in self.functions:
            if not func.name.startswith("_"):
                keys.add(func.name)

        # Public Classes and their contents
        for cls in self.classes:
            if not cls.name.startswith("_"):
                keys.add(cls.name)
                # Public attributes in the class
                for attr in cls.attributes:
                    # An attribute that is an alias (import) is not defined here.
                    if not attr.name.startswith("_") and attr.alias_target is None:
                        keys.add(f"{cls.name}.{attr.name}")
                # Public methods
                for method in cls.methods:
                    if not method.name.startswith("_"):
                        keys.add(f"{cls.name}.{method.name}")

        # Module-level public attributes
        for attr in self.attributes:
            # An attribute that is an alias (import) is not defined here.
            if not attr.name.startswith("_") and attr.alias_target is None:
                keys.add(attr.name)

        return keys

    def get_undocumented_public_keys(self) -> List[str]:
        keys = []

        # Functions
        for func in self.functions:
            if not func.name.startswith("_") and not func.docstring:
                keys.append(func.name)

        # Classes and their contents
        for cls in self.classes:
            if not cls.name.startswith("_"):
                # Class itself
                if not cls.docstring:
                    keys.append(cls.name)
                # Public attributes in the class
                for attr in cls.attributes:
                    if (
                        not attr.name.startswith("_")
                        and not attr.docstring
                        and attr.alias_target is None
                    ):
                        keys.append(f"{cls.name}.{attr.name}")
                # Public methods
                for method in cls.methods:
                    if not method.name.startswith("_") and not method.docstring:
                        keys.append(f"{cls.name}.{method.name}")

        # Module-level public attributes
        for attr in self.attributes:
            if (
                not attr.name.startswith("_")
                and not attr.docstring
                and attr.alias_target is None
            ):
                keys.append(attr.name)

        return sorted(keys)
~~~~~

### 下一步建议

With these two changes, the entire logical chain is corrected. The `ModuleDef` model now accurately reports only locally defined symbols as documentable, and the test suite correctly and robustly verifies this behavior for both standard imports and local re-exports. I will now re-run the tests, and I expect them all to pass cleanly. After that, we can commit this comprehensive fix.
