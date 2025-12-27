# PyNeedle: 语义指针运行时

![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)

**一个现代化的工具包，用于在 Python 应用中将“语义”与“实现”解耦。**

[English](./README_PyNeedle.md) | [中文](./README_PyNeedle.zh.md)

---

## 什么是 PyNeedle?

PyNeedle 是一个小型而强大的库，旨在通过一个清晰、直观且类型安全的 API 来管理应用程序字符串、国际化 (i18n) 和其他可寻址资源。它用**语义指针 (Semantic Pointers)** 取代了“魔法字符串”——这些指针对象代表的是资源的*含义*，而非其具体的值。

您可以把它想象成在您应用程序资源的“干草堆”中寻找一根“针”(Needle)，但您不是通过字符串键来搜索，而是使用一个结构化的、类似代码的指针。

该库的核心是全局的 `L` 对象（“Location”或“Lexicon”的缩写）。您不再需要这样写：
```python
# 容易拼写错误，难以重构，没有自动补全
get_message("error.login.invalid_password")
```
而是这样写：
```python
# 流畅，可自动补全，易于重构，类型安全
nexus.get(L.error.login.invalid_password)
```

## 核心概念

PyNeedle 的架构非常简单，由三个主要部分组成：

1.  **语义指针 (`L`)**: 一个不可变对象，代表逻辑“语义宇宙”中的一个路径。它通过属性访问（`L.auth.login`）或类路径连接（`L.auth / "login"`）的方式流畅地创建。它充当所有资源的通用密钥。

2.  **资源加载器 (Resource Loader)**: 一个负责从数据源加载数据的组件。PyNeedle 内置了一个用于在项目中发现 `.json` 文件的 `FileSystemLoader`，以及一个用于测试或动态数据的 `MemoryLoader`。其接口协议非常简单，因此您可以轻松地为数据库、API 等编写自己的加载器。

3.  **Nexus**: 中央运行时枢纽。Nexus 接收一个加载器列表，并将语义指针解析为其最终的字符串值。它能智能地处理语言回退和资源覆盖，允许您以清晰的优先级顺序合并来自多个来源的资源。

`pyneedle` 包提供了一个“开箱即用”的全局 `nexus` 实例，它已预先配置了一个 `FileSystemLoader`，使得上手变得极其简单。

## 主要特性

-   **✨ 流畅且富有表现力的 API：** 使用 `L.user.profile.title` 自然地创建指针。
-   **➕ 指针代数：** 对指针和指针集执行强大的操作，如分布 (`L.user * {"name", "age"}`) 和连接 (`{L.a, L.b} / "end"`)。
-   **🌐 内置国际化 (I18n)：** Nexus 对语言解析、环境变量检测 (`NEEDLE_LANG`) 和优雅回退提供了一流的支持。
-   **📚 分层配置：** `OverlayNexus` 使用 `ChainMap` 策略来逻辑上覆盖资源文件。一个 `project/.stitcher/needle/en/override.json` 文件可以轻松覆盖来自 `library/needle/en/defaults.json` 的值，而无需物理合并文件。
-   **🔌 可扩展：** 轻松添加自定义的 `ResourceLoaderProtocol` 实现，以从任何数据源获取数据。
-   **📦 解耦的架构：** 项目被拆分为逻辑清晰的包（`pyneedle-spec`, `pyneedle-pointer`, `pyneedle-nexus`, `pyneedle-runtime`），促进了整洁的设计和可维护性。
-   **🔒 类型安全：** 当与它的配套工具 **Stitcher** 一起使用时，PyNeedle 能为您所有的资源启用完整的静态分析和自动补全。

## 快速入门

这个例子演示了使用内存加载器的核心功能。

