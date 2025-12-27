简要回答
你的方案非常扎实，它通过“组合模式 (Composite Pattern)”和“读写分离 (CQRS)”两个核心重构，将 `Needle` 从一个单一的本地化工具升维成了通用的语义资源网格。这完全符合 Stitcher “缝合一切”的哲学。

我将执行此重构，核心路径为：**升级协议定义** -> **重构 Nexus 内核** -> **升级运行时 Loader** -> **适配上层应用**。

## [WIP] refactor(core): 实现 Nexus Loader 化架构与读写分离协议

### 错误分析
无（新功能重构）

### 用户需求
1.  **Nexus Loader 化**: `Nexus` 需实现 `ResourceLoaderProtocol`，使其可被递归组合。
2.  **概念升维**: 将 `lang` 参数泛化为 `domain`，支持更广泛的资源上下文。
3.  **读写分离**: 引入 `WritableResourceLoaderProtocol`，解决 `put` 操作的权责归属问题。
4.  **写回委托**: `Nexus.put` 应自动委托给优先级最高的可写 Loader。

### 评论
这是一次架构级的“升维”重构。虽然代码变动涉及底层协议，但由于采用了接口隔离原则，对上层业务逻辑的侵入性可控。将 `lang` 重命名为 `domain` 是一次这就“正名”，虽然繁琐但对长期维护至关重要。

### 目标
1.  在 `pyneedle-spec` 中定义 `WritableResourceLoaderProtocol` 并更新 `ResourceLoaderProtocol`。
2.  重构 `pyneedle-nexus`，使 `OverlayNexus` 实现上述协议，并支持递归组合与写回。
3.  升级 `pyneedle-runtime` 中的 `FileSystemLoader` 和 `JsonHandler` 以支持 `put` 和 `locate`。
4.  更新所有受影响的测试用例和上层调用（`stitcher-cli`, `stitcher-common`）。

### 基本原理
通过让 `Nexus` 自身成为一个 `Loader`，我们消除了“容器”与“内容”的边界，使得资源拓扑结构可以无限分形扩展。引入 `domain` 概念解除了对“语言”的语义绑定，使得该架构可以用于主题、环境配置等任何分片场景。

### 标签
#intent/refine #flow/ready #priority/high #comp/runtime #concept/state #scope/core #ai/instruct #task/domain/core-runtime #task/object/nexus-loader #task/action/refactor #task/state/begin

---

### Script

#### Acts 1: 升级核心协议 (Spec)
我们将首先修改 `pyneedle-spec`，引入写协议并将 `lang` 重命名为 `domain`。

~~~~~act
patch_file
packages/pyneedle-spec/src/needle/spec/protocols.py
~~~~~
~~~~~python.old
class ResourceLoaderProtocol(Protocol):
    def load(self, lang: str) -> Dict[str, Any]: ...


class NexusProtocol(Protocol):
    def get(
        self, pointer: Union[str, SemanticPointerProtocol], lang: str | None = None
    ) -> str: ...

    def reload(self, lang: str | None = None) -> None: ...
~~~~~
~~~~~python.new
from pathlib import Path


class ResourceLoaderProtocol(Protocol):
    def load(self, domain: str) -> Dict[str, Any]: ...


class WritableResourceLoaderProtocol(ResourceLoaderProtocol, Protocol):
    def put(
        self, pointer: Union[str, SemanticPointerProtocol], value: Any, domain: str
    ) -> bool: ...

    def locate(
        self, pointer: Union[str, SemanticPointerProtocol], domain: str
    ) -> Path: ...


class NexusProtocol(ResourceLoaderProtocol, Protocol):
    def get(
        self, pointer: Union[str, SemanticPointerProtocol], domain: str | None = None
    ) -> str: ...

    def reload(self, domain: str | None = None) -> None: ...
~~~~~

#### Acts 2: 更新 MemoryLoader
更新 `pyneedle-nexus` 中的 `MemoryLoader` 以适配新的协议签名。

~~~~~act
patch_file
packages/pyneedle-nexus/src/needle/nexus/loaders.py
~~~~~
~~~~~python.old
class MemoryLoader(ResourceLoaderProtocol):
    def __init__(self, data: Dict[str, Dict[str, Any]]):
        self._data = data

    def load(self, lang: str) -> Dict[str, Any]:
        # Return a copy to simulate I/O snapshotting and prevent
        # ChainMap from reflecting dynamic changes in source data immediately.
        return self._data.get(lang, {}).copy()
