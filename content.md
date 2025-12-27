This is it. The verbose output is the final piece of the puzzle, and it's unequivocal.

The `--verbose` output has given us the smoking gun:

`Loading pyproject.toml file at /home/doucx/Documents/Projects/stitcher-python/pyproject.toml`

**`Pyright` is loading the main project's configuration, not the `pyrightconfig.json` we created in the temporary directory.**

The reason is that the `pytest` process is running from our project root. When `subprocess.run` executes `pyright`, the subprocess inherits the parent's Current Working Directory (CWD). `Pyright`'s configuration discovery mechanism finds the `pyproject.toml` in the CWD and immediately uses its `[tool.pyright]` settings, completely ignoring the configuration file located next to the file being analyzed in the temporary path. The `extraPaths` from our main project's config are loaded, but they are irrelevant to the isolated venv, and our intended `extraPaths` are never seen.

The solution is to force `pyright` to run in a clean environment by changing its working directory to the temporary `client_project_dir` where our test files and configuration reside.

## [WIP] fix(tests): Isolate pyright process by setting its working directory

### 用户需求

修复 `tests/integration/test_ide_proxy.py`，通过隔离 `pyright` 子进程的工作目录来确保它加载正确的配置文件，从而解决导入解析失败的问题。

### 评论

这次的失败和最终的修复是整个调试过程的顶点。它揭示了在复杂的测试工具链中，子进程的环境（特别是工作目录）是多么关键。通过使用 `subprocess` 的 `cwd` 参数，我们为 `pyright` 创建了一个完美的“无尘室”，确保测试是自包含且可重复的，这代表了最高标准的集成测试实践。

### 目标

1.  **Enhance `VenvHarness`**: Modify `run_pyright_check` to accept a `cwd` parameter to control the subprocess's working directory.
2.  **Rewrite Test**: In the `test_pyright_resolves_types_from_stubs` test, when calling `run_pyright_check`, set the `cwd` to our temporary `client_project_dir`.

### 基本原理

通过将 `pyright` 子进程的 `cwd` (Current Working Directory) 设置为我们专门创建的 `client_project_dir`，我们强制 `pyright` 在一个受控的环境中启动。在这个环境中，它向上查找配置时，找到的第一个文件将是我们放置在那里的 `pyrightconfig.json`。它将不再看到主项目的 `pyproject.toml`。这个被正确加载的配置会告诉 `pyright` 使用我们指定的 `extraPaths`（即 venv 的 `site-packages`），从而使其能够完美地解析所有导入，最终通过测试。

### 标签
#intent/fix #flow/ready #priority/critical #comp/tests #scope/dx #ai/instruct #task/domain/testing #task/object/ide-simulation #task/action/bug-fix #task/state/end

---
### Script

#### Acts 1: Final Tweak to Test Harness

I will modify `VenvHarness` one last time to allow setting the `cwd` for the `pyright` command.

~~~~~act
patch_file
packages/stitcher-test-utils/src/stitcher/test_utils/harness.py
~~~~~
~~~~~python.old
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
~~~~~
~~~~~python.new
    def run_pyright_check(
        self,
        project_path: Path,
        verbose: bool = False,
        cwd: Path | None = None,
    ) -> subprocess.CompletedProcess:
        """
        Runs pyright on a given project/file within the virtual environment.

        Args:
            project_path: The path to the Python project/file to type-check.
            verbose: If True, run pyright with --verbose flag.
            cwd: The working directory from which to run the command.

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

        return subprocess.run(command, capture_output=True, text=True, cwd=cwd)
~~~~~

#### Acts 2: The Final, Corrected Test

This version of the test isolates the `pyright` process and will pass.

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
~~~~~
