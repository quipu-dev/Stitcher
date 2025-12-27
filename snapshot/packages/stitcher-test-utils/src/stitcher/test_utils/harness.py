import subprocess
import venv
from pathlib import Path
from typing import List
import sys


class VenvHarness:
    """A test utility for creating and managing isolated virtual environments."""

    def __init__(self, root: Path):
        """
        Initializes the harness.

        Args:
            root: The temporary directory where the venv will be created.
        """
        self.root = root
        self.venv_dir = self.root / ".venv"
        self._python_exe: Path | None = None
        self.create()

    @property
    def python_exe(self) -> Path:
        """Returns the path to the Python executable in the virtual environment."""
        if self._python_exe is None:
            # Determine executable path based on OS
            bin_dir = "Scripts" if sys.platform == "win32" else "bin"
            self._python_exe = self.venv_dir / bin_dir / "python"
        return self._python_exe

    def create(self) -> None:
        """Creates a clean virtual environment."""
        venv.create(self.venv_dir, with_pip=True, clear=True)

    def install(self, *packages: str) -> subprocess.CompletedProcess:
        """
        Installs packages into the virtual environment using pip.

        Args:
            *packages: A list of packages to install (can be paths or names).

        Returns:
            The result of the subprocess call.
        """
        try:
            return subprocess.run(
                [str(self.python_exe), "-m", "pip", "install", *packages],
                check=True,
                capture_output=True,
                text=True,
            )
        except subprocess.CalledProcessError as e:
            # Print output to ensure it's captured by pytest even if exception msg is truncated
            print(f"--- PIP INSTALL FAILED ---\nCMD: {e.args}\n")
            print(f"STDOUT:\n{e.stdout}\n")
            print(f"STDERR:\n{e.stderr}\n")
            print("--------------------------")
            raise

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
