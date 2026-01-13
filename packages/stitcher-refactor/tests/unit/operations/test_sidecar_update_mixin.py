import pytest
from pathlib import Path
from stitcher.refactor.operations.base import SidecarUpdateMixin


@pytest.fixture
def mixin():
    return SidecarUpdateMixin()


class TestJsonSuriUpdates:
    def test_updates_suri_on_symbol_rename(self, mixin):
        old_suri = "py://src/app.py#OldClass"
        new_suri = "py://src/app.py#NewClass"
        data = {old_suri: {"hash": "1"}}
        updated = mixin._update_sidecar_data(
            data,
            Path("src/app.json"),
            old_module_fqn="app",
            new_module_fqn="app",
            old_fqn="app.OldClass",
            new_fqn="app.NewClass",
        )
        assert updated == {new_suri: {"hash": "1"}}

    def test_updates_suri_on_nested_symbol_rename(self, mixin):
        old_suri = "py://src/app.py#MyClass.old_method"
        new_suri = "py://src/app.py#MyClass.new_method"
        data = {old_suri: {"hash": "1"}}
        updated = mixin._update_sidecar_data(
            data,
            Path("src/app.json"),
            old_module_fqn="app",
            new_module_fqn="app",
            old_fqn="app.MyClass.old_method",
            new_fqn="app.MyClass.new_method",
        )
        assert updated == {new_suri: {"hash": "1"}}

    def test_updates_suri_on_parent_rename(self, mixin):
        old_suri = "py://src/app.py#OldClass.method"
        new_suri = "py://src/app.py#NewClass.method"
        data = {old_suri: {"hash": "1"}}
        updated = mixin._update_sidecar_data(
            data,
            Path("src/app.json"),
            old_module_fqn="app",
            new_module_fqn="app",
            old_fqn="app.OldClass",
            new_fqn="app.NewClass",
        )
        assert updated == {new_suri: {"hash": "1"}}

    def test_updates_suri_on_file_move(self, mixin):
        old_suri = "py://src/old_path/app.py#MyClass"
        new_suri = "py://src/new_path/app.py#MyClass"
        data = {old_suri: {"hash": "1"}}
        updated = mixin._update_sidecar_data(
            data,
            Path("src/old_path/app.json"),
            old_module_fqn="old_path.app",
            new_module_fqn="new_path.app",
            old_fqn="old_path.app.MyClass",
            new_fqn="new_path.app.MyClass",
            old_file_path="src/old_path/app.py",
            new_file_path="src/new_path/app.py",
        )
        assert updated == {new_suri: {"hash": "1"}}

    def test_updates_suri_on_combined_move_and_rename(self, mixin):
        old_suri = "py://src/old_path/app.py#OldClass"
        new_suri = "py://src/new_path/app.py#NewClass"
        data = {old_suri: {"hash": "1"}}
        updated = mixin._update_sidecar_data(
            data,
            Path("src/old_path/app.json"),
            old_module_fqn="old_path.app",
            new_module_fqn="new_path.app",
            old_fqn="old_path.app.OldClass",
            new_fqn="new_path.app.NewClass",
            old_file_path="src/old_path/app.py",
            new_file_path="src/new_path/app.py",
        )
        assert updated == {new_suri: {"hash": "1"}}


class TestYamlFragmentUpdates:
    def test_updates_fragment_on_symbol_rename(self, mixin):
        data = {"OldClass": "doc", "Other": "doc"}
        updated = mixin._update_sidecar_data(
            data,
            Path("app.stitcher.yaml"),
            old_module_fqn="app",
            new_module_fqn="app",
            old_fqn="app.OldClass",
            new_fqn="app.NewClass",
        )
        assert updated == {"NewClass": "doc", "Other": "doc"}

    def test_updates_fragment_on_nested_symbol_rename(self, mixin):
        data = {"MyClass.old_method": "doc"}
        updated = mixin._update_sidecar_data(
            data,
            Path("app.stitcher.yaml"),
            old_module_fqn="app",
            new_module_fqn="app",
            old_fqn="app.MyClass.old_method",
            new_fqn="app.MyClass.new_method",
        )
        assert updated == {"MyClass.new_method": "doc"}

    def test_updates_fragment_on_parent_rename(self, mixin):
        data = {"OldClass.method": "doc"}
        updated = mixin._update_sidecar_data(
            data,
            Path("app.stitcher.yaml"),
            old_module_fqn="app",
            new_module_fqn="app",
            old_fqn="app.OldClass",
            new_fqn="app.NewClass",
        )
        assert updated == {"NewClass.method": "doc"}

    def test_does_not_update_fragment_on_pure_file_move(self, mixin):
        data = {"MyClass": "doc"}
        original_data = data.copy()
        updated = mixin._update_sidecar_data(
            data,
            Path("old_path/app.stitcher.yaml"),
            old_module_fqn="old_path.app",
            new_module_fqn="new_path.app",
            old_fqn="old_path.app.MyClass",
            new_fqn="new_path.app.MyClass",  # Symbol name 'MyClass' is unchanged
            old_file_path="old_path/app.py",
            new_file_path="new_path/app.py",
        )
        # The key is relative to the file, so a move should NOT change it.
        assert updated == original_data
