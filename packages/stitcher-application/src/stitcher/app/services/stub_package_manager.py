from pathlib import Path
import tomli_w


class StubPackageManager:
    """Manages the scaffolding of a PEP 561 stub package."""

    def scaffold(self, package_path: Path, source_project_name: str) -> bool:
        """
        Creates the directory structure and pyproject.toml for a stub package.

        Returns:
            bool: True if the package was created, False if it already existed.
        """
        config_path = package_path / "pyproject.toml"
        if config_path.exists():
            return False

        # Ensure root directory exists
        package_path.mkdir(parents=True, exist_ok=True)
        (package_path / "src").mkdir(exist_ok=True)

        # Create pyproject.toml
        pyproject_content = {
            "build-system": {
                "requires": ["hatchling"],
                "build-backend": "hatchling.build",
            },
            "project": {
                "name": f"{source_project_name}-stubs",
                "version": "0.1.0",  # Placeholder version
                "description": f"PEP 561 type stubs for {source_project_name}",
            },
        }
        with config_path.open("wb") as f:
            tomli_w.dump(pyproject_content, f)

        return True