~~~~~
~~~~~python.new
class MemoryLoader(ResourceLoaderProtocol):
    def __init__(self, data: Dict[str, Dict[str, Any]]):
        self._data = data

    def load(self, domain: str) -> Dict[str, Any]:
        # Return a copy to simulate I/O snapshotting and prevent
        # ChainMap from reflecting dynamic changes in source data immediately.
        return self._data.get(domain, {}).copy()
~~~~~

#### Acts 3: 重构 OverlayNexus
这是核心变更。`OverlayNexus` 将实现 `load` (返回层叠视图) 和 `put` (写回委托)。

~~~~~act
patch_file
packages/pyneedle-nexus/src/needle/nexus/nexus.py
~~~~~
~~~~~python.old
class OverlayNexus(NexusProtocol):
    def __init__(self, loaders: List[ResourceLoaderProtocol], default_lang: str = "en"):
        self.loaders = loaders
        self.default_lang = default_lang
        self._views: Dict[str, ChainMap[str, Any]] = {}

    def _get_or_create_view(self, lang: str) -> ChainMap[str, Any]:
        if lang not in self._views:
            # Trigger load() on all loaders for the requested language.
            # The list comprehension creates a list of dictionaries.
            # The order of `self.loaders` is preserved, which is crucial for ChainMap.
            maps = [loader.load(lang) for loader in self.loaders]
            self._views[lang] = ChainMap(*maps)
        return self._views[lang]

    def _resolve_lang(self, explicit_lang: Optional[str] = None) -> str:
        if explicit_lang:
            return explicit_lang

        # Priority 1: NEEDLE_LANG (new standard)
        needle_lang = os.getenv("NEEDLE_LANG")
        if needle_lang:
            return needle_lang

        # Priority 2: STITCHER_LANG (legacy compatibility)
        stitcher_lang = os.getenv("STITCHER_LANG")
        if stitcher_lang:
            return stitcher_lang

        system_lang = os.getenv("LANG")
        if system_lang:
            return system_lang.split("_")[0].split(".")[0].lower()

        return self.default_lang

    def get(
        self, pointer: Union[str, SemanticPointerProtocol], lang: Optional[str] = None
    ) -> str:
        key = str(pointer)
        target_lang = self._resolve_lang(lang)

        # 1. Try target language
        target_view = self._get_or_create_view(target_lang)
        value = target_view.get(key)
        if value is not None:
            return str(value)

        # 2. Try default language (if different)
        if target_lang != self.default_lang:
            default_view = self._get_or_create_view(self.default_lang)
            value = default_view.get(key)
            if value is not None:
                return str(value)

        # 3. Fallback to Identity
        return key

    def reload(self, lang: Optional[str] = None) -> None:
        if lang:
            self._views.pop(lang, None)
        else:
            self._views.clear()
~~~~~
~~~~~python.new
from pathlib import Path
from needle.spec import WritableResourceLoaderProtocol


class OverlayNexus(NexusProtocol):
    def __init__(
        self, loaders: List[ResourceLoaderProtocol], default_domain: str = "en"
    ):
        self.loaders = loaders
        self.default_domain = default_domain
        self._views: Dict[str, ChainMap[str, Any]] = {}

    def load(self, domain: str) -> Dict[str, Any]:
        """
        Implementation of ResourceLoaderProtocol.
        Returns the overlay view (ChainMap) as a dictionary-like object.
        This allows a Nexus to be used as a loader inside another Nexus.
        """
        return self._get_or_create_view(domain)

    def _get_or_create_view(self, domain: str) -> ChainMap[str, Any]:
        if domain not in self._views:
            # Trigger load() on all loaders for the requested domain.
            # The order of `self.loaders` is preserved (Priority: First > Last)
            maps = [loader.load(domain) for loader in self.loaders]
            self._views[domain] = ChainMap(*maps)
        return self._views[domain]

    def _resolve_domain(self, explicit_domain: Optional[str] = None) -> str:
        if explicit_domain:
            return explicit_domain

        # Priority 1: NEEDLE_LANG (renamed concept mapping)
        needle_domain = os.getenv("NEEDLE_LANG")
        if needle_domain:
            return needle_domain

        # Priority 2: STITCHER_LANG (legacy compatibility)
        stitcher_domain = os.getenv("STITCHER_LANG")
        if stitcher_domain:
            return stitcher_domain

        system_domain = os.getenv("LANG")
        if system_domain:
            return system_domain.split("_")[0].split(".")[0].lower()

        return self.default_domain

    def get(
        self,
        pointer: Union[str, SemanticPointerProtocol],
        domain: Optional[str] = None,
    ) -> str:
        key = str(pointer)
        target_domain = self._resolve_domain(domain)

        # 1. Try target domain
        target_view = self._get_or_create_view(target_domain)
        value = target_view.get(key)
        if value is not None:
            return str(value)

        # 2. Try default domain (if different)
        if target_domain != self.default_domain:
            default_view = self._get_or_create_view(self.default_domain)
            value = default_view.get(key)
            if value is not None:
                return str(value)

        # 3. Fallback to Identity
        return key

    def reload(self, domain: Optional[str] = None) -> None:
        if domain:
            self._views.pop(domain, None)
        else:
            self._views.clear()

    # --- Write Support ---

    def _get_writable_loader(self) -> Optional[WritableResourceLoaderProtocol]:
        for loader in self.loaders:
            if isinstance(loader, WritableResourceLoaderProtocol):
                return loader
        return None

    def put(
        self,
        pointer: Union[str, SemanticPointerProtocol],
        value: Any,
        domain: Optional[str] = None,
    ) -> bool:
        """
        Delegates the write operation to the highest priority WritableLoader.
        """
        target_domain = self._resolve_domain(domain)
        loader = self._get_writable_loader()
        if not loader:
            return False

        success = loader.put(pointer, value, target_domain)
        if success:
            # If write succeeded, we must invalidate the cache for this domain
            # so subsequent reads reflect the change.
            self.reload(target_domain)
        return success

    def locate(
        self,
        pointer: Union[str, SemanticPointerProtocol],
        domain: Optional[str] = None,
    ) -> Optional[Path]:
        """
        Delegates location finding to the highest priority WritableLoader.
        """
        target_domain = self._resolve_domain(domain)
        loader = self._get_writable_loader()
        if not loader:
            return None
        return loader.locate(pointer, target_domain)
