from pathlib import Path
import tomli_w

from stitcher.common.transaction import TransactionManager


class StubPackageManager:
    @staticmethod
    def _get_pep561_logical_path(logical_path: Path) -> Path:
        if not logical_path.parts:
            return logical_path

        namespace = logical_path.parts[0]
        rest_of_path = logical_path.parts[1:]
        # e.g. my_app/main.py -> my_app-stubs/main.py
        return Path(f"{namespace}-stubs", *rest_of_path)

    def scaffold(
        self,
        package_path: Path,
        source_project_name: str,
        package_namespace: str,
        tm: TransactionManager,
        root_path: Path,
    ) -> bool:
        config_path = package_path / "pyproject.toml"
        if config_path.exists():
            return False

        # Note: Directory creation is now handled implicitly by add_write.
        stub_src_dirname = self._get_pep561_logical_path(
            Path(package_namespace)
        ).as_posix()

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
        # Convert dict to TOML string
        toml_bytes = tomli_w.dumps(pyproject_content).encode("utf-8")

        # Add operation to transaction manager
        relative_config_path = config_path.relative_to(root_path)
        tm.add_write(str(relative_config_path), toml_bytes.decode("utf-8"))

        return True
