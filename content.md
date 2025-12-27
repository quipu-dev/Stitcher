简要回答
好的，重构后的代码已经改变了 `Needle` 的核心术语（从 `lang` 转向 `domain`），并且引入了写回逻辑。

我现在将手动更新相关的 `.stitcher.yaml` 文件，以解决 `stitcher check` 报告的所有错误：包括签名不匹配、悬空定义（删除旧名称）以及补全缺失的新协议文档。

## [COMMIT] docs(needle): 同步文档以适配 Nexus Loader 化重构

### 用户需求
手动更新 YAML 文档，使其与代码中 `lang` -> `domain` 的变更及新功能的加入保持一致。

### 评论
这是一次必要的文档同步。通过手动更新而非 `hydrate`，我们可以确保文档描述的逻辑准确性（例如解释 `domain` 的泛化意义），而不仅仅是简单的字符串同步。

### 目标
1.  更新 `MemoryLoader` 文档，将 `lang` 改为 `domain`。
2.  更新 `OverlayNexus` 文档，添加 `load`, `put`, `locate` 的描述，并移除已删除的 `_resolve_lang`。
3.  添加 `WritableResourceLoaderProtocol` 及其方法的完整文档。
4.  更新 `NexusProtocol` 和 `ResourceLoaderProtocol` 的参数描述。

### 标签
#intent/document #flow/ready #priority/medium #comp/docs #scope/core #ai/instruct #task/domain/core-runtime #task/object/nexus-docs #task/action/update #task/state/end

---

### Script

#### Acts 1: 更新 MemoryLoader 文档

~~~~~act
write_file
packages/pyneedle-nexus/src/needle/nexus/loaders.stitcher.yaml
~~~~~
~~~~~yaml
"MemoryLoader": |-
  A resource loader that sources data from an in-memory dictionary.

  Ideal for testing, dynamic configuration, or runtime overrides.
"MemoryLoader.__init__": |-
  Initializes the loader with data.

  Args:
      data: A dictionary where keys are domain identifiers (e.g., lang codes)
            and values are dictionaries of FQN -> value.
            e.g., {"en": {"app.title": "My App"}}
"MemoryLoader.load": |-
  Loads resources for a specific domain from memory.
~~~~~

#### Acts 2: 更新 OverlayNexus 文档

~~~~~act
write_file
packages/pyneedle-nexus/src/needle/nexus/nexus.stitcher.yaml
~~~~~
~~~~~yaml
"OverlayNexus": |-
  Standard implementation of the Nexus protocol using a logical overlay strategy.

  It manages an ordered list of resource loaders and uses `collections.ChainMap`
  to create prioritized, logical views of resources without performing
  a physical merge. It also implements the Loader protocol, allowing it to be
  nested within other Nexus instances.
"OverlayNexus.__init__": |-
  Initializes the Nexus with a list of loaders.

  Args:
      loaders: A list of resource loaders. The order determines priority;
               loaders at the beginning of the list override those at the end.
      default_domain: The fallback domain to use if the target domain is not found.
"OverlayNexus._get_or_create_view": |-
  Lazily loads and caches the ChainMap view for a given domain.
"OverlayNexus._resolve_domain": |-
  Determines the current active domain based on environment variables and system settings.
"OverlayNexus.get": |-
  Resolves a semantic pointer to a string value with graceful fallback.
"OverlayNexus.load": |-
  Returns the overlay view for the requested domain. This enables a Nexus
  to act as a data source for another Nexus.
"OverlayNexus.locate": |-
  Finds the physical path for a resource by delegating to the first writable loader.
"OverlayNexus.put": |-
  Writes a value to a resource by delegating to the first writable loader.
"OverlayNexus.reload": |-
  Clears internal caches for one or all domains.
~~~~~

#### Acts 3: 更新核心协议 (Spec) 文档

~~~~~act
write_file
packages/pyneedle-spec/src/needle/spec/protocols.stitcher.yaml
~~~~~
~~~~~yaml
"NexusProtocol": |-
  Defines the contract for the runtime central hub (Nexus).
"NexusProtocol.get": |-
  Resolves a pointer or string key to its localized value.

  Args:
      pointer: The semantic key to look up.
      domain: Optional explicit domain override.

  Returns:
      The resolved string value, or the key itself if not found (Identity Fallback).
"NexusProtocol.reload": |-
  Clears internal caches and forces a reload of resources.

  Args:
      domain: If provided, only reload that specific domain.
            If None, reload all.
"PointerSetProtocol": |-
  Defines the contract for a set of Semantic Pointers (Ls).

  It represents a 'Semantic Domain' or 'Surface' rather than a single point.
"PointerSetProtocol.__add__": |-
  Operator '+': Broadcasts the add operation to all members.
"PointerSetProtocol.__iter__": |-
  Iterating over the set yields individual SemanticPointers.
"PointerSetProtocol.__mul__": |-
  Operator '*': Broadcasts a cartesian product operation.
"PointerSetProtocol.__or__": |-
  Operator '|': Unions two PointerSets.
"PointerSetProtocol.__truediv__": |-
  Operator '/': Broadcasts the join operation to all members of the set.
  Example: {L.a, L.b} / "end" -> {L.a.end, L.b.end}
"ResourceLoaderProtocol": |-
  Defines the contract for loading raw resource data.
"ResourceLoaderProtocol.load": |-
  Loads resources for a specific domain.

  Args:
      domain: The target domain (e.g., 'en', 'zh', 'dark_theme').

  Returns:
      A dictionary mapping Fully Qualified Names (FQNs) to values.
"SemanticPointerProtocol": |-
  Defines the contract for a Semantic Pointer (L).

  A Semantic Pointer is a recursive, immutable reference to a semantic location.
  It serves as the primary key for addressing resources in the Nexus.
"SemanticPointerProtocol.__add__": |-
  Operator '+': Joins the pointer with a string or another pointer.
  Example: L.auth + "login" -> L.auth.login
"SemanticPointerProtocol.__eq__": |-
  Pointers must be comparable with strings and other pointers.
"SemanticPointerProtocol.__getattr__": |-
  Creates a new pointer extended by the attribute name.
  Example: L.auth -> "auth"
"SemanticPointerProtocol.__hash__": |-
  Pointers must be hashable to be used as dictionary keys.
"SemanticPointerProtocol.__mul__": |-
  Operator '*': Distributes the pointer over a set of suffixes, creating a PointerSet.
  Example: L.auth * {"read", "write"} -> {L.auth.read, L.auth.write}
"SemanticPointerProtocol.__str__": |-
  Returns the fully qualified string representation of the pointer.
  Example: "auth.login.success"
"SemanticPointerProtocol.__truediv__": |-
  Operator '/': Joins the pointer with a string or another pointer (path-like syntax).
  Example: L.auth / "login" -> L.auth.login
"T_Pointer": |-
  A TypeVar used for covariant type hinting in the SemanticPointerProtocol.
"WritableResourceLoaderProtocol": |-
  Extends ResourceLoader with writing and location capabilities.
"WritableResourceLoaderProtocol.locate": |-
  Returns the physical path where a resource would be stored.
"WritableResourceLoaderProtocol.put": |-
  Persists a value for a specific pointer and domain.
~~~~~

### 下一步建议
同步完成后，你可以再次运行 `stitcher check`。如果一切正常，所有错误都应该消失，项目文档将处于完美同步状态。
