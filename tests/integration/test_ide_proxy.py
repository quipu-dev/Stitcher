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

    source_content = "class ProxyModel:\n    def get_id(self) -> int:\n        return 1"

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
        "src/ide_proxy/py.typed", ""  # The final piece of the puzzle for PEP 561
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

    # --- Part 2: Verify Precedence (Stub > Source) ---

    # 8. Modify the stub file to remove the return type annotation.
    # We locate the generated .pyi file in the source stub package directory.
    # Namespace is "ide_proxy", so dir is "ide_proxy-stubs".
    pyi_path = stub_pkg_path / "src" / "ide_proxy-stubs" / "models.pyi"
    assert pyi_path.exists()

    # Replace "-> int" with "" (stripping type info)
    original_pyi_content = pyi_path.read_text()
    stripped_pyi_content = original_pyi_content.replace("-> int", "")
    pyi_path.write_text(stripped_pyi_content)

    # 9. Reinstall the modified stub package to update site-packages.
    # We use --force-reinstall to ensure pip updates the files.
    isolated_env.install("--force-reinstall", str(stub_pkg_path))

    # 10. Run Pyright again.
    # Now that the stub has no return type, Pyright should treat it as Unknown/Any,
    # IGNORING the source code which still has "-> int".
    # This proves Pyright is indeed reading the .pyi file, not the .py file.
    result_stripped = isolated_env.run_pyright_check(
        Path("."), verbose=True, cwd=client_project_dir
    )

    assert result_stripped.returncode == 0
    # Pyright default for unannotated return is Unknown
    assert 'Type of "instance.get_id()" is "Unknown"' in result_stripped.stdout, (
        f"Pyright should have fallen back to Unknown after stripping stubs.\n"
        f"This implies it might be reading source code instead of stubs.\n"
        f"STDOUT:\n{result_stripped.stdout}"
    )