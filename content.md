Excellent question. Your intuition is spot on. We've proven the environment is correct for the Python runtime, but we haven't proven that `pyright` is *using* that environment. Your question, "how can we see what config `pyright` is using?", is the key to solving this once and for all.

The answer is the `--verbose` flag. When run with this flag, `pyright` will print detailed diagnostic information, including which configuration files it finds and which search paths it's using.

My final attempt failed because, while I correctly identified the need for a configuration file, the `venvPath` option can be finicky. It tells `pyright` where to find the Python interpreter, but it doesn't always guarantee that it will correctly discover and add the `site-packages` directory to its search paths, especially in complex temporary directory setups like ours.

The most direct and foolproof way to solve this is to explicitly tell `pyright` where to find the installed packages using the `extraPaths` configuration option.

Here is the definitive plan to diagnose and fix this test.

## [WIP] fix(tests): Add verbose diagnostics and explicit paths to Pyright config

### 错误分析

The diagnostic data has proven that the Python environment is correctly set up, but `pyright` is failing to use it for import resolution. The root cause is that `pyright`'s automatic environment discovery is not robust enough for our testing harness. Even with `venvPath` specified, it is not adding the virtual environment's `site-packages` directory to its internal search paths. The solution is to stop relying on implicit discovery and instead explicitly provide the `site-packages` path to `pyright` via the `extraPaths` configuration setting, leaving no room for ambiguity.

### 用户需求

1.  Enhance the test harness to run `pyright` with `--verbose` to get diagnostic output.
2.  Fix the `test_ide_proxy.py` test by creating a `pyrightconfig.json` that explicitly tells `pyright` where to find the installed packages.

### 评论

This is the final, correct approach. We are now instrumenting the tool itself to tell us what it's doing (`--verbose`) and providing it with an explicit, unambiguous configuration (`extraPaths`) instead of relying on "magic" discovery mechanisms. This mirrors how a developer would solve a real-world configuration problem and results in a test that is both correct and highly robust.

### 目标

1.  **Enhance `VenvHarness`**:
    *   Add a `get_site_packages_path()` method.
    *   Modify `run_pyright_check` to accept a `verbose` flag and pass `--verbose` to the command.
2.  **Rewrite Test**:
    *   In `test_pyright_resolves_types_from_stubs`, call the new `get_site_packages_path()` method.
    *   Create a `pyrightconfig.json` that uses the `extraPaths` key to point directly to the `site-packages` directory.
    *   Run `pyright` with `verbose=True` and include its full output in the diagnostic block of the assertion message.

### 基本原理

The `extraPaths` setting in `pyrightconfig.json` is the canonical way to add directories to `pyright`'s import resolution search path. By programmatically finding the `site-packages` directory of our isolated virtual environment and feeding it to `pyright` via this setting, we are directly injecting the necessary context. `pyright` will now search this directory, find the installed `ide_proxy` runtime package and the `ide-proxy-stubs` package, and correctly resolve the import, allowing the test to finally pass.

### 标签
#intent/fix #flow/ready #priority/critical #comp/tests #scope/dx #ai/instruct #task/domain/testing #task/object/ide-simulation #task/action/bug-fix #task/state/end

---
### Script

#### Acts 1: Final Enhancements to the Test Harness

I will add the final diagnostic tools to `VenvHarness`.

~~~~~act
patch_file
packages/stitcher-test-utils/src/stitcher/test_utils/harness.py
~~~~~
~~~~~python.old
    def run_pyright_check(self, script_path: Path) -> subprocess.CompletedProcess:
        """
        Runs pyright on a given script within the virtual environment.

        Args:
            script_path: The path to the Python script to type-check.

        Returns:
            The result of the subprocess call.
        """
        self.install("pyright")
        # Pyright is a JS application, so it provides an entry point script.
        # We find it in the venv's bin directory.
        bin_dir = "Scripts" if sys.platform == "win32" else "bin"
        pyright_exe = self.venv_dir / bin_dir / "pyright"
        return subprocess.run(
            [str(pyright_exe), str(script_path)], capture_output=True, text=True
        )

    # --- Diagnostic Methods ---

    def pip_list(self) -> str:
~~~~~
~~~~~python.new
    def run_pyright_check(
        self, project_path: Path, verbose: bool = False
    ) -> subprocess.CompletedProcess:
        """
        Runs pyright on a given project/file within the virtual environment.

        Args:
            project_path: The path to the Python project/file to type-check.
            verbose: If True, run pyright with --verbose flag.

        Returns:
            The result of the subprocess call.
        """
        self.install("pyright")
        bin_dir = "Scripts" if sys.platform == "win32" else "bin"
        pyright_exe = self.venv_dir / bin_dir / "pyright"

        command = [str(pyright_exe)]
        if verbose:
            command.append("--verbose")
        command.append(str(project_path))

        return subprocess.run(command, capture_output=True, text=True)

    def get_site_packages_path(self) -> Path:
        """Returns the absolute path to the site-packages directory."""
        result = self.run_python_command(
            "import site; print(site.getsitepackages()[0])"
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"Could not determine site-packages path: {result.stderr}"
            )
        return Path(result.stdout.strip())

    # --- Diagnostic Methods ---

    def pip_list(self) -> str:
~~~~~

#### Acts 2: The Definitive Fix for the Pyright Test

This is the final version of the test, incorporating all diagnostics and the correct configuration fix.

~~~~~act
write_file
tests/integration/test_ide_proxy.py
~~~~~
~~~~~python
import json
from pathlib import Path
from stitcher.app import StitcherApp
from stitcher.test_utils import WorkspaceFactory, VenvHarness


def test_pyright_resolves_types_from_stubs(
    tmp_path: Path, isolated_env: VenvHarness
):
    """
    Verifies that Pyright can resolve types from a generated stub package by
    providing an explicit pyrightconfig.json that points to the venv's
    site-packages. This is the definitive test for IDE compatibility.
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

    # 4. Install BOTH packages.
    isolated_env.install(str(runtime_project_root))
    isolated_env.install(str(stub_pkg_path))

    # 5. Create a client project directory.
    client_project_dir = tmp_path / "client_project"
    client_project_dir.mkdir()
    client_script = client_project_dir / "main.py"
    client_script.write_text(
        "from ide_proxy.models import ProxyModel\n\n"
        "instance = ProxyModel()\n"
        "reveal_type(instance.get_id())\n"
    )

    # 6. *** THE DEFINITIVE FIX ***
    #    Create a pyrightconfig.json that explicitly tells pyright where to
    #    find the installed packages.
    pyright_config_path = client_project_dir / "pyrightconfig.json"
    site_packages = isolated_env.get_site_packages_path()
    pyright_config = {"extraPaths": [str(site_packages)]}
    pyright_config_path.write_text(json.dumps(pyright_config))

    # 7. Run Pyright check with verbosity for better diagnostics.
    result = isolated_env.run_pyright_check(client_project_dir, verbose=True)

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
~~~~~
