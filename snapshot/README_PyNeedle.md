# PyNeedle: The Semantic Pointer Runtime

![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)

**A modern toolkit for decoupling meaning from implementation in Python applications.**

[English](./README_PyNeedle.md) | [中文](./README_PyNeedle.zh.md)

---

## What is PyNeedle?

PyNeedle is a small, powerful library designed to manage application strings, internationalization (i18n), and other addressable resources through a clean, intuitive, and type-safe API. It replaces "magic strings" with **Semantic Pointers**—objects that represent the *meaning* of a resource, not its value.

Think of it as finding a "needle" in the "haystack" of your application's resources, but instead of searching by a string key, you use a structured, code-like pointer.

The core of the library is the global `L` object (short for "Location" or "Lexicon"). Instead of writing this:
```python
# Prone to typos, hard to refactor, no autocompletion
get_message("error.login.invalid_password")
```
You write this:
```python
# Fluent, autocompletes, refactorable, type-safe
nexus.get(L.error.login.invalid_password)
```

## Core Concepts

PyNeedle's architecture is simple and composed of three main parts:

1.  **Semantic Pointer (`L`)**: An immutable object that represents a path in a logical "semantic universe". It's created fluently using attribute access (`L.auth.login`) or path-like joins (`L.auth / "login"`). It acts as the universal key for all resources.

2.  **Resource Loader**: A component responsible for loading data from a source. PyNeedle includes a `FileSystemLoader` for discovering `.json` files in your project and a `MemoryLoader` for tests or dynamic data. The contract is simple, so you can easily write your own loader for databases, APIs, etc.

3.  **Nexus**: The central runtime hub. The Nexus takes a list of loaders and resolves Semantic Pointers into their final string values. It intelligently handles language fallbacks and overlays, allowing you to merge resources from multiple sources with a clear priority order.

The `pyneedle` package provides a "batteries-included" global `nexus` instance that is pre-configured with a `FileSystemLoader`, making it incredibly easy to get started.

## Key Features

-   **✨ Fluent & Expressive API:** Create pointers naturally with `L.user.profile.title`.
-   **➕ Pointer Algebra:** Perform powerful operations on pointers and sets of pointers, like distribution (`L.user * {"name", "age"}`) and concatenation (`{L.a, L.b} / "end"`).
-   **🌐 Built-in I18n:** The Nexus has first-class support for language resolution, environment variable detection (`NEEDLE_LANG`), and graceful fallbacks.
-   **📚 Layered Configuration:** The `OverlayNexus` uses a `ChainMap` strategy to logically overlay resource files. A `project/.stitcher/needle/en/override.json` can easily override values from a `library/needle/en/defaults.json` without merging files.
-   **🔌 Extensible:** Easily add custom `ResourceLoaderProtocol` implementations to fetch data from any source.
-   **📦 Decoupled Architecture:** The project is split into logical packages (`pyneedle-spec`, `pyneedle-pointer`, `pyneedle-nexus`, `pyneedle-runtime`), promoting clean design and maintainability.
-   **🔒 Type Safe:** When used with its companion tool, **Stitcher**, PyNeedle enables full static analysis and autocompletion for all your resources.

## Quick Start

This example demonstrates the core functionality using an in-memory loader.

```python
from needle import L, nexus
from needle.nexus import OverlayNexus, MemoryLoader

# 1. Define some resource data for different languages
resource_data = {
    "en": {
        "app.title": "My Awesome App",
        "user.greeting": "Welcome, {name}!",
    },
    "zh": {
        "app.title": "我的超棒应用",
    },
}

# 2. Create a loader with this data
memory_loader = MemoryLoader(data=resource_data)

# 3. Create a Nexus instance with the loader
#    (In a real app, you might just use the global 'nexus' instance)
local_nexus = OverlayNexus(loaders=[memory_loader], default_lang="en")

# 4. Resolve pointers to strings
# --- Resolving in the default language (en) ---
title_en = local_nexus.get(L.app.title)
print(f"English Title: {title_en}")
# Output: English Title: My Awesome App

# --- Explicitly requesting a language that exists ---
title_zh = local_nexus.get(L.app.title, lang="zh")
print(f"Chinese Title: {title_zh}")
# Output: Chinese Title: 我的超棒应用

# --- Requesting a key that falls back to the default language ---
# 'user.greeting' doesn't exist in 'zh', so it falls back to 'en'
greeting_fallback = local_nexus.get(L.user.greeting, lang="zh")
print(f"Fallback Greeting: {greeting_fallback}")
# Output: Fallback Greeting: Welcome, {name}!

# --- Requesting a key that doesn't exist anywhere ---
# It gracefully falls back to its own string representation (Identity Fallback)
non_existent = local_nexus.get(L.app.non_existent_key)
print(f"Non-existent Key: {non_existent}")
# Output: Non-existent Key: app.non_existent_key
```

## Advanced Usage

### Pointer Algebra

Create sets of pointers for powerful, expressive operations.

```python
from needle import L, PointerSet

# Define a set of base pointers
user_fields = PointerSet([L.user.name, L.user.email])

# Broadcast a suffix across the set
form_labels = user_fields / "label"
# Result: PointerSet({L.user.name.label, L.user.email.label})

# Use multiplication for cartesian-product-like expansion
actions = {"read", "write"}
permissions = L.auth.user * actions
# Result: PointerSet({L.auth.user.read, L.auth.user.write})
```

### File-Based Loading

The default global `nexus` instance uses a `FileSystemLoader`. Simply create the following directory structure in your project root:

```
my_project/
├── needle/
│   ├── en/
│   │   └── main.json
│   └── zh/
│       └── main.json
├── pyproject.toml
└── src/
    └── ...
```

**`needle/en/main.json`:**
```json
{
    "app.title": "My App from File"
}
```

Now, your application code is incredibly simple:

```python
# src/my_project/main.py
from needle import L, nexus

def main():
    # The global nexus automatically finds and loads the files
    print(nexus.get(L.app.title))

# Output: My App from File
```

## Architecture

PyNeedle is a monorepo composed of several focused packages:

-   `pyneedle-spec`: Defines the core `Protocol` interfaces for all components.
-   `pyneedle-pointer`: The standard implementation of `SemanticPointer` (`L`) and `PointerSet`.
-   `pyneedle-nexus`: The standard `OverlayNexus` runtime implementation and loaders like `MemoryLoader`.
-   `pyneedle-runtime`: Provides the `FileSystemLoader` and composes the other components into the batteries-included `needle` package.
-   `pyneedle`: The user-facing distribution that combines all of the above into a single, easy-to-use namespace package.

## Installation

Since this project is not yet available on PyPI, you need to install it from a local clone.

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/doucx/stitcher-python.git
    cd stitcher-python
    ```

2.  **Create and activate a virtual environment:**
    ```bash
    python -m venv .venv
    source .venv/bin/activate
    # On Windows: .venv\Scripts\activate
    ```

3.  **Install the project in editable mode with development dependencies:**
    ```bash
    pip install -e .[dev]
    ```
    This will make the `needle` package and all its components available in your environment.

## License

This project is licensed under the Apache License, Version 2.0. See the [LICENSE](./LICENSE) file for details.
