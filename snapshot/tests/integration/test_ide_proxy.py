import json
from pathlib import Path
from stitcher.app import StitcherApp
from stitcher.test_utils import WorkspaceFactory, VenvHarness


def test_pyright_resolves_types_from_stubs(
    tmp_path: Path, isolated_env: VenvHarness
):
    """
    Verifies that Pyright can resolve types from a generated stub package by
    running it from a controlled working directory with an explicit pyright
    config. This is the definitive test for IDE compatibility.
    """
    # --- ARRANGE ---

    source_content = "class ProxyModel:\n    def get_id(self):\n        return 1"

    # 1. Create the source project for Stitcher to scan.
    source_project_root = tmp_path / "source_project"
    WorkspaceFactory(source_project_root).with_project_name(
        "ide-proxy-proj"
    ).with_config(
        {"scan_paths": ["src/ide_proxy"], "stub_package": "stubs"}
    ).with_source(
        "src/ide_proxy/models.py", source_content
    ).build()

    # 2. Create a correctly configured, installable RUNTIME package.
    runtime_project_root = tmp_path / "runtime_project"
    WorkspaceFactory(runtime_project_root).with_source(
        "src/ide_proxy/models.py", source_content
    ).with_source(
        "src/ide_proxy/__init__.py",
        "__path__ = __import__('pkgutil').extend_path(__path__, __name__)",
    ).with_source(
        "pyproject.toml",
        """
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
[project]
name = "ide-proxy-proj"
version = "0.1.0"
[tool.hatch.build.targets.wheel]
packages = ["src/ide_proxy"]
""",
    ).build()

    # --- ACT ---

    # 3. Generate the stub package.
    app = StitcherApp(root_path=source_project_root)
    app.run_from_config()
    stub_pkg_path = source_project_root / "stubs"

    # 4. Install BOTH packages into the isolated venv.
    isolated_env.install(str(runtime_project_root))
    isolated_env.install(str(stub_pkg_path))

    # 5. Create a client project directory with code and pyright config.
    client_project_dir = tmp_path / "client_project"
    client_project_dir.mkdir()
    (client_project_dir / "main.py").write_text(
        "from ide_proxy.models import ProxyModel\n\n"
        "instance = ProxyModel()\n"
        "reveal_type(instance.get_id())\n"
    )

    # 6. Create the pyrightconfig.json.
    pyright_config_path = client_project_dir / "pyrightconfig.json"
    site_packages = isolated_env.get_site_packages_path()
    pyright_config = {"extraPaths": [str(site_packages)]}
    pyright_config_path.write_text(json.dumps(pyright_config))

    # 7. *** THE DEFINITIVE FIX ***
    #    Run Pyright check from within the client project directory.
    #    We check "." which means "the current directory".
    result = isolated_env.run_pyright_check(
        Path("."), verbose=True, cwd=client_project_dir
    )

    # --- ASSERT ---

    diagnostic_info = f"""
    --- PYRIGHT CONFIG ---
{json.dumps(pyright_config, indent=2)}
    ---
    [PYRIGHT VERBOSE OUTPUT]
    STDOUT:
{result.stdout}
    STDERR:
{result.stderr}
    """

    assert result.returncode == 0, f"Pyright failed with errors.\n{diagnostic_info}"
    assert "0 errors" in result.stdout, f"Pyright reported errors.\n{diagnostic_info}"
    assert (
        'Type of "instance.get_id()" is "int"' in result.stdout
    ), f"Pyright did not resolve the return type correctly.\n{diagnostic_info}"