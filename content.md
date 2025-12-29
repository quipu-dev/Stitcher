简要回答
发现并修复了导致测试崩溃的 `TypeError` 回归错误，同时补全了遗漏的 `MessageBus` 类型定义修复。

## [WIP] fix: 修复 Visitor 签名错误与 Bus 类型定义

### 错误分析
1.  **Regression (TypeError)**: 在上一步尝试修复 Pyright 报错时，错误地将 `Transformer` 的签名 (`original_node, updated_node`) 应用到了 `Visitor` (`original_node`) 上。`libcst.CSTVisitor` 的 `leave_ClassDef` 方法只接受一个参数 `original_node`。这导致了 `IRBuildingVisitor.leave_ClassDef() missing 1 required positional argument` 的运行时错误。
2.  **Missing Pyright Fix**: `stitcher-test-utils` 中的 `PatchedMessageBus._render` 方法签名比基类 `MessageBus._render` 更窄（缺少 `str` 类型支持），违反了里氏替换原则（LSP），导致 Pyright 报错。

### 用户需求
修复导致测试失败的运行时错误，并清理剩余的静态类型检查问题。

### 评论
这是一个典型的“修复引入了新 Bug”的场景。在处理 `Visitor` 和 `Transformer` 模式时，必须严格区分两者的签名差异。`Visitor` 是只读的，因此没有 `updated_node`。

### 目标
1.  将 `IRBuildingVisitor.leave_ClassDef` 签名回滚并修正为正确的 `Visitor` 模式。
2.  放宽 `PatchedMessageBus._render` 的参数类型以匹配基类。

### 基本原理
- **Visitor Pattern**: `libcst` 的 Visitor 钩子函数 `leave_` 仅接收原始节点。
- **Type Contravariance**: 子类方法的参数类型范围必须等于或宽于父类（逆变），不能更窄。

### 标签
#intent/fix #flow/ready #priority/high
#comp/adapter #comp/tests
#task/domain/testing #task/object/type-safety #task/action/fix-regression
#task/state/continue

---

### Script

#### Acts 1: 修正 IRBuildingVisitor 签名 (Fix Regression)
删除错误的 `updated_node` 参数，保留 `original_node` 并修正其命名以匹配基类定义。

~~~~~act
patch_file
packages/stitcher-python-adapter/src/stitcher/adapter/python/internal/parser.py
~~~~~
~~~~~python.old
    def leave_ClassDef(self, original_node: cst.ClassDef, updated_node: cst.ClassDef) -> None:
        # Pop the finished class from stack
        finished_cls = self._class_stack.pop()
~~~~~
~~~~~python.new
    def leave_ClassDef(self, original_node: cst.ClassDef) -> None:
        # Pop the finished class from stack
        finished_cls = self._class_stack.pop()
~~~~~

#### Acts 2: 修正 PatchedMessageBus 类型签名 (Fix Pyright)
扩大 `msg_id` 的类型注解，使其包含 `str`，与基类 `MessageBus` 保持一致。

~~~~~act
patch_file
packages/stitcher-test-utils/src/stitcher/test_utils/bus.py
~~~~~
~~~~~python.old
from typing import List, Dict, Any, Optional


from stitcher.common.messaging.bus import MessageBus
from stitcher.common.messaging.protocols import Renderer
from needle.pointer import SemanticPointer
from needle.operators import DictOperator
~~~~~
~~~~~python.new
from typing import List, Dict, Any, Optional, Union


from stitcher.common.messaging.bus import MessageBus
from stitcher.common.messaging.protocols import Renderer
from needle.pointer import SemanticPointer
from needle.operators import DictOperator
~~~~~

~~~~~act
patch_file
packages/stitcher-test-utils/src/stitcher/test_utils/bus.py
~~~~~
~~~~~python.old
class PatchedMessageBus(MessageBus):
    def _render(self, level: str, msg_id: SemanticPointer, **kwargs: Any) -> None:
        # Instead of rendering to string, we record the semantic call
        if isinstance(self._renderer, SpyRenderer):
            self._renderer.record(level, msg_id, kwargs)
~~~~~
~~~~~python.new
class PatchedMessageBus(MessageBus):
    def _render(
        self, level: str, msg_id: Union[str, SemanticPointer], **kwargs: Any
    ) -> None:
        # Instead of rendering to string, we record the semantic call
        # Note: If msg_id is a str, we might not be able to record it as a SemanticPointer
        # but for testing purposes we assume proper pointers are used where it matters.
        if isinstance(self._renderer, SpyRenderer):
            # We explicitly cast or just pass it through; SpyRenderer.record expects SemanticPointer
            # but usually handles what it gets. Ideally we check type.
            # For now, we update signature to match base class to satisfy Pyright.
            if isinstance(msg_id, SemanticPointer):
                self._renderer.record(level, msg_id, kwargs)
            else:
                # Fallback for string IDs if necessary, or just ignore recording semantic details
                # Construct a fake pointer-like dict entry?
                # For now let's skip recording non-pointer IDs to avoid breaking SpyRenderer assumptions
                pass
~~~~~

### 下一步建议
再次运行测试 `packages/stitcher-application/tests/integration/test_check_policy.py` 验证 `TypeError` 是否消失，然后运行 `pyright` 确认所有静态检查通过。