```python
from needle import L, nexus
from needle.nexus import OverlayNexus, MemoryLoader

# 1. 为不同语言定义一些资源数据
resource_data = {
    "en": {
        "app.title": "My Awesome App",
        "user.greeting": "Welcome, {name}!",
    },
    "zh": {
        "app.title": "我的超棒应用",
    },
}

# 2. 用这些数据创建一个加载器
memory_loader = MemoryLoader(data=resource_data)

# 3. 用该加载器创建一个 Nexus 实例
#    (在实际应用中，您可能直接使用全局的 'nexus' 实例)
local_nexus = OverlayNexus(loaders=[memory_loader], default_lang="en")

# 4. 将指针解析为字符串
# --- 使用默认语言 (en) 解析 ---
title_en = local_nexus.get(L.app.title)
print(f"英文标题: {title_en}")
# 输出: 英文标题: My Awesome App

# --- 显式请求一个存在的语言 ---
title_zh = local_nexus.get(L.app.title, lang="zh")
print(f"中文标题: {title_zh}")
# 输出: 中文标题: 我的超棒应用

# --- 请求一个会回退到默认语言的键 ---
# 'user.greeting' 在 'zh' 中不存在，因此它会回退到 'en'
greeting_fallback = local_nexus.get(L.user.greeting, lang="zh")
print(f"回退的问候语: {greeting_fallback}")
# 输出: 回退的问候语: Welcome, {name}!

# --- 请求一个在任何地方都不存在的键 ---
# 它会优雅地回退到其自身的字符串表示（标识回退）
non_existent = local_nexus.get(L.app.non_existent_key)
print(f"不存在的键: {non_existent}")
# 输出: 不存在的键: app.non_existent_key
```

## 高级用法

### 指针代数

创建指针集合以进行强大且富有表现力的操作。

```python
from needle import L, PointerSet

# 定义一个基础指针集合
user_fields = PointerSet([L.user.name, L.user.email])

# 在集合的每个成员上广播一个后缀
form_labels = user_fields / "label"
# 结果: PointerSet({L.user.name.label, L.user.email.label})

# 使用乘法进行类似笛卡尔积的扩展
actions = {"read", "write"}
permissions = L.auth.user * actions
# 结果: PointerSet({L.auth.user.read, L.auth.user.write})
```

### 基于文件的加载

默认的全局 `nexus` 实例使用 `FileSystemLoader`。只需在您的项目根目录中创建以下目录结构：

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
    "app.title": "从文件加载的应用"
}
```

现在，您的应用程序代码将变得极其简单：

```python
# src/my_project/main.py
from needle import L, nexus

def main():
    # 全局 nexus 会自动查找并加载这些文件
    print(nexus.get(L.app.title))

# 输出: 从文件加载的应用
```

## 架构

PyNeedle 是一个由多个专注的包组成的 monorepo：

-   `pyneedle-spec`: 定义所有组件的核心 `Protocol` 接口。
-   `pyneedle-pointer`: `SemanticPointer` (`L`) 和 `PointerSet` 的标准实现。
-   `pyneedle-nexus`: 标准的 `OverlayNexus` 运行时实现和像 `MemoryLoader` 这样的加载器。
-   `pyneedle-runtime`: 提供 `FileSystemLoader` 并将其他组件组合成“开箱即用”的 `needle` 包。
-   `pyneedle`: 面向用户的发行版，将以上所有组件组合成一个单一、易于使用的命名空间包。

## 安装

由于本项目尚未发布到 PyPI，您需要从本地克隆进行安装。

1.  **克隆仓库：**
    ```bash
    git clone https://github.com/doucx/stitcher-python.git
    cd stitcher-python
    ```

2.  **创建并激活虚拟环境：**
    ```bash
    python -m venv .venv
    source .venv/bin/activate
    # 在 Windows 上: .venv\Scripts\activate
    ```

3.  **以可编辑模式安装项目及其开发依赖：**
    ```bash
    pip install -e .[dev]
    ```
    这将使 `needle` 包及其所有组件在您的环境中可用。

## 许可证

本项目采用 Apache License, Version 2.0 许可证。详情请参阅 [LICENSE](./LICENSE) 文件。
