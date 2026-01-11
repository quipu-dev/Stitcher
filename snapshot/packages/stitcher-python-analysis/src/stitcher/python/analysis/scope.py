from typing import Dict
from stitcher.spec import ModuleDef


class ScopeAnalyzer:
    def build_from_ir(
        self, module: ModuleDef, logical_module_fqn: str
    ) -> Dict[str, str]:
        local_symbols: Dict[str, str] = {}

        # 1. Register imported aliases (e.g., 'helper' -> 'pkg.utils.helper')
        for attr in module.attributes:
            if attr.alias_target:
                local_symbols[attr.name] = attr.alias_target

        # 2. Register local definitions
        def register_local(name: str, parent_fqn: str = "") -> str:
            fqn = (
                f"{parent_fqn}.{name}" if parent_fqn else f"{logical_module_fqn}.{name}"
            )
            local_symbols[name] = fqn
            return fqn

        for func in module.functions:
            register_local(func.name)

        for cls in module.classes:
            # cls_fqn = register_local(cls.name)
            # Register class-level aliases
            for attr in cls.attributes:
                if attr.alias_target:
                    local_symbols[attr.name] = attr.alias_target
            # Methods are handled by visitor's scope analysis (e.g., self.method)

        return local_symbols
