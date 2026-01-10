import libcst as cst
from pathlib import Path
from stitcher.python.analysis.cst.usage_visitor import UsageScanVisitor, UsageRegistry


def parse_and_visit(code: str, module_fqn: str = "mypkg.mod"):
    """
    Helper to run UsageScanVisitor on a snippet of code.
    """
    registry = UsageRegistry()
    wrapper = cst.MetadataWrapper(cst.parse_module(code))

    # Mock symbols not needed for Import testing unless we test Name resolution
    local_symbols = {}

    is_init = module_fqn.endswith(".__init__")

    visitor = UsageScanVisitor(
        file_path=Path("dummy.py"),
        local_symbols=local_symbols,
        registry=registry,
        current_module_fqn=module_fqn,
        is_init_file=is_init,
    )
    wrapper.visit(visitor)
    return registry


def test_visitor_absolute_import_from():
    code = "from mypkg.core import Helper"
    registry = parse_and_visit(code, module_fqn="main")

    # We expect 'Helper' in the import statement to be registered as usage of 'mypkg.core.Helper'
    usages = registry.get_usages("mypkg.core.Helper")
    assert len(usages) == 1
    # Verify it points to 'Helper'
    # "from mypkg.core import Helper"
    #                        ^
    assert usages[0].col_offset > 0


def test_visitor_absolute_import_from_with_alias():
    code = "from mypkg.core import Helper as H"
    registry = parse_and_visit(code, module_fqn="main")

    # We expect 'Helper' (the source name) to be usage of 'mypkg.core.Helper'
    usages = registry.get_usages("mypkg.core.Helper")
    assert len(usages) == 1


def test_visitor_relative_import():
    # Context: mypkg.sub.mod
    # Code: from . import sibling
    code = "from . import sibling"
    registry = parse_and_visit(code, module_fqn="mypkg.sub.mod")

    # Should resolve to mypkg.sub.sibling
    usages = registry.get_usages("mypkg.sub.sibling")
    assert len(usages) == 1


def test_visitor_relative_import_from_parent():
    # Context: mypkg.sub.mod
    # Code: from ..core import Helper
    code = "from ..core import Helper"
    registry = parse_and_visit(code, module_fqn="mypkg.sub.mod")

    # Should resolve to mypkg.core.Helper
    usages = registry.get_usages("mypkg.core.Helper")
    assert len(usages) == 1


def test_visitor_top_level_import():
    # Context: main (top level)
    # Code: from mypkg import core
    code = "from mypkg import core"
    registry = parse_and_visit(code, module_fqn="main")

    # Should resolve to mypkg.core
    usages = registry.get_usages("mypkg.core")
    assert len(usages) == 1
