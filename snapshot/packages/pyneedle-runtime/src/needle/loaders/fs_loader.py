import os
from pathlib import Path
from typing import Dict, List, Any, Optional, Union

from needle.spec import WritableResourceLoaderProtocol, SemanticPointerProtocol
from needle.nexus import BaseLoader
from .protocols import FileHandlerProtocol
from .json_handler import JsonHandler


class FileSystemLoader(BaseLoader, WritableResourceLoaderProtocol):
    def __init__(
        self,
        roots: Optional[List[Path]] = None,
        handlers: Optional[List[FileHandlerProtocol]] = None,
        default_domain: str = "en",
    ):
        super().__init__(default_domain)
        self.handlers = handlers or [JsonHandler()]
        self.roots = roots or [self._find_project_root()]
        
        # Cache structure: Path -> { key: value }
        # This caches the CONTENT of files, not the domain view.
        self._file_cache: Dict[Path, Dict[str, Any]] = {}

    def _find_project_root(self, start_dir: Optional[Path] = None) -> Path:
        current_dir = (start_dir or Path.cwd()).resolve()
        while current_dir.parent != current_dir:
            if (current_dir / "pyproject.toml").is_file() or (
                current_dir / ".git"
            ).is_dir():
                return current_dir
            current_dir = current_dir.parent
        return start_dir or Path.cwd()

    def add_root(self, path: Path):
        if path not in self.roots:
            self.roots.insert(0, path)

    def _get_candidate_paths(self, domain: str, parts: List[str]) -> List[Path]:
        """
        Implements simplified SST probing logic.
        For pointer 'a.b.c':
        1. <root>/needle/<domain>/a/b.json (key: c)
        2. <root>/needle/<domain>/a.json   (key: b.c)
        3. <root>/needle/<domain>/__init__.json (key: a.b.c)
        
        Plus .stitcher/needle/... variants.
        """
        candidates = []
        
        # Heuristic 1: Namespace file (a/b.json)
        if len(parts) >= 2:
            rel_path = Path(*parts[: len(parts) - 1]).with_suffix(".json")
            candidates.append(rel_path)
            
        # Heuristic 2: Category file (a.json)
        if len(parts) >= 1:
             rel_path = Path(parts[0]).with_suffix(".json")
             candidates.append(rel_path)
             
        # Heuristic 3: Root file
        candidates.append(Path("__init__.json"))
        
        return candidates

    def _read_file(self, path: Path, ignore_cache: bool) -> Optional[Dict[str, Any]]:
        if not ignore_cache and path in self._file_cache:
            return self._file_cache[path]
            
        if not path.is_file():
            return None
            
        for handler in self.handlers:
            if handler.match(path):
                data = handler.load(path)
                # Store in cache
                self._file_cache[path] = data
                return data
        return None

    def fetch(
        self,
        pointer: Union[str, SemanticPointerProtocol],
        domain: str,
        ignore_cache: bool = False,
    ) -> Optional[str]:
        key_str = str(pointer)
        parts = key_str.split(".")
        
        candidates = self._get_candidate_paths(domain, parts)
        
        for root in self.roots:
            # We need to check both .stitcher/needle and needle/ locations
            # Order: .stitcher (hidden) > needle (packaged)
            base_dirs = [
                root / ".stitcher" / "needle" / domain,
                root / "needle" / domain
            ]
            
            for base_dir in base_dirs:
                for rel_path in candidates:
                    full_path = base_dir / rel_path
                    
                    data = self._read_file(full_path, ignore_cache)
                    if data:
                        # Extract value from data using the remaining key parts
                        # SST Logic:
                        # If file is a/b.json, key in file is 'c' (parts[-1])
                        # If file is a.json, key in file is 'b.c'
                        
                        # Determine the suffix key within the file
                        # We reverse-engineer based on path name
                        if rel_path.name == "__init__.json":
                            internal_key = key_str
                        else:
                            # Remove the path parts from the full key to get internal key
                            # e.g. key=a.b.c, path=a/b.json -> stem=b -> internal=c
                            # But wait, 'a/b.json' implies we consumed 'a' and 'b'.
                            # Simplified logic:
                            # We just check if the FULL FQN key exists (SST FQN Contract),
                            # OR if the suffix exists.
                            
                            # SST Recommendation: Keys in file SHOULD be FQN.
                            # "auth.login.success": "..."
                            # But we also support nested structure if loaded as JSON.
                            # Current JSONHandler returns flattened dict? No, it returns raw dict.
                            # And we need to support flat FQN keys.
                            
                            # Let's try direct lookup first (FQN match)
                            if key_str in data:
                                return str(data[key_str])
                                
                            # If not found, we might need traversal if JSON is nested.
                            # For MVP, let's assume flat FQN keys or simple matches.
                            pass
                            
        return None

    def load(self, domain: str, ignore_cache: bool = False) -> Dict[str, Any]:
        """
        Full scan implementation for dumps.
        """
        merged_registry: Dict[str, str] = {}
        # ... logic similar to previous load, but using _read_file to populate cache ...
        for root in self.roots:
            base_dirs = [
                 root / "needle" / domain, # Load low priority first
                 root / ".stitcher" / "needle" / domain
            ]
            
            for base_dir in base_dirs:
                if not base_dir.is_dir(): continue
                for dirpath, _, filenames in os.walk(base_dir):
                    for filename in filenames:
                        file_path = Path(dirpath) / filename
                        data = self._read_file(file_path, ignore_cache)
                        if data:
                            # Flatten
                            for k, v in data.items():
                                merged_registry[str(k)] = str(v)
                                
        return merged_registry

    def locate(self, pointer: Union[str, SemanticPointerProtocol], domain: str) -> Path:
        # Simple write location logic (same as before for MVP)
        root = self.roots[0]
        parts = str(pointer).split(".")
        base_dir = root / ".stitcher" / "needle" / domain
        
        if len(parts) >= 3:
            relative = Path(*parts[:2]).with_suffix(".json")
        elif len(parts) == 2:
            relative = Path(parts[0]).with_suffix(".json")
        else:
            relative = Path("__init__.json")
            
        return base_dir / relative

    def put(
        self, pointer: Union[str, SemanticPointerProtocol], value: Any, domain: str
    ) -> bool:
        key = str(pointer)
        target_path = self.locate(key, domain)
        
        handler = self.handlers[0] # Assume JSON
        
        # Load raw without cache to ensure atomic write on latest state
        data = {}
        if target_path.exists():
             data = handler.load(target_path)
             
        data[key] = str(value)
        
        success = handler.save(target_path, data)
        if success:
            # Invalidate cache for this file
            if target_path in self._file_cache:
                del self._file_cache[target_path]
                
        return success