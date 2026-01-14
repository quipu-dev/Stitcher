from pathlib import Path

try:
    import tomllib
except ImportError:
    import tomli as tomllib  # type: ignore

from .exceptions import WorkspaceNotFoundError


def find_workspace_root(start_path: Path) -> Path:
    current = start_path.resolve()
    # If start_path is a file, start from its parent
    if current.is_file():
        current = current.parent

    # Traverse upwards
    for parent in [current] + list(current.parents):
        # 1. Check for .git (strongest indicator)
        if (parent / ".git").exists():
            return parent

        # 2. Check for pyproject.toml with workspace definition (stronger indicator)
        pyproject = parent / "pyproject.toml"
        if pyproject.exists():
            try:
                with pyproject.open("rb") as f:
                    data = tomllib.load(f)
                # Check for uv workspace or similar tools
                if (
                    "tool" in data
                    and "uv" in data["tool"]
                    and "workspace" in data["tool"]["uv"]
                ):
                    return parent
            except Exception:
                pass  # Ignore malformed toml files, let the third check handle it

        # 3. Fallback to any pyproject.toml as a root indicator (for simple projects/tests)
        if pyproject.exists():
            return parent

    # No root found in the entire hierarchy
    raise WorkspaceNotFoundError(str(start_path))
