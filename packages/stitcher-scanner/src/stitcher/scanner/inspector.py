import inspect
import importlib
from typing import Callable, Any
from stitcher.spec import Argument, ArgumentKind, FunctionDef


class InspectionError(Exception):
    pass


def _map_param_kind(kind: inspect._ParameterKind) -> ArgumentKind:
    if kind == inspect.Parameter.POSITIONAL_ONLY:
        return ArgumentKind.POSITIONAL_ONLY
    if kind == inspect.Parameter.POSITIONAL_OR_KEYWORD:
        return ArgumentKind.POSITIONAL_OR_KEYWORD
    if kind == inspect.Parameter.VAR_POSITIONAL:
        return ArgumentKind.VAR_POSITIONAL
    if kind == inspect.Parameter.KEYWORD_ONLY:
        return ArgumentKind.KEYWORD_ONLY
    if kind == inspect.Parameter.VAR_KEYWORD:
        return ArgumentKind.VAR_KEYWORD
    raise ValueError(f"Unknown parameter kind: {kind}")


def _get_annotation_str(annotation: Any) -> str:
    if annotation == inspect.Parameter.empty:
        return ""

    # Handle generic types from typing module
    if hasattr(annotation, "__origin__"):
        return str(annotation).replace("typing.", "")

    if hasattr(annotation, "__name__"):
        return annotation.__name__

    return str(annotation)


def parse_plugin_entry(entry_point_str: str) -> FunctionDef:
    try:
        module_str, callable_str = entry_point_str.split(":", 1)
        module = importlib.import_module(module_str)
        target_callable: Callable = getattr(module, callable_str)
    except (ImportError, AttributeError, ValueError) as e:
        raise InspectionError(
            f"Could not load entry point '{entry_point_str}': {e}"
        ) from e

    try:
        signature = inspect.signature(target_callable)
        docstring = inspect.getdoc(target_callable)
    except (TypeError, ValueError) as e:
        raise InspectionError(
            f"Could not inspect signature of '{entry_point_str}': {e}"
        ) from e

    # Build arguments
    args: list[Argument] = []
    for param in signature.parameters.values():
        default_val = None
        if param.default != inspect.Parameter.empty:
            default_val = repr(param.default)

        args.append(
            Argument(
                name=param.name,
                kind=_map_param_kind(param.kind),
                annotation=_get_annotation_str(param.annotation) or None,
                default=default_val,
            )
        )

    # Build FunctionDef
    return_annotation = _get_annotation_str(signature.return_annotation)
    func_name = target_callable.__name__

    return FunctionDef(
        name=func_name,
        args=args,
        docstring=docstring,
        return_annotation=return_annotation or None,
        is_async=inspect.iscoroutinefunction(target_callable),
    )