~~~~~

#### Acts 4: 升级 Runtime Loader (FS & Json)
更新 `pyneedle-runtime` 以支持 `domain` 参数，并为 `JsonHandler` 和 `FileSystemLoader` 实现写能力。

~~~~~act
patch_file
packages/pyneedle-runtime/src/needle/loaders/protocols.py
~~~~~
~~~~~python.old
class FileHandlerProtocol(Protocol):
    def match(self, path: Path) -> bool: ...

    def load(self, path: Path) -> Dict[str, Any]: ...
~~~~~
~~~~~python.new
class FileHandlerProtocol(Protocol):
    def match(self, path: Path) -> bool: ...

    def load(self, path: Path) -> Dict[str, Any]: ...

    def save(self, path: Path, data: Dict[str, Any]) -> bool: ...
~~~~~

~~~~~act
patch_file
packages/pyneedle-runtime/src/needle/loaders/json_handler.py
~~~~~
~~~~~python.old
class JsonHandler(FileHandlerProtocol):
    def match(self, path: Path) -> bool:
        return path.suffix.lower() == ".json"

    def load(self, path: Path) -> Dict[str, Any]:
        try:
            with path.open("r", encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, dict) else {}
        except (json.JSONDecodeError, OSError):
            return {}
~~~~~
~~~~~python.new
class JsonHandler(FileHandlerProtocol):
    def match(self, path: Path) -> bool:
        return path.suffix.lower() == ".json"

    def load(self, path: Path) -> Dict[str, Any]:
        try:
            with path.open("r", encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, dict) else {}
        except (json.JSONDecodeError, OSError):
            return {}

    def save(self, path: Path, data: Dict[str, Any]) -> bool:
        try:
            # Ensure directory exists
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, sort_keys=True, ensure_ascii=False)
            return True
        except OSError:
            return False
~~~~~

~~~~~act
patch_file
packages/pyneedle-runtime/src/needle/loaders/fs_loader.py
~~~~~
~~~~~python.old
class FileSystemLoader(ResourceLoaderProtocol):
    def __init__(
        self,
        roots: Optional[List[Path]] = None,
        handlers: Optional[List[FileHandlerProtocol]] = None,
    ):
        self.handlers = handlers or [JsonHandler()]
        self.roots = roots or [self._find_project_root()]

    def _find_project_root(self, start_dir: Optional[Path] = None) -> Path:
        current_dir = (start_dir or Path.cwd()).resolve()
        # Stop at filesystem root
        while current_dir.parent != current_dir:
            if (current_dir / "pyproject.toml").is_file() or (
                current_dir / ".git"
            ).is_dir():
                return current_dir
            current_dir = current_dir.parent
        return start_dir or Path.cwd()

    def add_root(self, path: Path):
        if path not in self.roots:
            self.roots.insert(0, path)

    def load(self, lang: str) -> Dict[str, Any]:
        merged_registry: Dict[str, str] = {}

        for root in self.roots:
            # Path Option 1: .stitcher/needle/<lang> (for project-specific overrides)
            hidden_path = root / ".stitcher" / "needle" / lang
            if hidden_path.is_dir():
                merged_registry.update(self._load_directory(hidden_path))

            # Path Option 2: needle/<lang> (for packaged assets)
            asset_path = root / "needle" / lang
            if asset_path.is_dir():
                merged_registry.update(self._load_directory(asset_path))

        return merged_registry

    def _load_directory(self, root_path: Path) -> Dict[str, str]:
        registry: Dict[str, str] = {}
        for dirpath, _, filenames in os.walk(root_path):
            for filename in filenames:
                file_path = Path(dirpath) / filename
                for handler in self.handlers:
                    if handler.match(file_path):
                        content = handler.load(file_path)
                        # Ensure all values are strings for FQN registry
                        for key, value in content.items():
                            registry[str(key)] = str(value)
                        break  # Stop after first matching handler
        return registry
