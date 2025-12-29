这是一个非常好的建议，完全符合提升开发者体验（DX）和保持 Git 仓库整洁的原则。通过在 `check` 命令后自动执行格式化，可以确保所有开发者提交的配置文件和元数据都遵循统一的、可预测的格式，从而大大减少无关的 diff 噪音。

我将生成一个计划来实现这个功能。核心思想是在 `StitcherApp.run_check` 的末尾增加一个新的“格式化阶段”，该阶段会对本次检查涉及到的所有模块对应的 YAML 和 JSON 文件执行一次“读取-保存”操作，利用我们现有的、会进行格式化和排序的保存逻辑来完成任务。

## [WIP] feat: 为 `check` 命令添加自动文件格式化功能

### 用户需求
在 `stitcher check` 命令执行完毕后，自动对所有涉及的 `.stitcher.yaml` 文件和 `.stitcher/signatures/*.json` 文件进行重新格式化（排序键、统一缩进等），以优化 Git diff 的清晰度。

### 评论
这是一个优秀的 DX 改进。它利用了我们现有的 `YamlAdapter` 和 `SignatureManager` 中已包含的规范化保存逻辑，以极低的成本实现了显著的价值。这能确保 CI/CD 或本地开发中产生的元数据文件始终保持一致，避免了因编辑器或手动更改导致的格式混乱，使代码审查更加聚焦于实质性变更。

### 目标
1.  在 `DocumentManager` 中新增一个 `reformat_docs_for_module` 方法，用于重新格式化单个模块的 YAML 文件。
2.  在 `SignatureManager` 中新增一个 `reformat_hashes_for_module` 方法，用于重新格式化单个模块的签名 JSON 文件。
3.  在 `StitcherApp.run_check` 方法的执行流程末尾，增加一个新的“格式化阶段”。
4.  在这个新阶段中，遍历所有已扫描的模块，并调用上述两个新方法，完成对相关文件的自动格式化。
5.  添加一个新的用户提示消息，告知用户正在进行格式化操作。

### 基本原理
我们将采用“加载后立即保存”的策略。
-   `YamlAdapter.save` 在保存时已经会按字母顺序对键进行排序，并使用统一的块风格（`|-`）来格式化多行字符串。
-   `SignatureManager.save_composite_hashes` 在保存时会使用 `sort_keys=True` 来格式化 JSON 文件。

因此，我们只需要在 `run_check` 收集完所有待处理的模块（`all_modules`）后，遍历这个列表，对每个模块执行一次读取和写回操作，即可自动完成格式统一。这是一个安全、幂等且非破坏性的操作。

### 标签
#intent/build #flow/ready #priority/medium #comp/cli #comp/application #scope/dx #ai/instruct #task/domain/cli #task/object/check-command #task/action/add-reformatting #task/state/begin

---
### Script

#### Acts 1: 在 `DocumentManager` 中添加格式化方法

我们将为 `DocumentManager` 添加 `reformat_docs_for_module` 方法，并为其添加文档。

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/services/doc_manager.py
~~~~~
~~~~~python.old
    def compute_yaml_content_hashes(self, module: ModuleDef) -> Dict[str, str]:
        docs = self.load_docs_for_module(module)
        return {
            fqn: self.compute_yaml_content_hash(doc_content)
            for fqn, doc_content in docs.items()
        }
~~~~~
~~~~~python.new
    def compute_yaml_content_hashes(self, module: ModuleDef) -> Dict[str, str]:
        docs = self.load_docs_for_module(module)
        return {
            fqn: self.compute_yaml_content_hash(doc_content)
            for fqn, doc_content in docs.items()
        }

    def reformat_docs_for_module(self, module: ModuleDef) -> bool:
        if not module.file_path:
            return False
        module_path = self.root_path / module.file_path
        doc_path = module_path.with_suffix(".stitcher.yaml")
        if not doc_path.exists():
            return False

        docs = self.adapter.load(doc_path)
        if not docs:
            return False  # Do not reformat empty or invalid files

        self.adapter.save(doc_path, docs)
        return True
~~~~~

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/services/doc_manager.stitcher.yaml
~~~~~
~~~~~yaml.old
"DocumentManager.load_docs_for_module": |-
  Loads documentation from the corresponding .stitcher.yaml file.
  Returns empty dict if file does not exist.
