好的，这是一个关键的重构步骤，它将使整个项目的资源文件与我们新的、更优雅的加载器架构保持一致。创建一个一次性的迁移脚本是最高效、最可靠的方法。

我将为你生成一个包含该脚本的完整计划。

## [WIP] chore(repo): 将所有 Needle 资源迁移到 SST v2.2 物理存储规范

### 用户需求
创建一个自动化脚本，扫描整个项目，找到所有旧格式的 `needle` JSON 文件（使用 FQN 作为键），并将它们转换为符合 SST v2.2 规范的新格式（嵌套目录和使用相对键的 JSON 文件）。

### 评论
这是一次必要的、全项目范围内的“技术债”清理。将物理文件格式与新的加载器架构对齐，将极大地改善开发体验（DX），使资源文件更易于人类阅读、编辑和进行版本控制。这个一次性脚本确保了迁移过程的一致性和无差错性。

### 目标
1.  创建一个名为 `scripts/migrate_sst_v2.py` 的 Python 脚本。
2.  该脚本将具备以下能力：
    *   递归查找所有包内的 `needle/**/*.json` 文件。
    *   读取使用 FQN 的扁平 JSON 数据。
    *   使用与 `JsonHandler` 中相同的“膨胀”(`inflate`)逻辑，在内存中将扁平数据重建为嵌套字典。
    *   遍历内存中的嵌套字典，并根据 SST v2.2 规范（`category/namespace.json`）创建新的目录结构和文件。
    *   将包含相对键的数据写入新文件。
    *   删除旧的、扁平化的 JSON 文件。
3.  执行此脚本，完成全项目迁移。
4.  迁移完成后删除该脚本。

### 基本原理
我们利用之前在 `JsonHandler` 中实现的 `_inflate_dict` 算法，这是本次迁移的核心引擎。它能可靠地将 FQN 键值对转换成逻辑上的嵌套结构。脚本的主要工作是将这个内存中的逻辑结构“物化”为符合 SST v2.2 规范的物理文件系统结构。通过自动化此过程，我们避免了手动迁移可能引入的大量错误。

### 标签
#intent/tooling #flow/ready #priority/high #comp/runtime #concept/state #scope/dx #task/domain/storage #task/object/asset-migration #task/action/implementation #task/state/continue

---

### Script

#### Acts 1: 创建迁移脚本

我们将创建一个独立的 Python 脚本来处理整个迁移过程。

~~~~~act
write_file
scripts/migrate_sst_v2.py
~~~~~
~~~~~python
import json
import shutil
from pathlib import Path
from typing import Any, Dict, List

# --- 核心算法：从 JsonHandler 复制而来 ---

def _inflate_dict(d: Dict[str, Any]) -> Dict[str, Any]:
    """将扁平的 FQN 字典 '膨胀' 为嵌套字典。"""
    result: Dict[str, Any] = {}
    for k, v in sorted(d.items()): # 排序以保证确定性
        parts = k.split(".")
        d_curr = result
        for i, part in enumerate(parts[:-1]):
            if part not in d_curr:
                d_curr[part] = {}
            # 处理冲突：'a' 之前是叶子，现在需要成为一个节点
            elif not isinstance(d_curr[part], dict):
                d_curr[part] = {"_": d_curr[part]}
            d_curr = d_curr[part]
        
        last_part = parts[-1]
        # 处理冲突：'a.b' 之前是节点，现在需要赋值
        if last_part in d_curr and isinstance(d_curr[last_part], dict):
             d_curr[last_part]["_"] = v
        else:
            d_curr[last_part] = v
    return result

# --- 迁移逻辑 ---

