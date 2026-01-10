## [WIP] fix: 修复 SourceLocation 导出遗漏及 Pyright 类型错误

### 错误分析
1.  **ImportError**: 上一个计划在 `stitcher-spec` 的 `models.py` 中定义了 `SourceLocation`，但忘记在 `__init__.py` 中导出它。这导致依赖它的其他包（如 `stitcher-python-analysis`）无法导入，进而引发连锁的导入错误和看似循环依赖的异常。
2.  **Pyright Type Errors**:
    *   `store.py`: SQLite `lastrowid` 可能为 `None`，与返回类型 `int` 冲突。
    *   `serializers.py`: `BaseSerializer` 的 `to_yaml` 签名定义过窄 (`Dict`)，与其子类 `RawSerializer` (`Union[str, Dict]`) 和协议冲突。
    *   `index_adapter.py` & `griffe/parser.py`: 尝试访问 `object` 或 `griffe.Object` 上未静态定义的属性 (`location`, `end_lineno`)。

### 用户需求
修复构建错误，使 `SourceLocation` 能够被正确导入，并解决静态类型检查器报告的问题。

### 评论
这是典型的“实现后清理”工作。在修改核心接口时，必须确保模块导出同步更新。同时，处理 `object` 类型的动态属性访问时，使用 `getattr` 比直接访问更安全且符合类型检查规则。

### 目标
1.  在 `packages/stitcher-spec/src/stitcher/spec/__init__.py` 中导出 `SourceLocation`。
2.  修正 `store.py`, `serializers.py`, `index_adapter.py`, `griffe/parser.py` 中的 Pyright 错误。

### 基本原理
*   **导出修复**: 显式导出是 Python 包管理的标准做法。
*   **类型安全**: 将 `Optional` 类型显式解包（例如使用 `or 0`），并修正基类方法签名以匹配协议定义，消除 Liskov 替换原则违例。对于动态属性，使用 `getattr` 既能运行时安全也能通过静态检查。

### 标签
#intent/fix #flow/ready #priority/critical
#comp/interfaces #comp/index #comp/adapters
#concept/typing
#ai/instruct
#task/domain/analysis #task/object/symbol-location #task/action/repair
#task/state/continue

---

### Script

#### Acts 1: 修复 stitcher-spec 导出

~~~~~act
patch_file
packages/stitcher-spec/src/stitcher/spec/__init__.py
~~~~~
~~~~~python.old
    Argument,
    ArgumentKind,
    Attribute,
    ClassDef,
    FunctionDef,
    ModuleDef,
    ConflictType,
    ResolutionAction,
~~~~~
~~~~~python.new
    Argument,
    ArgumentKind,
    Attribute,
    ClassDef,
    FunctionDef,
    ModuleDef,
    SourceLocation,
    ConflictType,
    ResolutionAction,
~~~~~

~~~~~act
patch_file
packages/stitcher-spec/src/stitcher/spec/__init__.py
~~~~~
~~~~~python.old
    "Fingerprint",
    "InvalidFingerprintKeyError",
    "Argument",
    "ArgumentKind",
    "Attribute",
    "ClassDef",
    "FunctionDef",
    "ModuleDef",
    # Reconciliation Models
    "ConflictType",
~~~~~
~~~~~python.new
    "Fingerprint",
    "InvalidFingerprintKeyError",
    "Argument",
    "ArgumentKind",
    "Attribute",
    "ClassDef",
    "FunctionDef",
    "ModuleDef",
    "SourceLocation",
    # Reconciliation Models
    "ConflictType",
~~~~~

#### Acts 2: 修复 stitcher-index 类型错误 (store.py)

处理 `lastrowid` 可能为 None 的情况。

~~~~~act
patch_file
packages/stitcher-index/src/stitcher/index/store.py
~~~~~
~~~~~python.old
                    """,
                    (path, content_hash, mtime, size),
                )
                return cursor.lastrowid, True

    def get_file_by_path(self, path: str) -> Optional[FileRecord]:
~~~~~
~~~~~python.new
                    """,
                    (path, content_hash, mtime, size),
                )
                # lastrowid should not be None for INSERT, but type hint says Optional[int]
                return cursor.lastrowid or 0, True

    def get_file_by_path(self, path: str) -> Optional[FileRecord]:
