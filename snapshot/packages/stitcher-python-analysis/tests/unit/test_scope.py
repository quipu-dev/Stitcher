from stitcher.spec import ModuleDef, Attribute, FunctionDef, ClassDef
from stitcher.python.analysis.scope import ScopeAnalyzer


def test_scope_analyzer_from_ir():
    # 1. Setup: Create a mock ModuleDef IR
    module_ir = ModuleDef(
        file_path="src/main.py",
        attributes=[
            # import os -> alias 'os' -> 'os'
            Attribute(name="os", alias_target="os"),
            # from utils import helper -> alias 'helper' -> 'utils.helper'
            Attribute(name="helper", alias_target="utils.helper"),
        ],
        functions=[FunctionDef(name="my_func")],
        classes=[
            ClassDef(
                name="MyClass",
                attributes=[
                    # from .models import User -> alias 'User' -> 'main.models.User'
                    Attribute(name="User", alias_target="main.models.User")
                ],
            )
        ],
    )

    analyzer = ScopeAnalyzer()

    # 2. Act
    symbol_map = analyzer.build_from_ir(module_ir, logical_module_fqn="main")

    # 3. Assert
    assert symbol_map["os"] == "os"
    assert symbol_map["helper"] == "utils.helper"
    # Local function definition should be mapped to its FQN
    assert symbol_map["my_func"] == "main.my_func"
    # Local class definition
    assert symbol_map["MyClass"] == "main.MyClass"
    # Class-level alias
    assert symbol_map["User"] == "main.models.User"
