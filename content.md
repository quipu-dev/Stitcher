Excellent point. Your reasoning is perfectly aligned with the project's architectural principles.

Naming the package `stitcher-python-analysis` instead of a generic `stitcher-analysis` is a crucial distinction. It adheres to the **HFEA (High-Fidelity Engineering Axioms)** principle of "Strict分层与边界" (Strict Layering and Boundaries) by explicitly defining the component's domain (Python) from the outset. This avoids creating a generic "analysis" bucket that would inevitably become a monolith, and it paves a clear path for future language support (e.g., `stitcher-go-analysis`, `stitcher-rust-analysis`) without requiring any architectural changes.

This is a strategically sound decision that prevents `stitcher-python-adapter` from becoming a "god object" responsible for both high-level adaptation and low-level analysis tooling.

I will now generate the plan to create the skeleton for the `stitcher-python-analysis` package.

## [WIP] feat: Create stitcher-python-analysis package skeleton

### 用户需求

Create a new, language-specific package named `stitcher-python-analysis` to house shared Python code analysis logic (e.g., common LibCST tools), rather than overloading the existing `stitcher-python-adapter` package.

### 评论

This is a strategically sound decision that strongly adheres to the High-Fidelity Engineering Axioms (HFEA). By creating a dedicated, language-specific analysis package, we achieve several key architectural goals:
1.  **Prevents Scope Creep**: It stops `stitcher-python-adapter` from becoming a "god object" that mixes high-level adaptation logic with low-level AST/CST tooling.
2.  **Establishes Clear Boundaries**: It creates a clear separation of concerns. `stitcher-python-analysis` will provide foundational tools, while `stitcher-python-adapter` and `stitcher-refactor` will be consumers of those tools.
3.  **Future-Proofs the Architecture**: It sets a clear and scalable precedent for supporting other languages in the future (e.g., `stitcher-go-analysis`) without polluting the core namespace.

### 目标

1.  Create the complete directory structure for the new `stitcher-python-analysis` package.
2.  Create a basic `pyproject.toml` file with the necessary project metadata and initial dependencies.
3.  Establish the namespace package structure under `src/stitcher/analysis/python`.
4.  Create the corresponding test directory structure (`tests/unit`, `tests/integration`) in accordance with the monorepo testing architecture.

### 基本原理

We will use a single `run_command` with `mkdir -p` for maximum efficiency in creating the entire directory tree in one operation. `write_file` will then be used to create the initial `pyproject.toml` and `__init__.py` files. The structure will explicitly follow all established monorepo conventions, including the testing layout which prohibits `__init__.py` files in test directories.

### 标签

#intent/architect #flow/ready #priority/high #comp/build #scope/dx #ai/instruct #task/domain/architecture #task/object/analysis-layer #task/action/implementation #task/state/begin

---

### Script

#### Acts 1: Create package directory structure

First, we'll create all the necessary directories for the new package, including the source and test folders.

~~~~~act
run_command
~~~~~
~~~~~bash
mkdir -p packages/stitcher-python-analysis/src/stitcher/analysis/python
mkdir -p packages/stitcher-python-analysis/tests/unit
mkdir -p packages/stitcher-python-analysis/tests/integration
~~~~~

#### Acts 2: Create initial package files

Next, we will create the `pyproject.toml` file to define the new package and its dependencies, and the `__init__.py` to establish the namespace.

~~~~~act
write_file
packages/stitcher-python-analysis/pyproject.toml
~~~~~
~~~~~toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "stitcher-python-analysis"
version = "0.1.0"
description = "Shared Python code analysis toolkit for Stitcher (CST Visitors, etc.)."
requires-python = ">=3.10"
dependencies = [
    "stitcher-spec",
    "stitcher-common",
    "libcst",
    "griffe",
]

[tool.hatch.build.targets.wheel]
packages = ["src/stitcher"]

[tool.uv.sources]
stitcher-spec = { workspace = true }
stitcher-common = { workspace = true }
~~~~~

~~~~~act
write_file
packages/stitcher-python-analysis/src/stitcher/analysis/python/__init__.py
~~~~~
~~~~~python
# This must be the very first line to allow this package to coexist with other
# namespace packages in editable installs.
__path__ = __import__("pkgutil").extend_path(__path__, __name__)
~~~~~

### 下一步建议

The package skeleton is now in place. The next logical step, as outlined in the roadmap, is to begin migrating shared analysis logic into this new package.

I recommend we start by identifying the generic LibCST Visitor and Transformer base classes currently located in `stitcher-refactor` and create a new plan to move them into `stitcher-python-analysis`. This will be the first step in making our refactoring engine a consumer of this new, shared analysis layer.