~~~~~
~~~~~python.new
from needle.spec import WritableResourceLoaderProtocol

# ... imports ...


class FileSystemLoader(WritableResourceLoaderProtocol):
    def __init__(
        self,
        roots: Optional[List[Path]] = None,
        handlers: Optional[List[FileHandlerProtocol]] = None,
    ):
        self.handlers = handlers or [JsonHandler()]
        self.roots = roots or [self._find_project_root()]

    def _find_project_root(self, start_dir: Optional[Path] = None) -> Path:
        current_dir = (start_dir or Path.cwd()).resolve()
        # Stop at filesystem root
        while current_dir.parent != current_dir:
            if (current_dir / "pyproject.toml").is_file() or (
                current_dir / ".git"
            ).is_dir():
                return current_dir
            current_dir = current_dir.parent
        return start_dir or Path.cwd()

    def add_root(self, path: Path):
        if path not in self.roots:
            self.roots.insert(0, path)

    def load(self, domain: str) -> Dict[str, Any]:
        merged_registry: Dict[str, str] = {}

        for root in self.roots:
            # Path Option 1: .stitcher/needle/<domain> (for project-specific overrides)
            hidden_path = root / ".stitcher" / "needle" / domain
            if hidden_path.is_dir():
                merged_registry.update(self._load_directory(hidden_path))

            # Path Option 2: needle/<domain> (for packaged assets)
            asset_path = root / "needle" / domain
            if asset_path.is_dir():
                merged_registry.update(self._load_directory(asset_path))

        return merged_registry

    def _load_directory(self, root_path: Path) -> Dict[str, str]:
        registry: Dict[str, str] = {}
        for dirpath, _, filenames in os.walk(root_path):
            for filename in filenames:
                file_path = Path(dirpath) / filename
                for handler in self.handlers:
                    if handler.match(file_path):
                        content = handler.load(file_path)
                        # Ensure all values are strings for FQN registry
                        for key, value in content.items():
                            registry[str(key)] = str(value)
                        break  # Stop after first matching handler
        return registry

    def _get_writable_path(self, pointer: str, domain: str) -> Path:
        """
        Determines the physical file path for a given pointer.
        Prioritizes the first root (highest priority) and .stitcher hidden dir.
        Strategy: Use FQN parts to build path.
        e.g., L.auth.login.success -> auth/login.json
        """
        root = self.roots[0]  # Write to highest priority root
        parts = pointer.split(".")
        
        # Simple heuristic: Use the first part as directory, second as file, rest as keys
        # But wait, our current physical layout logic in SST (Stitcher SST) is:
        # needle/<lang>/<category>/<namespace>.json
        # L.cli.ui.welcome -> needle/en/cli/ui.json -> key: welcome
        # This requires pointer algebra knowledge or a heuristic.
        
        # For this MVP implementation, let's use a flat fallback or a simple folder strategy.
        # Let's assume: <domain>/<p1>/<p2>.json if len > 2
        # else <domain>/<p1>.json
        
        base_dir = root / ".stitcher" / "needle" / domain
        
        if len(parts) >= 3:
             # L.cli.ui.welcome -> cli/ui.json
             relative = Path(*parts[:2]).with_suffix(".json")
        elif len(parts) == 2:
             # L.cli.help -> cli.json
             relative = Path(parts[0]).with_suffix(".json")
        else:
             # L.error -> __init__.json (fallback)
             relative = Path("__init__.json")
             
        return base_dir / relative

    def locate(self, pointer: Union[str, Any], domain: str) -> Path:
        return self._get_writable_path(str(pointer), domain)

    def put(self, pointer: Union[str, Any], value: Any, domain: str) -> bool:
        key = str(pointer)
        target_path = self.locate(key, domain)
        
        # We need to find the specific handler for .json (default)
        handler = self.handlers[0] # Assume JSON for MVP writing
        
        # Load existing (if any)
        data = {}
        if target_path.exists():
            data = handler.load(target_path)
            
        # Update
        # Note: This simple put assumes the file structure matches the key structure 
        # based on _get_writable_path. 
        # But wait, load() flattens everything. 
        # If we write { "cli.ui.welcome": "Hi" } into cli/ui.json, that's fine for now.
        # FQN keys in files are valid per SST.
        data[key] = str(value)
        
        return handler.save(target_path, data)