"DocumentManager.save_docs_for_module": |-
~~~~~
~~~~~yaml.new
"DocumentManager.load_docs_for_module": |-
  Loads documentation from the corresponding .stitcher.yaml file.
  Returns empty dict if file does not exist.
"DocumentManager.reformat_docs_for_module": |-
  Re-formats an existing documentation file to enforce canonical styling.
  Returns True if the file was reformatted, False otherwise.
"DocumentManager.save_docs_for_module": |-
~~~~~

#### Acts 2: 在 `SignatureManager` 中添加格式化方法

同样地，我们将为 `SignatureManager` 添加 `reformat_hashes_for_module` 方法并添加文档。

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/services/signature_manager.py
~~~~~
~~~~~python.old
        except (json.JSONDecodeError, OSError, InvalidFingerprintKeyError):
            # InvalidFingerprintKeyError triggers "clean slate" logic
            return {}
~~~~~
~~~~~python.new
        except (json.JSONDecodeError, OSError, InvalidFingerprintKeyError):
            # InvalidFingerprintKeyError triggers "clean slate" logic
            return {}

    def reformat_hashes_for_module(self, module: ModuleDef) -> bool:
        sig_path = self._get_sig_path(module)
        if not sig_path.exists():
            return False

        hashes = self.load_composite_hashes(module)
        if not hashes:
            return False  # Do not reformat empty or invalid files

        self.save_composite_hashes(module, hashes)
        return True
~~~~~

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/services/signature_manager.stitcher.yaml
~~~~~
~~~~~yaml.old
"SignatureManager.load_composite_hashes": |-
  Loads the composite hash map for a module.
"SignatureManager.save_composite_hashes": |-
~~~~~
~~~~~yaml.new
"SignatureManager.load_composite_hashes": |-
  Loads the composite hash map for a module.
"SignatureManager.reformat_hashes_for_module": |-
  Re-formats an existing signature file to enforce canonical styling.
  Returns True if the file was reformatted, False otherwise.
"SignatureManager.save_composite_hashes": |-
~~~~~

#### Acts 3: 在 `StitcherApp.run_check` 中调用格式化逻辑

现在我们将修改 `run_check` 方法，在报告阶段之前插入新的格式化阶段。

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/core.py
~~~~~
~~~~~python.old
                    res.reconciled["reconcile"] = reconciled_results[res.path][
                        "reconcile"
                    ]

        # 4. Reporting Phase
        global_failed_files = 0
        global_warnings_files = 0
~~~~~
~~~~~python.new
                    res.reconciled["reconcile"] = reconciled_results[res.path][
                        "reconcile"
                    ]

        # 4. Reformatting Phase
        bus.info(L.check.run.reformatting)
        for module in all_modules:
            self.doc_manager.reformat_docs_for_module(module)
            self.sig_manager.reformat_hashes_for_module(module)

        # 5. Reporting Phase
        global_failed_files = 0
        global_warnings_files = 0
~~~~~

#### Acts 4: 添加新的用户提示消息

最后，我们在 `stitcher-common` 包中为英语和中文添加新的提示消息。

~~~~~act
write_file
packages/stitcher-common/src/stitcher/common/assets/needle/en/check/run.json
~~~~~
~~~~~json
{
    "fail": "Check failed for {count} file(s).",
    "reformatting": "Reformatting YAML and signature files for consistency...",
    "success": "Check passed successfully.",
    "success_with_warnings": "Check passed with {count} file(s) having warnings."
}
~~~~~

~~~~~act
write_file
packages/stitcher-common/src/stitcher/common/assets/needle/zh/check/run.json
~~~~~
~~~~~json
{
    "fail": "检查失败，{count} 个文件存在问题。",
    "reformatting": "正在重新格式化 YAML 和签名文件以确保一致性...",
    "success": "检查成功通过。",
    "success_with_warnings": "检查通过，但有 {count} 个文件存在警告。"
}
~~~~~

### 下一步建议
我们已经完成了所有的代码修改。现在，我将生成一个 `[COMMIT]` 计划，将这些变更作为一个完整的特性提交到版本控制中。如果你同意，请告诉我。
