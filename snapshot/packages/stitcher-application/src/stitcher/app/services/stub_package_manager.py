from pathlib import Path
import tomli_w


class StubPackageManager:
    def scaffold(
        self, package_path: Path, source_project_name: str, package_namespace: str
    ) -> bool:
        config_path = package_path / "pyproject.toml"
        if config_path.exists():
            return False

        # Ensure root directory exists
        package_path.mkdir(parents=True, exist_ok=True)
        stub_namespace = f"{package_namespace}-stubs"
        # Create src/namespace-stubs directory, e.g., src/needle-stubs
        (package_path / "src" / stub_namespace).mkdir(parents=True, exist_ok=True)

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
                                "packages": [f"src/{stub_namespace}"]
                            }
                        }
                    }
                }
            },
        }
        with config_path.open("wb") as f:
            tomli_w.dump(pyproject_content, f)

        return True
