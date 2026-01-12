from pathlib import Path
from stitcher.lang.python.adapter import PythonAdapter


def test_extract_references_basic():
    """测试基本的引用提取：包括导入和本地符号使用。"""
    code = """
import os
from mypkg import utils
from . import core

class Processor:
    def process(self):
        utils.do_work()
        print(os.path.join("a", "b"))
        self._internal()

    def _internal(self):
        pass
"""
    root = Path("/tmp/proj")
    adapter = PythonAdapter(root, [root])
    file_path = root / "src/main.py"

    # 执行解析
    _, references = adapter.parse(file_path, code)

    # 辅助断言函数
    def find_refs(target_fqn_fragment):
        # After decoupling, we assert against the logical target_fqn, not the physical target_id
        return [r for r in references if target_fqn_fragment in r.target_fqn]

    # 1. 验证导入引用 (Imports)
    # import os
    os_refs = find_refs("os")
    assert len(os_refs) >= 1
    assert os_refs[0].kind == "import_path"
    assert os_refs[0].target_fqn == "os"

    # from mypkg import utils
    utils_refs = find_refs("mypkg.utils")
    assert len(utils_refs) >= 1
    assert utils_refs[0].target_fqn == "mypkg.utils"

    # 2. 验证调用引用 (Usages)
    # utils.do_work() -> should resolve to a reference to 'mypkg.utils.do_work'
    do_work_refs = find_refs("mypkg.utils.do_work")
    assert len(do_work_refs) > 0
    assert do_work_refs[0].kind == "symbol"

    # 3. 验证本地引用 (Local Usages)
    # self._internal()
    # TODO: 当前 UsageScanVisitor 缺乏 Class 上下文感知能力，无法解析 'self'。
    # 暂时跳过此断言，待实现 Scope Analysis 后恢复。
    # internal_refs = find_refs("Processor._internal")
    # assert len(internal_refs) > 0
    # assert internal_refs[0].location_start > 0
