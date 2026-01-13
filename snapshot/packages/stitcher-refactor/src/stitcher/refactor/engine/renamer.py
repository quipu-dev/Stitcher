import libcst as cst
from collections import defaultdict
from typing import List, Dict, Optional
from pathlib import Path
import json
from ruamel.yaml import YAML

from stitcher.refactor.engine.context import RefactorContext
from stitcher.common.transaction import WriteFileOp
from stitcher.lang.python.analysis.models import UsageLocation, ReferenceType
from stitcher.lang.python.transform.rename import SymbolRenamerTransformer
from stitcher.lang.python.uri import SURIGenerator

class GlobalBatchRenamer:
    def __init__(self, rename_map: Dict[str, str], ctx: RefactorContext):
        self.rename_map = rename_map
        self.ctx = ctx
        self._yaml_loader = YAML()

    def analyze(self) -> List[WriteFileOp]:
        ops: List[WriteFileOp] = []
        usages_by_file: Dict[Path, List[UsageLocation]] = defaultdict(list)

        # 1. Collect all usages for all renames and group by file
        for old_fqn in self.rename_map.keys():
            usages = self.ctx.graph.find_usages(old_fqn)
            for usage in usages:
                usages_by_file[usage.file_path].append(usage)

        # 2. For each affected file, apply the correct update strategy
        for file_path, file_usages in usages_by_file.items():
            try:
                original_source = file_path.read_text(encoding="utf-8")
                new_source: Optional[str] = None

                if file_path.suffix == ".py":
                    new_source = self._update_python_content(original_source, file_usages)
                elif file_path.suffix in (".yml", ".yaml"):
                    new_source = self._update_yaml_content(original_source, file_usages)
                elif file_path.suffix == ".json":
                    new_source = self._update_json_content(original_source, file_usages)
                
                if new_source is not None and new_source != original_source:
                    relative_path = file_path.relative_to(self.ctx.graph.root_path)
                    ops.append(WriteFileOp(path=relative_path, content=new_source))

            except Exception as e:
                # In a real app, we'd log this, but for now, re-raise
                # Add context to the error
                raise RuntimeError(f"Failed to process refactoring for file {file_path}: {e}") from e
        return ops

    def _update_python_content(self, source: str, usages: List[UsageLocation]) -> str:
        module = cst.parse_module(source)
        wrapper = cst.MetadataWrapper(module)
        transformer = SymbolRenamerTransformer(self.rename_map, usages)
        modified_module = wrapper.visit(transformer)
        return modified_module.code

    def _update_yaml_content(self, source: str, usages: List[UsageLocation]) -> str:
        # For YAML, we replace FQN keys.
        # This is a simple string replacement for now, assuming keys are unique.
        # A more robust solution would use ruamel.yaml to load, modify, and dump.
        new_source = source
        for usage in usages:
            if usage.ref_type == ReferenceType.SIDECAR_NAME:
                old_fqn = usage.target_node_fqn
                new_fqn = self.rename_map.get(old_fqn)
                if new_fqn:
                    # Simple, but potentially risky if FQN appears as a value.
                    # The usage location gives us line info, but key replacement is sufficient for now.
                    new_source = new_source.replace(f"{old_fqn}:", f"{new_fqn}:")
        return new_source
    
    def _update_json_content(self, source: str, usages: List[UsageLocation]) -> str:
        # For JSON, we replace SURI keys by modifying the fragment.
        data = json.loads(source)
        new_data = data.copy()
        
        for usage in usages:
            if usage.ref_type == ReferenceType.SIDECAR_ID:
                # The usage's target_node_fqn is the FQN of the symbol *inside* the SURI.
                old_fqn = usage.target_node_fqn
                new_fqn = self.rename_map.get(old_fqn)

                if new_fqn:
                    # Find the SURI key that contains this FQN.
                    # This requires iterating through keys and parsing them.
                    for suri_key in list(new_data.keys()):
                        try:
                            path, fragment = SURIGenerator.parse(suri_key)
                            # The fragment is what needs to be renamed
                            if fragment == old_fqn.split('.', 1)[-1]: # Heuristic
                                new_fragment = new_fqn.split('.', 1)[-1]
                                new_suri = SURIGenerator.for_symbol(path, new_fragment)
                                if new_suri != suri_key:
                                    new_data[new_suri] = new_data.pop(suri_key)
                        except (ValueError, IndexError):
                            continue
                            
        return json.dumps(new_data, indent=2, sort_keys=True)
