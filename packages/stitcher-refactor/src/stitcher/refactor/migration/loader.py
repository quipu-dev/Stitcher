import importlib.util
from pathlib import Path

from .spec import MigrationSpec
from .exceptions import MigrationScriptError


class MigrationLoader:
    def load_from_path(self, path: Path) -> MigrationSpec:
        if not path.is_file():
            raise FileNotFoundError(f"Migration script not found at: {path}")

        # Create a unique module name to avoid polluting sys.modules with a common name
        module_name = f"stitcher.migrations.{path.stem}"

        try:
            spec = importlib.util.spec_from_file_location(module_name, path)
            if spec is None or spec.loader is None:
                raise MigrationScriptError(f"Could not create module spec for {path}")

            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
        except SyntaxError as e:
            raise MigrationScriptError(
                f"Syntax error in migration script {path}: {e}"
            ) from e
        except Exception as e:
            raise MigrationScriptError(
                f"Failed to load migration script {path}: {e}"
            ) from e

        if not hasattr(module, "upgrade"):
            raise MigrationScriptError(
                f"Migration script {path} is missing the 'upgrade' function."
            )

        upgrade_func = getattr(module, "upgrade")
        if not callable(upgrade_func):
            raise MigrationScriptError(
                f"The 'upgrade' attribute in {path} is not a callable function."
            )

        migration_spec = MigrationSpec()
        upgrade_func(migration_spec)

        return migration_spec
