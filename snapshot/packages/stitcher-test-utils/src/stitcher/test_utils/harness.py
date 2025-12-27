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
        return subprocess.run(
            [str(self.python_exe), "-m", "pip", "install", *packages],
            check=True,
            capture_output=True,
            text=True,
        )

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
