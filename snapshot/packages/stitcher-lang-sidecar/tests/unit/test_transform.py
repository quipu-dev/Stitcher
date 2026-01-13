import pytest
from pathlib import Path
from stitcher.lang.sidecar import SidecarTransformer, SidecarTransformContext


@pytest.fixture
def transformer():
    return SidecarTransformer()


class TestJsonSuriUpdates:
    def test_updates_suri_on_symbol_rename(self, transformer):
        old_suri = "py://src/app.py#OldClass"
        new_suri = "py://src/app.py#NewClass"
        data = {old_suri: {"hash": "1"}}
        context = SidecarTransformContext(
            old_module_fqn="app",
            new_module_fqn="app",
            old_fqn="app.OldClass",
            new_fqn="app.NewClass",
            old_file_path="src/app.py",
            new_file_path="src/app.py",
        )
        updated = transformer.transform(Path("src/app.json"), data, context)
        assert updated == {new_suri: {"hash": "1"}}

    def test_updates_suri_on_nested_symbol_rename(self, transformer):
        old_suri = "py://src/app.py#MyClass.old_method"
        new_suri = "py://src/app.py#MyClass.new_method"
        data = {old_suri: {"hash": "1"}}
        context = SidecarTransformContext(
            old_module_fqn="app",
            new_module_fqn="app",
            old_fqn="app.MyClass.old_method",
            new_fqn="app.MyClass.new_method",
            old_file_path="src/app.py",
            new_file_path="src/app.py",
        )
        updated = transformer.transform(Path("src/app.json"), data, context)
        assert updated == {new_suri: {"hash": "1"}}

    def test_updates_suri_on_parent_rename(self, transformer):
        old_suri = "py://src/app.py#OldClass.method"
        new_suri = "py://src/app.py#NewClass.method"
        data = {old_suri: {"hash": "1"}}
        context = SidecarTransformContext(
            old_module_fqn="app",
            new_module_fqn="app",
            old_fqn="app.OldClass",
            new_fqn="app.NewClass",
            old_file_path="src/app.py",
            new_file_path="src/app.py",
        )
        updated = transformer.transform(Path("src/app.json"), data, context)
        assert updated == {new_suri: {"hash": "1"}}

    def test_updates_suri_on_file_move(self, transformer):
        old_suri = "py://src/old_path/app.py#MyClass"
        new_suri = "py://src/new_path/app.py#MyClass"
        data = {old_suri: {"hash": "1"}}
        context = SidecarTransformContext(
            old_module_fqn="old_path.app",
            new_module_fqn="new_path.app",
            old_fqn="old_path.app.MyClass",
            new_fqn="new_path.app.MyClass",
            old_file_path="src/old_path/app.py",
            new_file_path="src/new_path/app.py",
        )
        updated = transformer.transform(Path("src/old_path/app.json"), data, context)
        assert updated == {new_suri: {"hash": "1"}}

    def test_updates_suri_on_combined_move_and_rename(self, transformer):
        old_suri = "py://src/old_path/app.py#OldClass"
        new_suri = "py://src/new_path/app.py#NewClass"
        data = {old_suri: {"hash": "1"}}
        context = SidecarTransformContext(
            old_module_fqn="old_path.app",
            new_module_fqn="new_path.app",
            old_fqn="old_path.app.OldClass",
            new_fqn="new_path.app.NewClass",
            old_file_path="src/old_path/app.py",
            new_file_path="src/new_path/app.py",
        )
        updated = transformer.transform(Path("src/old_path/app.json"), data, context)
        assert updated == {new_suri: {"hash": "1"}}


class TestYamlFragmentUpdates:
    def test_updates_fragment_on_symbol_rename(self, transformer):
        data = {"OldClass": "doc", "Other": "doc"}
        context = SidecarTransformContext(
            old_module_fqn="app",
            new_module_fqn="app",
            old_fqn="app.OldClass",
            new_fqn="app.NewClass",
        )
        updated = transformer.transform(Path("app.stitcher.yaml"), data, context)
        assert updated == {"NewClass": "doc", "Other": "doc"}

    def test_updates_fragment_on_nested_symbol_rename(self, transformer):
        data = {"MyClass.old_method": "doc"}
        context = SidecarTransformContext(
            old_module_fqn="app",
            new_module_fqn="app",
            old_fqn="app.MyClass.old_method",
            new_fqn="app.MyClass.new_method",
        )
        updated = transformer.transform(Path("app.stitcher.yaml"), data, context)
        assert updated == {"MyClass.new_method": "doc"}

    def test_updates_fragment_on_parent_rename(self, transformer):
        data = {"OldClass.method": "doc"}
        context = SidecarTransformContext(
            old_module_fqn="app",
            new_module_fqn="app",
            old_fqn="app.OldClass",
            new_fqn="app.NewClass",
        )
        updated = transformer.transform(Path("app.stitcher.yaml"), data, context)
        assert updated == {"NewClass.method": "doc"}

    def test_does_not_update_fragment_on_pure_file_move(self, transformer):
        data = {"MyClass": "doc"}
        original_data = data.copy()
        context = SidecarTransformContext(
            old_module_fqn="old_path.app",
            new_module_fqn="new_path.app",
            old_fqn="old_path.app.MyClass",
            new_fqn="new_path.app.MyClass",
            old_file_path="old_path/app.py",
            new_file_path="new_path/app.py",
        )
        updated = transformer.transform(
            Path("old_path/app.stitcher.yaml"), data, context
        )
        assert updated == original_data
