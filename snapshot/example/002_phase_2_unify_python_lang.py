from pathlib import Path
from stitcher.refactor.migration import MigrationSpec, Move, MoveDir


def upgrade(spec: MigrationSpec):
    """
    Stitcher 架构重构阶段二：语言能力统一与合并

    将原来的 stitcher-python-adapter 和 stitcher-python-analysis 合并为
    统一的 stitcher-lang-python 包，并按功能垂直重构内部结构。
    """

    # --- 1. 从 stitcher-python-adapter 迁移 ---

    # 迁移解析能力 (Parsing)
    spec.add(
        Move(
            Path(
                "packages/stitcher-python-adapter/src/stitcher/adapter/python/griffe_parser.py"
            ),
            Path(
                "packages/stitcher-lang-python/src/stitcher/lang/python/parser/griffe.py"
            ),
        )
    )
    spec.add(
        Move(
            Path(
                "packages/stitcher-python-adapter/src/stitcher/adapter/python/parser.py"
            ),
            Path(
                "packages/stitcher-lang-python/src/stitcher/lang/python/parser/cst.py"
            ),
        )
    )

    # 迁移索引适配器 (Indexing)
    spec.add(
        Move(
            Path(
                "packages/stitcher-python-adapter/src/stitcher/adapter/python/index_adapter.py"
            ),
            Path("packages/stitcher-lang-python/src/stitcher/lang/python/adapter.py"),
        )
    )

    # 迁移转换门面 (Transforming)
    spec.add(
        Move(
            Path(
                "packages/stitcher-python-adapter/src/stitcher/adapter/python/transformer.py"
            ),
            Path(
                "packages/stitcher-lang-python/src/stitcher/lang/python/transform/facade.py"
            ),
        )
    )

    # 迁移文档能力 (Docstrings)
    spec.add(
        MoveDir(
            Path(
                "packages/stitcher-python-adapter/src/stitcher/adapter/python/docstring"
            ),
            Path("packages/stitcher-lang-python/src/stitcher/lang/python/docstring"),
        )
    )

    # 迁移其他基础能力
    spec.add(
        Move(
            Path(
                "packages/stitcher-python-adapter/src/stitcher/adapter/python/fingerprint.py"
            ),
            Path(
                "packages/stitcher-lang-python/src/stitcher/lang/python/fingerprint.py"
            ),
        )
    )
    spec.add(
        Move(
            Path(
                "packages/stitcher-python-adapter/src/stitcher/adapter/python/inspector.py"
            ),
            Path("packages/stitcher-lang-python/src/stitcher/lang/python/inspector.py"),
        )
    )
    spec.add(
        Move(
            Path("packages/stitcher-python-adapter/src/stitcher/adapter/python/uri.py"),
            Path("packages/stitcher-lang-python/src/stitcher/lang/python/uri.py"),
        )
    )

    # --- 2. 从 stitcher-python-analysis 迁移 ---

    # 迁移分析模型与基础工具
    spec.add(
        Move(
            Path(
                "packages/stitcher-python-analysis/src/stitcher/python/analysis/models.py"
            ),
            Path(
                "packages/stitcher-lang-python/src/stitcher/lang/python/analysis/models.py"
            ),
        )
    )
    spec.add(
        Move(
            Path(
                "packages/stitcher-python-analysis/src/stitcher/python/analysis/scope.py"
            ),
            Path(
                "packages/stitcher-lang-python/src/stitcher/lang/python/analysis/scope.py"
            ),
        )
    )
    spec.add(
        Move(
            Path(
                "packages/stitcher-python-analysis/src/stitcher/python/analysis/utils.py"
            ),
            Path(
                "packages/stitcher-lang-python/src/stitcher/lang/python/analysis/utils.py"
            ),
        )
    )

    # 迁移分析访问器 (Analysis Visitors)
    spec.add(
        Move(
            Path(
                "packages/stitcher-python-analysis/src/stitcher/python/analysis/cst/visitors.py"
            ),
            Path(
                "packages/stitcher-lang-python/src/stitcher/lang/python/analysis/visitors.py"
            ),
        )
    )
    spec.add(
        Move(
            Path(
                "packages/stitcher-python-analysis/src/stitcher/python/analysis/cst/usage_visitor.py"
            ),
            Path(
                "packages/stitcher-lang-python/src/stitcher/lang/python/analysis/usage_visitor.py"
            ),
        )
    )

    # 迁移重构转换器 (Refactor/Transform Visitors)
    spec.add(
        Move(
            Path(
                "packages/stitcher-python-analysis/src/stitcher/python/analysis/cst/transformers.py"
            ),
            Path(
                "packages/stitcher-lang-python/src/stitcher/lang/python/transform/cst_visitors.py"
            ),
        )
    )
    spec.add(
        Move(
            Path(
                "packages/stitcher-python-analysis/src/stitcher/python/analysis/cst/rename_transformers.py"
            ),
            Path(
                "packages/stitcher-lang-python/src/stitcher/lang/python/transform/rename.py"
            ),
        )
    )

    # --- 3. 迁移测试用例 (可选但建议) ---
    # spec.add(MoveDir(
    #     Path("packages/stitcher-python-adapter/tests"),
    #     Path("packages/stitcher-lang-python/tests/adapter")
    # ))
    # spec.add(MoveDir(
    #     Path("packages/stitcher-python-analysis/tests"),
    #     Path("packages/stitcher-lang-python/tests/analysis")
    # ))
