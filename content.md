好的，我已经确认了相关测试文件的位置。

根据“测试与代码共存”的原则，`test_message_bus.py` 及其 sidecar 文件应当随着 `FeedbackBus` 的实现一起迁移到 `stitcher-bus` 包中。

## [WIP] refactor: 迁移消息总线相关的测试文件

### 用户需求
将 `test_message_bus.py` 及其对应的 `.stitcher.yaml` 文件从 `stitcher-common` 迁移到 `stitcher-bus` 的测试目录中，并确保目录结构符合 Monorepo 规范。

### 评论
将测试用例与被测代码物理上保持一致是维护大型 Monorepo 的关键。这确保了当我们运行 `packages/stitcher-bus` 的包内测试时，能够包含所有相关的验证逻辑。这符合 `d3-principle-pytest-monorepo-architecture` 规范。

### 目标
1.  在 `packages/stitcher-bus` 中创建 `tests/unit` 目录结构。
2.  移动 `packages/stitcher-common/tests/unit/test_message_bus.py` 到新位置。
3.  移动对应的 `packages/stitcher-common/tests/unit/test_message_bus.stitcher.yaml` 到新位置。

### 基本原理
我们使用 `move_file` 指令来执行物理位置的变更。由于测试文件通常位于 `tests/` 目录下（不在 `src/` 下），且不直接参与 `stitcher` 的命名空间分发逻辑，因此直接进行文件系统层面的移动即可。

### 标签
#intent/refine #flow/ready #priority/medium 
#comp/tests #concept/ui #scope/dx 
#ai/instruct
#task/domain/testing #task/object/message-bus-tests #task/action/relocation #task/state/continue

---

### Script

#### Acts 1: 创建新的测试目录结构

在 `stitcher-bus` 包内建立标准的测试存放路径。

~~~~~act
run_command
~~~~~
~~~~~
mkdir -p packages/stitcher-bus/tests/unit
~~~~~

#### Acts 2: 移动测试文件及其 Sidecar

将测试用例及其元数据文件迁移到目标包。

~~~~~act
move_file
packages/stitcher-common/tests/unit/test_message_bus.py
packages/stitcher-bus/tests/unit/test_message_bus.py
~~~~~

~~~~~act
move_file
packages/stitcher-common/tests/unit/test_message_bus.stitcher.yaml
packages/stitcher-bus/tests/unit/test_message_bus.stitcher.yaml
~~~~~

### 下一步建议
1.  **执行重构脚本**: 现在可以安全地执行之前生成的 `migrations/004_move_bus_to_dedicated_package.py` 迁移脚本了。它将处理 `src/` 下的代码移动及全局引用更新。
2.  **验证测试**: 重构完成后，建议在根目录运行 `pytest packages/stitcher-bus`，确保迁移后的测试用例依然能够正确发现并执行。
3.  **检查导入**: 迁移后的 `test_message_bus.py` 如果直接引用了 `stitcher.common.bus`（单例），在 `stitcher-bus` 作为一个独立单元测试时可能需要调整。但在本项目结构下，通过根目录的 `pythonpath` 配置，它依然是可运行的。
