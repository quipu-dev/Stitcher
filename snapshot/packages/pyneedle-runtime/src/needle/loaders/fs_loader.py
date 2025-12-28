import os
from pathlib import Path
from typing import Dict, List, Any, Optional, Union, Tuple
from collections import ChainMap

from .protocols import FileHandlerProtocol
from .json_handler import JsonHandler

from needle.spec import WritableResourceLoaderProtocol
from needle.nexus import BaseLoader


class FileSystemLoader(BaseLoader, WritableResourceLoaderProtocol):
    def __init__(
        self,
        roots: Optional[List[Path]] = None,
        handlers: Optional[List[FileHandlerProtocol]] = None,
        default_domain: str = "en",
    ):
        super().__init__(default_domain)
        self.handlers = handlers or [JsonHandler()]
        # Roots are strictly provided by the caller. No auto-discovery here.
        self.roots = roots or []
        
        # Cache structure: domain -> List of (Path, flattened_dict)
        # Order: High priority -> Low priority
        self._layer_cache: Dict[str, List[Tuple[Path, Dict[str, str]]]] = {}

    def add_root(self, path: Path):
        """Add a new root with highest priority."""
        if path not in self.roots:
            self.roots.insert(0, path)
            self._layer_cache.clear() # Invalidate cache

    def _ensure_layers(self, domain: str) -> List[Tuple[Path, Dict[str, str]]]:
        if domain not in self._layer_cache:
            self._layer_cache[domain] = self._scan_layers(domain)
        return self._layer_cache[domain]

    def _scan_layers(self, domain: str) -> List[Tuple[Path, Dict[str, str]]]:
        layers: List[Tuple[Path, Dict[str, str]]] = []
        
        # Scan roots in order (High Priority -> Low Priority)
        for root in self.roots:
            # 1. Project overrides: .stitcher/needle/<domain>
            hidden_path = root / ".stitcher" / "needle" / domain
            if hidden_path.is_dir():
                layers.extend(self._scan_directory(hidden_path))
            
            # 2. Package assets: needle/<domain>
            asset_path = root / "needle" / domain
            if asset_path.is_dir():
                layers.extend(self._scan_directory(asset_path))
                
        return layers

    def _scan_directory(self, root_path: Path) -> List[Tuple[Path, Dict[str, str]]]:
        """
        Scans a directory for supported files.
        Returns a list of layers. 
        Note: The order of files within a directory is OS-dependent, 
        but we process them deterministically if needed.
        """
        layers = []
        # We walk top-down.
        for dirpath, _, filenames in os.walk(root_path):
            # Sort filenames to ensure deterministic loading order
            for filename in sorted(filenames):
                file_path = Path(dirpath) / filename
                for handler in self.handlers:
                    if handler.match(file_path):
                        # Handler is responsible for flattening
                        content = handler.load(file_path)
                        # Ensure content is strictly Dict[str, str]
                        str_content = {str(k): str(v) for k, v in content.items()}
                        layers.append((file_path, str_content))
                        break # Only use the first matching handler per file
        return layers

    def fetch(
        self, pointer: str, domain: str, ignore_cache: bool = False
    ) -> Optional[str]:
        if ignore_cache:
            self._layer_cache.pop(domain, None)
            
        layers = self._ensure_layers(domain)
        
        # Optimization: Build a ChainMap only if needed, or query layers directly?
        # SST v2.2 suggests "fetch uses ChainMap view".
        # Let's create a transient ChainMap for the lookup.
        # layers is [(p1, d1), (p2, d2)...]
        # ChainMap expects maps in priority order. Our list is already High->Low.
        if not layers:
            return None
            
        # Extract just the dicts
        maps = [d for _, d in layers]
        return ChainMap(*maps).get(pointer)

    def load(self, domain: str, ignore_cache: bool = False) -> Dict[str, Any]:
        """Returns the aggregated view of the domain."""
        if ignore_cache:
            self._layer_cache.pop(domain, None)
            
        layers = self._ensure_layers(domain)
        if not layers:
            return {}
            
        maps = [d for _, d in layers]
        # Convert ChainMap to a single dict for the return value
        return dict(ChainMap(*maps))

    def locate(self, pointer: Union[str, Any], domain: str) -> Path:
        key = str(pointer)
        layers = self._ensure_layers(domain)
        
        # Traverse layers to find the anchor
        for file_path, data in layers:
            if key in data:
                return file_path
        
        # Not found? Predict the write path (Create Logic)
        return self._predict_write_path(key, domain)

    def _predict_write_path(self, key: str, domain: str) -> Path:
        """
        Determines where to create a NEW key.
        Strategy: 
        1. Use the highest priority root.
        2. Use .stitcher/needle/<domain> base.
        3. Simple heuristic: First segment of key as filename.
        """
        if not self.roots:
            raise RuntimeError("No roots configured for FileSystemLoader")
            
        root = self.roots[0]
        base_dir = root / ".stitcher" / "needle" / domain
        
        parts = key.split(".")
        filename = f"{parts[0]}.json" # Default to JSON
        return base_dir / filename

    def put(self, pointer: Union[str, Any], value: Any, domain: str) -> bool:
        key = str(pointer)
        str_value = str(value)
        
        # 1. Locate the anchor (or predicted path)
        target_path = self.locate(key, domain)
        
        # 2. Find the layer in memory, or create if new
        layers = self._ensure_layers(domain)
        target_layer_idx = -1
        
        for idx, (path, _) in enumerate(layers):
            if path == target_path:
                target_layer_idx = idx
                break
        
        # 3. Update memory
        if target_layer_idx != -1:
            # Update existing layer
            layers[target_layer_idx][1][key] = str_value
            data_to_save = layers[target_layer_idx][1]
        else:
            # Create new layer
            new_data = {key: str_value}
            # Insert at the beginning (High Priority for new user overrides)
            # But wait, we need to respect the root order.
            # _predict_write_path uses roots[0], so inserting at 0 is correct 
            # IF layers are sorted by root. 
            # (Our _scan_layers puts roots[0] stuff first).
            layers.insert(0, (target_path, new_data))
            data_to_save = new_data

        # 4. Flush to disk (Inflate -> Save)
        # Assume JSON handler for now or find matching handler
        handler = self.handlers[0] # Default to first (JSON)
        # Try to find a handler that matches the target_path extension
        for h in self.handlers:
            if h.match(target_path):
                handler = h
                break
                
        return handler.save(target_path, data_to_save)