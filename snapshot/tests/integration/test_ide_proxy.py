from pathlib import Path
from stitcher.app import StitcherApp
from stitcher.test_utils import WorkspaceFactory, VenvHarness


def test_pyright_resolves_types_from_stubs(
    tmp_path: Path, isolated_env: VenvHarness
):
    """
    Verifies that Pyright can resolve types from a generated stub package,
    simulating the IDE experience in a realistic environment where both the
    runtime and stub packages are installed.
    """
    # --- ARRANGE ---

    # 1. Define shared source code (no type hints in runtime).
    source_content = "class ProxyModel:\n    def get_id(self):\n        return 1"

    # 2. Create the source project for Stitcher to scan.
    source_project_root = tmp_path / "source_project"
    WorkspaceFactory(source_project_root).with_project_name(
        "ide-proxy-proj"
    ).with_config(
        {"scan_paths": ["src/ide_proxy"], "stub_package": "stubs"}
    ).with_source(
        "src/ide_proxy/models.py", source_content
    ).build()

    # 3. Create a correctly configured, installable RUNTIME package using hatchling.
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

    # 4. Generate the stub package.
    app = StitcherApp(root_path=source_project_root)
    app.run_from_config()
    stub_pkg_path = source_project_root / "stubs"

    # 5. Install BOTH packages.
    isolated_env.install(str(runtime_project_root))
    isolated_env.install(str(stub_pkg_path))

    # 6. Run DIAGNOSTICS before the main check.
    pip_list_output = isolated_env.pip_list()
    site_packages_layout = isolated_env.get_site_packages_layout()
    import_result = isolated_env.run_python_command("import ide_proxy.models")

    # 7. Create a client script to be type-checked.
    client_script = tmp_path / "client.py"
    client_script.write_text(
        "from ide_proxy.models import ProxyModel\n\n"
        "instance = ProxyModel()\n"
        "reveal_type(instance.get_id())\n"
    )

    # 8. Run the final Pyright check.
    result = isolated_env.run_pyright_check(client_script)

    # --- ASSERT ---

    # 9. Assert with a rich diagnostic message.
    diagnostic_info = f"""
    --- DIAGNOSTICS ---
    [PIP LIST]
{pip_list_output}
    [SITE-PACKAGES LAYOUT]
{site_packages_layout}
    [PYTHON IMPORT TEST]
    Exit Code: {import_result.returncode}
    Stdout: {import_result.stdout.strip()}
    Stderr: {import_result.stderr.strip()}
    ---
    [PYRIGHT OUTPUT]
    STDOUT:
{result.stdout}
    STDERR:
{result.stderr}
    """

    assert (
        import_result.returncode == 0
    ), f"Python could not import the runtime module.\n{diagnostic_info}"
    assert (
        result.returncode == 0
    ), f"Pyright failed with errors.\n{diagnostic_info}"

    assert "0 errors" in result.stdout, f"Pyright reported errors.\n{diagnostic_info}"
    assert (
        'Type of "instance.get_id()" is "int"' in result.stdout
    ), f"Pyright did not resolve the return type correctly.\n{diagnostic_info}"