def write_structure(nested_data: Dict[str, Any], base_path: Path):
    """
    遍历嵌套字典，并根据 SST v2.2 规范写入文件系统。
    """
    for category, content in nested_data.items():
        if not isinstance(content, dict):
            # 这种情况不应该发生，但做个防御
            print(f"  - [WARN] Skipping top-level key '{category}' which is not a dictionary.")
            continue

        category_path = base_path / category
        category_path.mkdir(exist_ok=True)
        
        init_data = {}
        if "_" in content:
            init_data["_"] = content.pop("_")

        for namespace, ns_content in content.items():
            if not isinstance(ns_content, dict):
                 # 叶子节点，属于 category 的一部分，放入 __init__.json
                 init_data[namespace] = ns_content
                 continue
            
            # 这是一个真正的命名空间，写入自己的文件
            ns_file = category_path / f"{namespace}.json"
            print(f"  - Writing namespace to {ns_file.relative_to(Path.cwd())}")
            with ns_file.open("w", encoding="utf-8") as f:
                json.dump(ns_content, f, indent=2, sort_keys=True, ensure_ascii=False)
        
        if init_data:
            init_file = category_path / "__init__.json"
            print(f"  - Writing category data to {init_file.relative_to(Path.cwd())}")
            with init_file.open("w", encoding="utf-8") as f:
                json.dump(init_data, f, indent=2, sort_keys=True, ensure_ascii=False)


def find_and_migrate_files(root_dir: Path):
    """查找并迁移所有 needle JSON 文件。"""
    print(f"\nScanning in {root_dir}...")
    
    # 查找所有语言目录，例如 .../needle/en, .../needle/zh
    lang_dirs = list(root_dir.glob("**/needle/*"))
    
    migrated_files = []
    
    for lang_dir in lang_dirs:
        if not lang_dir.is_dir():
            continue

        old_files = list(lang_dir.glob("**/*.json"))
        if not old_files:
            continue

        print(f"\nProcessing language directory: {lang_dir.relative_to(Path.cwd())}")
        
        # 1. 将所有文件内容合并到一个大的扁平字典中
        full_flat_data: Dict[str, str] = {}
        for old_file in old_files:
            print(f"- Reading old file: {old_file.relative_to(Path.cwd())}")
            try:
                with old_file.open('r', encoding='utf-8') as f:
                    data = json.load(f)
                    full_flat_data.update(data)
            except json.JSONDecodeError:
                print(f"  - [WARN] Skipping invalid JSON file: {old_file}")
        
        if not full_flat_data:
            continue
            
        # 2. 将合并后的扁平字典膨胀为嵌套结构
        nested_structure = _inflate_dict(full_flat_data)
        
        # 3. 删除旧的目录内容，准备写入新结构
        print(f"- Cleaning directory {lang_dir.relative_to(Path.cwd())}")
        for item in lang_dir.iterdir():
            if item.is_dir():
                shutil.rmtree(item)
            else:
                item.unlink()

        # 4. 将嵌套结构写回文件系统
        write_structure(nested_structure, lang_dir)
        migrated_files.extend(old_files)

    return migrated_files


def main():
    project_root = Path(__file__).parent.parent
    packages_dir = project_root / "packages"
    
    print("--- Starting Needle SST v2.2 Migration ---")
    
    all_migrated = find_and_migrate_files(packages_dir)
    
    if all_migrated:
        print(f"\n✅ Migration complete. Processed {len(all_migrated)} old files.")
    else:
        print("\n🤔 No files found to migrate.")

if __name__ == "__main__":
    main()
~~~~~

#### Acts 2: 赋予脚本执行权限

~~~~~act
run_command
~~~~~
~~~~~sh
chmod +x scripts/migrate_sst_v2.py
~~~~~

#### Acts 3: 执行迁移

现在，我们运行脚本来转换所有 `needle` 资源文件。

~~~~~act
run_command
~~~~~
~~~~~sh
python scripts/migrate_sst_v2.py
~~~~~

#### Acts 4: 清理迁移脚本

迁移是一次性操作，完成后脚本即可删除。

~~~~~act
delete_file
scripts/migrate_sst_v2.py
~~~~~

### 下一步建议
迁移已经完成。现在整个代码库的物理资源文件都与新的加载器架构保持一致了。强烈建议立即运行完整的测试套件，以确保新的文件结构能够被 `FileSystemLoader` 正确地加载，并且所有依赖本地化字符串的测试（如 CLI 命令帮助文本测试）都能通过。
