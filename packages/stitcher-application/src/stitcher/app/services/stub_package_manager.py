from pathlib import Path
import tomli_w


class StubPackageManager:
    @staticmethod
    def _get_pep561_logical_path(logical_path: Path) -> Path:
        """Converts a standard logical path to a PEP 561-compliant one for stubs."""
        if not logical_path.parts:
            return logical_path

        namespace = logical_path.parts[0]
        rest_of_path = logical_path.parts[1:]
        # e.g. my_app/main.py -> my_app-stubs/main.py
        return Path(f"{namespace}-stubs", *rest_of_path)

    def scaffold(
        self, package_path: Path, source_project_name: str, package_namespace: str
    ) -> bool:
        config_path = package_path / "pyproject.toml"
        if config_path.exists():
            return False

        # Ensure root directory exists
        package_path.mkdir(parents=True, exist_ok=True)

        # Use the centralized logic to determine the stub source directory name
        stub_src_dirname = self._get_pep561_logical_path(
            Path(package_namespace)
        ).as_posix()
        (package_path / "src" / stub_src_dirname).mkdir(parents=True, exist_ok=True)

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
            "tool": {
                "hatch": {
                    "build": {
                        "targets": {
                            "wheel": {
                                # Essential for packaging .pyi files correctly under the namespace
                                "packages": [f"src/{stub_src_dirname}"]
                            }
                        }
                    }
                }
            },
        }
        with config_path.open("wb") as f:
            tomli_w.dump(pyproject_content, f)

        return True
