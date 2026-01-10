from pathlib import Path
from stitcher.adapter.python.index_adapter import PythonAdapter
from stitcher.index.types import ReferenceRecord


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
    adapter = PythonAdapter(root)
    file_path = root / "src/main.py"
    
    # 执行解析
    _, references = adapter.parse(file_path, code)
    
    # 辅助断言函数
    def find_refs(target_fragment):
        return [r for r in references if target_fragment in r.target_id]

    # 1. 验证导入引用 (Imports)
    # import os -> target should assume os
    # 注意：SURI 生成目前是推测性的，我们主要验证它捕获了 'os' 这个意图
    os_refs = find_refs("os")
    assert len(os_refs) >= 1
    assert os_refs[0].kind == "import_path"

    # from mypkg import utils
    utils_refs = find_refs("mypkg.utils")
    assert len(utils_refs) >= 1

    # 2. 验证调用引用 (Usages)
    # utils.do_work()
    # 应该引用 mypkg.utils.do_work (基于 import utils)
    do_work_refs = find_refs("do_work")
    assert len(do_work_refs) > 0
    assert do_work_refs[0].kind == "symbol"

    # 3. 验证本地引用 (Local Usages)
    # self._internal()
    # 应该引用 src/main.py#Processor._internal (或类似的本地 SURI)
    internal_refs = find_refs("Processor._internal")
    assert len(internal_refs) > 0
    
    # 验证位置信息不是空的 (0,0)
    assert internal_refs[0].location_start > 0