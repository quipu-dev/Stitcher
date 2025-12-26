import inspect
import importlib
from typing import Callable, Any
from stitcher.spec import Argument, ArgumentKind, FunctionDef

def _map_param_kind(kind: inspect._ParameterKind) -> ArgumentKind:
    """Maps inspect's ParameterKind enum to our own."""
    ...

def _get_annotation_str(annotation: Any) -> str:
    """Gets a string representation of a type annotation."""
    ...

def parse_plugin_entry(entry_point_str: str) -> FunctionDef:
    """
    Dynamically imports and inspects a callable from an entry point string
and converts it into a Stitcher FunctionDef IR object.

Args:
    entry_point_str: The import string (e.g., "my_pkg.main:my_func").

Returns:
    A FunctionDef instance representing the inspected callable.

Raises:
    InspectionError: If the entry point cannot be loaded or inspected.
    """
    ...

class InspectionError(Exception):
    """Custom exception for errors during plugin inspection."""