__path__ = __import__("pkgutil").extend_path(__path__, __name__)

import os
from pathlib import Path
from typing import Dict
from needle.pointer import L
from needle.operators import I18NFactoryOperator, OverlayOperator
from needle.runtime import _find_project_root
from .formatting import format_docstring, parse_docstring
from stitcher.bus.bus import FeedbackBus
from stitcher.spec.persistence import DocumentAdapter

# --- Composition Root ---

# 1. Config Sources
# We determine roots once at startup.
_project_root = _find_project_root()
_common_assets_root = Path(__file__).parent / "assets"

# 2. Factories
# Create factories for each layer.
# Note: User overrides live in .stitcher/needle, defaults in needle/.
# This path logic is technically part of the factory configuration.

# For user overrides, the root passed to Factory is the project root + .stitcher
# because Factory expects `root / needle / {lang}` structure?
# Wait, I18NFactory implementation does `root / needle / lang`.
# User overrides are at `project_root / .stitcher / needle / lang`.
# So we pass `project_root / .stitcher` as the root to the user factory.
_user_factory = I18NFactoryOperator(_project_root / ".stitcher")
_default_factory = I18NFactoryOperator(_common_assets_root)

# 3. Dynamic Pipeline with Caching
_operator_cache: Dict[str, OverlayOperator] = {}


def _detect_lang() -> str:
    # 1. Explicit override
    stitcher_lang = os.getenv("STITCHER_LANG")
    if stitcher_lang:
        return stitcher_lang

    # 2. System LANG (e.g. "zh_CN.UTF-8" -> "zh")
    sys_lang = os.getenv("LANG")
    if sys_lang:
        # Extract "zh" from "zh_CN.UTF-8" or "en_US"
        # Split by '.' first to remove encoding, then '_' to remove territory
        base_lang = sys_lang.split(".")[0].split("_")[0]
        if base_lang:
            return base_lang

    # 3. Default fallback
    return "en"


def get_current_renderer() -> OverlayOperator:
    lang_code = _detect_lang()

    if lang_code in _operator_cache:
        return _operator_cache[lang_code]

    # Construct the pipeline on demand
    # L.en or L.zh based on env string
    # We use a simple pointer construction here.
    lang_ptr = getattr(L, lang_code)

    user_op = _user_factory(lang_ptr)
    default_op = _default_factory(lang_ptr)

    # Priority: User > Default
    pipeline = OverlayOperator([user_op, default_op])

    _operator_cache[lang_code] = pipeline
    return pipeline


# 4. Message Bus
# The bus needs an object that has a __call__ (OperatorProtocol).
# We pass a proxy lambda that delegates to the current renderer.
# This ensures that if the env var changes, the next call picks it up (if we cleared cache)
# or at least allows dynamic resolution per call if we didn't cache aggressively.
# Given the cache above, it's 'Session Scope' caching.

# 4. Message Bus
# We pass a lambda that delegates to the current renderer.
# This ensures that we always use the latest operator from the cache (or rebuild it if cache cleared).
# Using a simple function instead of a Proxy class.


def stitcher_operator(key):
    renderer = get_current_renderer()
    return renderer(key)


bus = FeedbackBus(operator=stitcher_operator)


__all__ = [
    "bus",
    "stitcher_operator",
    "format_docstring",
    "parse_docstring",
    "DocumentAdapter",
]
