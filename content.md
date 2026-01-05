好的，我看到了这个 `AttributeError`。问题很明确：在 `planner.py` 中，代码尝试调用 `yaml_adapter.dump(data)`，但是 `YamlAdapter` 类并没有实现一个名为 `dump` 的方法。它有一个 `save` 方法用于将数据写入文件，但没有一个 `dump` 方法用于将数据序列化为字符串。

我将为 `YamlAdapter` 添加这个缺失的 `dump` 方法来修复此问题。

## [WIP] fix: 为 YamlAdapter 添加 dump 方法以解决 AttributeError

### 错误分析

`stitcher-refactor` 包中的 `Planner` 在处理 YAML 格式的边车文件（sidecar files）时，需要将更新后的数据内容序列化成一个字符串，以便创建一个 `WriteFileOp` 操作。它尝试通过调用 `yaml_adapter.dump(data)` 来实现这一点。

然而，`stitcher-common` 包中定义的 `YamlAdapter` 类只提供了 `load(path)` 和 `save(path, data)` 方法，缺少一个 `dump(data)` 方法来返回字符串形式的 YAML 内容。这导致了 `AttributeError`。

### 用户需求

修复在 `planner.py` 中发生的 `AttributeError: 'YamlAdapter' object has no attribute 'dump'` 错误。

### 评论

这是一个清晰的 API 缺失问题。`Planner` 的设计是正确的，它需要一个能返回字符串内容的序列化方法，而不是一个直接写入文件的方法，这样才能将文件I/O操作统一由 `TransactionManager` 管理。为 `YamlAdapter` 补充这个方法是符合逻辑的。

### 目标

1.  在 `stitcher.common.adapters.yaml_adapter.py` 文件中，为 `YamlAdapter` 类添加一个新的 `dump` 方法。
2.  确保 `dump` 方法使用与现有 `save` 方法相同的、支持多行字符串的格式化逻辑。
3.  更新 `yaml_adapter.stitcher.yaml` 文档，以包含这个新添加的方法。

### 基本原理

我将在 `YamlAdapter` 类中实现 `dump` 方法。它的内部逻辑将几乎完全复制自 `save` 方法中负责序列化的部分，但它不会将结果写入文件流，而是直接调用 `yaml.dump(data)` 并返回其字符串输出。这将为 `Planner` 提供它所需要的功能，从而解决 `AttributeError`。

### 标签

#intent/fix #flow/ready #priority/high #comp/engine #comp/common #concept/serialization #scope/api #ai/instruct #task/domain/refactoring #task/object/yaml-adapter #task/action/bug-fix #task/state/continue

---

### Script

#### Acts 1: 实现并记录 YamlAdapter.dump 方法

首先，我将修改 `yaml_adapter.py` 文件，在 `YamlAdapter` 类中添加 `dump` 方法。然后，我会更新其对应的文档文件。

~~~~~act
patch_file
packages/stitcher-common/src/stitcher/common/adapters/yaml_adapter.py
~~~~~
~~~~~python.old
        except yaml.YAMLError:
            return {}

    def save(self, path: Path, data: Dict[str, str]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        sorted_data = dict(sorted(data.items()))
~~~~~
~~~~~python.new
        except yaml.YAMLError:
            return {}

    def dump(self, data: Dict[str, str]) -> str:
        sorted_data = dict(sorted(data.items()))

        class MultilineDumper(yaml.SafeDumper):
            pass

        def str_presenter(dumper, data):
            return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|")

        MultilineDumper.add_representer(str, str_presenter)

        return yaml.dump(
            sorted_data,
            Dumper=MultilineDumper,
            allow_unicode=True,
            default_flow_style=False,
            sort_keys=False,
        )

    def save(self, path: Path, data: Dict[str, str]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        sorted_data = dict(sorted(data.items()))
~~~~~

~~~~~act
write_file
packages/stitcher-common/src/stitcher/common/adapters/yaml_adapter.stitcher.yaml
~~~~~
~~~~~yaml
"YamlAdapter": |-
  An adapter to read/write documentation from/to YAML files.
"YamlAdapter.dump": |-
  Dumps a dictionary of docstrings to a YAML formatted string.
"YamlAdapter.load": |-
  Loads docstrings from a YAML file. Returns an empty dictionary if the file
  does not exist, is not a valid YAML, or is not a dictionary.
"YamlAdapter.save": |-
  Saves a dictionary of docstrings to a YAML file, ensuring multiline strings
  are formatted in the block style for readability.
~~~~~

### 下一步建议

这个 `AttributeError` 应该已经解决了。请再次运行测试。如果所有测试都通过了，我们就可以认为这次重构任务完成了。