~~~~~

#### Acts 3: 修复 stitcher-python-adapter 类型错误 (serializers.py)

修正 `BaseSerializer` 的签名以匹配协议和子类。

~~~~~act
patch_file
packages/stitcher-python-adapter/src/stitcher/adapter/python/docstring/serializers.py
~~~~~
~~~~~python.old
    def _decode_item_value(self, value: str) -> dict:
        return {"annotation": None, "description": value}

    def to_yaml(self, ir: DocstringIR) -> Dict[str, Any]:
        raise NotImplementedError

    def from_yaml(self, data: Union[str, Dict[str, Any]]) -> DocstringIR:
~~~~~
~~~~~python.new
    def _decode_item_value(self, value: str) -> dict:
        return {"annotation": None, "description": value}

    def to_yaml(self, ir: DocstringIR) -> Union[str, Dict[str, Any]]:
        raise NotImplementedError

    def from_yaml(self, data: Union[str, Dict[str, Any]]) -> DocstringIR:
~~~~~

#### Acts 4: 修复 stitcher-python-adapter 类型错误 (index_adapter.py)

使用 `getattr` 安全访问动态属性。

~~~~~act
patch_file
packages/stitcher-python-adapter/src/stitcher/adapter/python/index_adapter.py
~~~~~
~~~~~python.old
            # Location Handling
            # We assume entity_for_hash also carries the location info if it is a Def object.
            # Attribute locations are passed via entity_for_hash if it's an Attribute obj.
            # But the 'add' signature treats entity_for_hash as Optional[object].
            # We should check if it has a 'location' attribute.
            loc_start = 0
            loc_end = 0

            if hasattr(entity_for_hash, "location") and entity_for_hash.location:
                # Mapping Strategy: Use lineno for location_start and end_lineno for location_end
                # This provides line-level precision for jump-to-definition.
                loc = entity_for_hash.location
                loc_start = loc.lineno
                loc_end = loc.end_lineno

            symbols.append(
~~~~~
~~~~~python.new
            # Location Handling
            # We assume entity_for_hash also carries the location info if it is a Def object.
            # Attribute locations are passed via entity_for_hash if it's an Attribute obj.
            # But the 'add' signature treats entity_for_hash as Optional[object].
            # We should check if it has a 'location' attribute.
            loc_start = 0
            loc_end = 0

            # Use getattr to avoid Pyright errors about accessing attributes on 'object' or 'None'
            loc = getattr(entity_for_hash, "location", None)
            if loc:
                # Mapping Strategy: Use lineno for location_start and end_lineno for location_end
                # This provides line-level precision for jump-to-definition.
                loc_start = loc.lineno
                loc_end = loc.end_lineno

            symbols.append(
~~~~~

#### Acts 5: 修复 stitcher-python-analysis 类型错误 (griffe/parser.py)

修复对 Griffe 对象的属性访问。

~~~~~act
patch_file
packages/stitcher-python-analysis/src/stitcher/python/analysis/griffe/parser.py
~~~~~
~~~~~python.old
    def _extract_location(self, obj: griffe.Object) -> Optional[SourceLocation]:
        if obj.lineno:
            return SourceLocation(
                lineno=obj.lineno,
                col_offset=0,  # Griffe doesn't provide column
                end_lineno=obj.end_lineno or obj.lineno,
                end_col_offset=0,
            )
        return None
~~~~~
~~~~~python.new
    def _extract_location(self, obj: griffe.Object) -> Optional[SourceLocation]:
        if obj.lineno:
            # Safely access end_lineno as it might not be present on base Object type
            end_lineno = getattr(obj, "end_lineno", None) or obj.lineno
            return SourceLocation(
                lineno=obj.lineno,
                col_offset=0,  # Griffe doesn't provide column
                end_lineno=end_lineno,
                end_col_offset=0,
            )
        return None
~~~~~

### 下一步建议
执行完这些修复后，应重新运行测试 (`pytest`) 和类型检查 (`pyright`)。如果通过，则可以继续推进到 **Debt 1.2: 引用分析** 的实现。
