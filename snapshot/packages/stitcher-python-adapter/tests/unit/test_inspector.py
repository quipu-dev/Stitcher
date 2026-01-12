import pytest
from stitcher.lang.python.inspector import parse_plugin_entry, InspectionError

# Mock module for testing
import sys


class MockModule:
    pass


def setup_mock_module(monkeypatch):
    mock_mod = MockModule()

    def valid_func(a: int) -> str:
        """My Docstring"""
        return str(a)

    async def async_func():
        pass

    mock_mod.valid_func = valid_func  # type: ignore
    mock_mod.async_func = async_func  # type: ignore
    mock_mod.not_callable = "I am a string"  # type: ignore

    monkeypatch.setitem(sys.modules, "my_plugin", mock_mod)


class TestInspector:
    def test_parse_valid_entry(self, monkeypatch):
        setup_mock_module(monkeypatch)
        func_def = parse_plugin_entry("my_plugin:valid_func")

        assert func_def.name == "valid_func"
        assert func_def.docstring == "My Docstring"
        assert func_def.return_annotation == "str"
        assert len(func_def.args) == 1
        assert func_def.args[0].name == "a"
        assert func_def.args[0].annotation == "int"

    def test_parse_async_entry(self, monkeypatch):
        setup_mock_module(monkeypatch)
        func_def = parse_plugin_entry("my_plugin:async_func")
        assert func_def.is_async

    def test_module_not_found(self):
        with pytest.raises(InspectionError, match="Could not load entry point"):
            parse_plugin_entry("non_existent_module:func")

    def test_attribute_not_found(self, monkeypatch):
        setup_mock_module(monkeypatch)
        with pytest.raises(InspectionError, match="Could not load entry point"):
            parse_plugin_entry("my_plugin:non_existent_func")

    def test_target_not_callable(self, monkeypatch):
        setup_mock_module(monkeypatch)
        # inspect.signature raises TypeError if not callable
        with pytest.raises(InspectionError, match="Could not inspect signature"):
            parse_plugin_entry("my_plugin:not_callable")