~~~~~

#### Acts 5: 修复 Tests
更新测试文件中的 `lang` 参数。

~~~~~act
patch_file
packages/pyneedle-nexus/tests/test_nexus.py
~~~~~
~~~~~python.old
def test_get_language_specificity_and_fallback(nexus_instance: OverlayNexus):
    # 1. Specific language (zh) is preferred when key exists
    assert nexus_instance.get("app.title", lang="zh") == "我的应用 (高优先级)"

    # 2. Key missing in 'zh', falls back to default 'en'
    # Note: loader 2 has 'app.welcome' in 'zh', so it should be found there.
    # The previous test comment was slightly confusing.
    # ChainMap for 'zh' combines loader1(zh) and loader2(zh).
    # loader1(zh) has NO 'app.welcome'. loader2(zh) HAS 'app.welcome' ("欢迎！").
    # So it should resolve to "欢迎！".
    assert nexus_instance.get(L.app.welcome, lang="zh") == "欢迎！"

    # 3. Key missing in both loaders for 'zh', falls back to 'en'
    # Let's add a key that is ONLY in EN
    # 'app.title' is in both. 'app.welcome' is in both (one en, one zh).
    # 'app.version' is in EN (loader2) and ZH (loader2).
    # We need a key that is truly missing in ZH.
    # Let's use a dynamic key for testing fallback.

    # Create a temporary nexus for precise fallback testing
    loader_fallback = MemoryLoader({"en": {"only.in.en": "Fallback Value"}, "zh": {}})
    nexus_fallback = OverlayNexus([loader_fallback])

    assert nexus_fallback.get("only.in.en", lang="zh") == "Fallback Value"
~~~~~
~~~~~python.new
def test_get_domain_specificity_and_fallback(nexus_instance: OverlayNexus):
    # 1. Specific domain (zh) is preferred when key exists
    assert nexus_instance.get("app.title", domain="zh") == "我的应用 (高优先级)"

    # 2. Key missing in 'zh', falls back to default 'en'
    assert nexus_instance.get(L.app.welcome, domain="zh") == "欢迎！"

    # 3. Key missing in both loaders for 'zh', falls back to 'en'
    loader_fallback = MemoryLoader({"en": {"only.in.en": "Fallback Value"}, "zh": {}})
    nexus_fallback = OverlayNexus([loader_fallback])

    assert nexus_fallback.get("only.in.en", domain="zh") == "Fallback Value"
~~~~~

~~~~~act
patch_file
packages/pyneedle-nexus/tests/test_nexus.py
~~~~~
~~~~~python.old
def test_language_resolution_priority(monkeypatch):
    nexus = OverlayNexus(
        loaders=[
            MemoryLoader(
                {"de": {"key": "de"}, "fr": {"key": "fr"}, "en": {"key": "en"}}
            )
        ]
    )

    # Priority 1: Explicit `lang` argument
    assert nexus.get("key", lang="de") == "de"
~~~~~
~~~~~python.new
def test_domain_resolution_priority(monkeypatch):
    nexus = OverlayNexus(
        loaders=[
            MemoryLoader(
                {"de": {"key": "de"}, "fr": {"key": "fr"}, "en": {"key": "en"}}
            )
        ]
    )

    # Priority 1: Explicit `domain` argument
    assert nexus.get("key", domain="de") == "de"
~~~~~

### 下一步建议
1.  **实现 `stitcher-needle` CLI**: 利用新的 `put` 能力，实现 `stitcher needle set <key> <value>` 命令，验证写回流程。
2.  **完善 `JsonHandler`**: 当前的 `JsonHandler` 实现较为简单，后续可增加对注释保留（如果使用 JSONC）或格式美化的支持。
3.  **扩展 `Nexus`**: 尝试在 `Nexus` 中嵌套另一个 `Nexus`，验证组合模式的有效性。
