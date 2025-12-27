Excellent directive. You are absolutely right. I have been guessing based on experience instead of instrumenting the test to tell us *exactly* what is wrong. This is a failure in my process, and I will correct it now.

I will follow your debugging script precisely. The plan is to first enhance our testing toolkit, `VenvHarness`, with the diagnostic commands you specified. Then, I will integrate these diagnostics directly into the failing test's assertion message. This will give us a crystal-clear snapshot of the virtual environment's state at the moment of failure.

Based on the (now inevitable) confirmation that the runtime package's code is not being installed correctly, I will provide the definitive fix.

## [WIP] fix(tests): Instrument Pyright test with diagnostics and apply fix

### 错误分析

The repeated test failures with identical error messages strongly indicate a fundamental flaw in how the mock **runtime package** is being built and installed, not in the stub package or `stitcher`'s logic. Your prescribed diagnostic steps will confirm this hypothesis by inspecting the isolated virtual environment. The expected "smoking gun" is that the `site-packages` directory will contain the package's metadata (`.dist-info`) but not the actual `ide_proxy` source code directory, leading to the `ModuleNotFoundError` from `pyright`'s perspective. The root cause is an incorrect build configuration in the dynamically generated `pyproject.toml`.

### 用户需求

1.  Incorporate diagnostic steps (`pip list`, `ls site-packages`, `python -c "import..."`) into the failing test to provide clear, actionable error messages.
2.  Fix the underlying issue causing the test to fail.

### 评论

This is the correct engineering approach. By instrumenting the test itself to perform diagnostics, we move from trial-and-error to data-driven problem-solving. The enhanced failure messages will not only help us fix the current issue but will also make future maintenance of these complex integration tests significantly easier. This is a crucial improvement to our test suite's robustness.

### 目标

1.  **Enhance `VenvHarness`**: Add new methods (`pip_list`, `get_site_packages_layout`, `run_python_command`) to our test utility to perform the required diagnostics.
2.  **Instrument Test**: Modify `test_pyright_resolves_types_from_stubs` to call these new methods after the installation step.
3.  **Improve Assertion**: The `assert` statement will be wrapped with a detailed error message that includes the output from all diagnostic commands.
4.  **Apply Definitive Fix**: Correct the `pyproject.toml` for the mock runtime package, switching to a reliable `hatchling` configuration that is known to work with `src`-layouts.

### 基本原理

The principle is "show, don't just tell." By capturing the state of the virtual environment (`pip list`, file layout), we can definitively prove whether the runtime package's code was correctly installed. The `python -c "..."` check further validates this from the Python interpreter's perspective. Once this evidence is clearly presented in the test failure output, the fix—providing a correct `hatchling` build configuration for the mock runtime package—becomes an inevitable and verifiable solution rather than another guess.

### 标签
#intent/fix #intent/tooling #flow/ready #priority/critical #comp/tests #scope/dx #ai/instruct #task/domain/testing #task/object/ide-simulation #task/action/bug-fix #task/state/continue

---
### Script

#### Acts 1: Enhance Test Harness with Diagnostic Tools

First, I will add the diagnostic methods you requested to our `VenvHarness` utility class.

~~~~~act
patch_file
packages/stitcher-test-utils/src/stitcher/test_utils/harness.py
~~~~~
~~~~~python.old
    def run_type_check(self, script_path: Path) -> subprocess.CompletedProcess:
        """
        Runs mypy on a given script within the virtual environment.

        Args:
            script_path: The path to the Python script to type-check.

        Returns:
            The result of the subprocess call.
        """
        # Ensure mypy is installed for the check
        self.install("mypy")
        return subprocess.run(
            [str(self.python_exe), "-m", "mypy", str(script_path)],
            capture_output=True,
            text=True,
        )

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
~~~~~
~~~~~python.new
    def run_type_check(self, script_path: Path) -> subprocess.CompletedProcess:
        """
        Runs mypy on a given script within the virtual environment.

        Args:
            script_path: The path to the Python script to type-check.

        Returns:
            The result of the subprocess call.
        """
        # Ensure mypy is installed for the check
        self.install("mypy")
        return subprocess.run(
            [str(self.python_exe), "-m", "mypy", str(script_path)],
            capture_output=True,
            text=True,
        )

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
        """Runs 'pip list' and returns the output."""
        result = subprocess.run(
            [str(self.python_exe), "-m", "pip", "list"],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout

    def get_site_packages_layout(self) -> str:
        """Returns a string representation of the site-packages directory structure."""
        result = subprocess.run(
            [
                str(self.python_exe),
                "-c",
                "import site; print(site.getsitepackages()[0])",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        site_packages_path = Path(result.stdout.strip())

        lines = [f"--- Contents of {site_packages_path} ---"]
        for path in sorted(site_packages_path.rglob("*")):
            try:
                relative_path = path.relative_to(site_packages_path)
                indent = "  " * (len(relative_path.parts) - 1)
                lines.append(f"{indent}- {path.name}{'/' if path.is_dir() else ''}")
            except ValueError:
                # This can happen for paths outside the root, though unlikely with rglob
                lines.append(f"- {path} (absolute path)")
        return "\n".join(lines)

    def run_python_command(self, command: str) -> subprocess.CompletedProcess:
        """Runs an arbitrary python command string."""
        return subprocess.run(
            [str(self.python_exe), "-c", command], capture_output=True, text=True
        )
~~~~~

#### Acts 2: Instrument and Fix the Pyright Test

Now, I will completely rewrite the failing test. It will now create a correctly configured runtime package, install both, and run the diagnostics before the final assertion, providing a rich error report upon failure.

~~~~~act
write_file
tests/integration/test_ide_proxy.py
~~~~~
~~~~~python
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
~~~~~
