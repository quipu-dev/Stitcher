import pytest
from stitcher.refactor.operations.base import SidecarUpdateMixin


@pytest.fixture
def mixin():
    return SidecarUpdateMixin()


class TestSidecarUpdateMixin:
    def test_update_exact_fqn_key(self, mixin):
        data = {"mypkg.core.OldClass": "doc"}
        updated = mixin._update_sidecar_data(
            data, None, "mypkg.core.OldClass", "mypkg.core.NewClass"
        )
        assert updated == {"mypkg.core.NewClass": "doc"}

    def test_update_cascading_fqn_key(self, mixin):
        data = {"mypkg.core.OldClass.method": "doc"}
        updated = mixin._update_sidecar_data(
            data, None, "mypkg.core.OldClass", "mypkg.core.NewClass"
        )
        assert updated == {"mypkg.core.NewClass.method": "doc"}

    def test_update_short_name_key_with_module_context(self, mixin):
        data = {"OldClass": "doc", "OldClass.method": "doc"}
        updated = mixin._update_sidecar_data(
            data, "mypkg.core", "mypkg.core.OldClass", "mypkg.core.NewClass"
        )
        assert updated == {"NewClass": "doc", "NewClass.method": "doc"}

    def test_update_short_name_to_fqn_on_module_move(self, mixin):
        data = {"OldClass": "doc"}
        updated = mixin._update_sidecar_data(
            data, "mypkg.core", "mypkg.core.OldClass", "mypkg.utils.NewClass"
        )
        # Key must become FQN because it's no longer in the same module
        assert updated == {"mypkg.utils.NewClass": "doc"}

    def test_no_change_for_unrelated_keys(self, mixin):
        data = {"other.Class": "doc", "mypkg.core.AnotherClass": "doc"}
        original_data = data.copy()
        updated = mixin._update_sidecar_data(
            data, "mypkg.core", "mypkg.core.OldClass", "mypkg.core.NewClass"
        )
        assert updated == original_data

    def test_no_change_for_short_name_without_module_context(self, mixin):
        data = {"OldClass": "doc"}
        original_data = data.copy()
        updated = mixin._update_sidecar_data(
            data, None, "mypkg.core.OldClass", "mypkg.core.NewClass"
        )
        assert updated == original_data

    def test_update_module_rename(self, mixin):
        data = {
            "mypkg.old_mod.MyClass": "doc",
            "mypkg.old_mod.MyClass.method": "doc",
            "mypkg.other_mod.MyClass": "doc",  # Should not change
        }
        updated = mixin._update_sidecar_data(
            data, "mypkg.old_mod", "mypkg.old_mod", "mypkg.new_mod"
        )
        assert updated == {
            "mypkg.new_mod.MyClass": "doc",
            "mypkg.new_mod.MyClass.method": "doc",
            "mypkg.other_mod.MyClass": "doc",
        }

    def test_update_short_name_when_module_is_renamed(self, mixin):
        data = {"MyClass": "doc", "MyClass.method": "doc"}
        updated = mixin._update_sidecar_data(
            data, "mypkg.old_mod", "mypkg.old_mod", "mypkg.new_mod"
        )
        # When renaming the module itself, short names remain short names
        assert updated == {"MyClass": "doc", "MyClass.method": "doc"}
