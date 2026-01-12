from pathlib import Path
from stitcher.refactor.migration import MigrationSpec, Move, MoveDir

def upgrade(spec: MigrationSpec):
    """
    Stitcher 架构重构阶段二：语言能力统一与合并 (Python)
    
    此脚本将分散在 stitcher-python-adapter 和 stitcher-python-analysis 中的功能
    合并到统一的 stitcher-lang-python 包中，建立清晰的层级结构（parser, transform, docstring）。
    """
    
    # --- 1. 迁移解析能力 (Parsing) ---
    # griffe_parser.py -> parser/griffe.py
    spec.add(Move(
        Path("packages/stitcher-python-adapter/src/stitcher/adapter/python/griffe_parser.py"),
        Path("packages/stitcher-lang-python/src/stitcher/lang/python/parser/griffe.py")
    ))
    
    # internal/parser.py -> parser/cst.py
    spec.add(Move(
        Path("packages/stitcher-python-adapter/src/stitcher/adapter/python/internal/parser.py"),
        Path("packages/stitcher-lang-python/src/stitcher/lang/python/parser/cst.py")
    ))

    # --- 2. 迁移索引能力 (Indexing/Adapting) ---
    # index_adapter.py -> adapter.py
    spec.add(Move(
        Path("packages/stitcher-python-adapter/src/stitcher/adapter/python/index_adapter.py"),
        Path("packages/stitcher-lang-python/src/stitcher/lang/python/adapter.py")
    ))

    # --- 3. 迁移文档能力 (Docstrings) ---
    # docstring/ (整个目录)
    spec.add(MoveDir(
        Path("packages/stitcher-python-adapter/src/stitcher/adapter/python/docstring"),
        Path("packages/stitcher-lang-python/src/stitcher/lang/python/docstring")
    ))

    # --- 4. 迁移转换能力 (Transforming) ---
    # internal/transformer.py -> transform/facade.py
    spec.add(Move(
        Path("packages/stitcher-python-adapter/src/stitcher/adapter/python/internal/transformer.py"),
        Path("packages/stitcher-lang-python/src/stitcher/lang/python/transform/facade.py")
    ))
    
    # 根据路线图: visitors.py -> transform/cst_visitors.py
    spec.add(Move(
        Path("packages/stitcher-python-analysis/src/stitcher/analysis/python/visitors.py"),
        Path("packages/stitcher-lang-python/src/stitcher/lang/python/transform/cst_visitors.py")
    ))

    # --- 5. 迁移分析模型 (Analysis Models) ---
    # models.py -> analysis/models.py
    spec.add(Move(
        Path("packages/stitcher-python-analysis/src/stitcher/analysis/python/models.py"),
        Path("packages/stitcher-lang-python/src/stitcher/lang/python/analysis/models.py")
    ))