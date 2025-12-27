import sys
from pathlib import Path

if sys.version_info < (3, 11):
    import tomli as tomllib
else:
    import tomllib

from stitcher.app import StitcherApp
from stitcher.test_utils import WorkspaceFactory


def _get_dir_structure(root_path: Path) -> str:
    """Helper to get a string representation of the directory structure."""
    lines = []
    for path in sorted(root_path.rglob("*")):
        relative_path = path.relative_to(root_path)
        indent = "  " * (len(relative_path.parts) - 1)
        lines.append(f"{indent}- {path.name}{'/' if path.is_dir() else ''}")
    return "\n".join(lines)


def test_pep561_structure_compliance(tmp_path: Path):
    """
    Verifies that generated stub packages comply with PEP 561 naming conventions
    for both package name and the source directory inside the package.
    """
    # 1. Arrange
    project_name = "my-project"
    namespace = "my_project"
    stub_dir_name = "stubs"

    factory = WorkspaceFactory(tmp_path)
    project_root = (
        factory.with_project_name(project_name)
        .with_config({"scan_paths": [f"src/{namespace}"], "stub_package": stub_dir_name})
        .with_source(f"src/{namespace}/main.py", "def func(): ...")
        .build()
    )

    app = StitcherApp(root_path=project_root)

    # 2. Act
    app.run_from_config()

    # 3. Assert
    stub_pkg_path = project_root / stub_dir_name
    stub_toml_path = stub_pkg_path / "pyproject.toml"

    # For debugging:
    dir_structure = _get_dir_structure(stub_pkg_path)
    debug_message = f"Generated directory structure:\n{dir_structure}"

    # 3.1. Assert pyproject.toml name is correct
    assert stub_toml_path.is_file(), f"pyproject.toml not found.\n{debug_message}"
    with stub_toml_path.open("rb") as f:
        config = tomllib.load(f)
    assert config["project"]["name"] == f"{project_name}-stubs"

    # 3.2. Assert src directory is named correctly (<namespace>-stubs)
    expected_src_dir = stub_pkg_path / "src" / f"{namespace}-stubs"
    incorrect_src_dir = stub_pkg_path / "src" / namespace

    assert expected_src_dir.is_dir(), f"Expected src dir not found.\n{debug_message}"
    assert (
        not incorrect_src_dir.exists()
    ), f"Incorrectly named src dir found.\n{debug_message}"

    # 3.3. Assert Hatch config points to the correct directory
    hatch_packages = config["tool"]["hatch"]["build"]["targets"]["wheel"]["packages"]
    assert hatch_packages == [f"src/{namespace}-stubs"]