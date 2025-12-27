from pathlib import Path
from stitcher.app import StitcherApp
from stitcher.test_utils import WorkspaceFactory, VenvHarness


def test_pyright_resolves_types_from_stubs(
    tmp_path: Path, isolated_env: VenvHarness
):
    """
    Verifies that Pyright (the engine for VSCode's Pylance) can successfully
    resolve types from a generated stub package, simulating the IDE experience.
    This test ensures a realistic environment by installing BOTH the runtime
    package and the stub package.
    """
    # --- ARRANGE ---

    # 1. Define the shared source code content.
    source_content = """
class ProxyModel:
    def get_id(self): # No type hints in runtime code
        return 1
"""
    # 2. Create the source project that Stitcher will scan.
    source_project_root = tmp_path / "source_project"
    factory_source = WorkspaceFactory(source_project_root)
    factory_source.with_project_name("ide-proxy-proj").with_config(
        {"scan_paths": ["src/ide_proxy"], "stub_package": "stubs"}
    ).with_source("src/ide_proxy/models.py", source_content).build()

    # 3. Create a basic, installable RUNTIME package.
    runtime_project_root = tmp_path / "runtime_project"
    factory_runtime = WorkspaceFactory(runtime_project_root)
    factory_runtime.with_source("src/ide_proxy/models.py", source_content).with_source(
        # pkgutil-style namespace is robust
        "src/ide_proxy/__init__.py",
        "__path__ = __import__('pkgutil').extend_path(__path__, __name__)",
    ).with_source(
        # Minimal pyproject.toml to make it installable
        "pyproject.toml",
        """
[build-system]
requires = ["setuptools>=61.0"]
build-backend = "setuptools.build_meta"

[project]
name = "ide-proxy-proj"
version = "0.1.0"

[tool.setuptools]
package-dir = {"" = "src"}

[tool.setuptools.packages.find]
where = ["src"]
""",
    ).build()

    # --- ACT ---

    # 4. Generate the stub package from the source project.
    app = StitcherApp(root_path=source_project_root)
    app.run_from_config()
    stub_pkg_path = source_project_root / "stubs"
    assert (
        stub_pkg_path / "src/ide_proxy-stubs/models.pyi"
    ).exists(), "Stub .pyi file was not generated."

    # 5. Install BOTH packages into the isolated venv.
    isolated_env.install(str(runtime_project_root))
    isolated_env.install(str(stub_pkg_path))

    # 6. Create a client script that consumes the code.
    client_script = tmp_path / "client.py"
    client_script.write_text(
        """
from ide_proxy.models import ProxyModel

# If stubs are working, pyright will know ProxyModel and its methods.
instance = ProxyModel()
reveal_type(instance.get_id())
"""
    )

    # 7. Run pyright inside the isolated environment.
    result = isolated_env.run_pyright_check(client_script)

    # --- ASSERT ---

    # 8. Assert that pyright completes successfully.
    assert (
        result.returncode == 0
    ), f"Pyright failed with errors:\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"

    # 9. Verify Pyright's output confirms successful type analysis.
    assert (
        "0 errors" in result.stdout
    ), f"Pyright reported errors:\n{result.stdout}"
    assert (
        'Type of "instance.get_id()" is "int"' in result.stdout
    ), f"Pyright did not resolve the return type correctly.\nOutput:\n{result.stdout}"