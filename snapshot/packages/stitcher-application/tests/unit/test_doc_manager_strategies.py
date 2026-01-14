import pytest
from stitcher.lang.python.uri import PythonURIGenerator
from stitcher.lang.sidecar import DocumentManager
from stitcher.spec import (
    DocstringIR,
    DocstringItem,
    DocstringSection,
    SectionKind,
)
from stitcher.lang.python.docstring import get_docstring_codec, get_docstring_serializer


@pytest.fixture(scope="module")
def sample_ir() -> DocstringIR:
    """A standard DocstringIR object for testing serialization."""
    return DocstringIR(
        summary="This is a summary.",
        extended="This is an extended description.",
        sections=[
            DocstringSection(
                kind=SectionKind.PARAMETERS,
                content=[
                    DocstringItem(name="param1", description="Description for param1."),
                    DocstringItem(name="param2", description="Description for param2."),
                ],
            )
        ],
        addons={"Addon.Test": {"key": "value"}},
    )


class TestDocumentManagerStrategies:
    @pytest.fixture(scope="class")
    def doc_manager(self, tmp_path_factory) -> DocumentManager:
        """A DocumentManager instance for the test class."""
        # tmp_path is not strictly needed here but good practice for services
        root = tmp_path_factory.mktemp("doc-manager-strat-tests")
        return DocumentManager(root, uri_generator=PythonURIGenerator())

    @pytest.mark.parametrize(
        "style, expected_params_key",
        [
            ("google", "Args"),
            ("numpy", "Parameters"),
        ],
    )
    def test_structured_serialization_roundtrip(
        self, doc_manager: DocumentManager, sample_ir, style, expected_params_key
    ):
        """Verify serialization and deserialization for Google and NumPy styles."""
        # 1. Set strategy
        parser, _ = get_docstring_codec(style)
        serializer = get_docstring_serializer(style)
        doc_manager.set_strategy(parser, serializer)

        # 2. Serialize (internal method call for direct testing)
        serialized_data = doc_manager._serialize_ir(sample_ir)

        # 3. Assert serialized format
        assert isinstance(serialized_data, dict)
        assert serialized_data["Summary"] == "This is a summary."
        assert serialized_data["Extended"] == "This is an extended description."
        assert expected_params_key in serialized_data
        assert "Addon.Test" in serialized_data
        params = serialized_data[expected_params_key]
        assert isinstance(params, dict)
        assert params["param1"] == "Description for param1."
        assert params["param2"] == "Description for param2."

        # 4. Deserialize
        deserialized_ir = doc_manager._deserialize_ir(serialized_data)

        # 5. Assert roundtrip equality (main fields)
        assert deserialized_ir.summary == sample_ir.summary
        assert deserialized_ir.extended == sample_ir.extended
        assert deserialized_ir.addons == sample_ir.addons

        param_section = next(
            s for s in deserialized_ir.sections if s.kind == SectionKind.PARAMETERS
        )
        assert isinstance(param_section.content, list)
        assert len(param_section.content) == 2
        # Note: Order is not guaranteed in dicts, so we check names
        param_names = {item.name for item in param_section.content}
        assert param_names == {"param1", "param2"}

    def test_raw_serialization_roundtrip(self, doc_manager: DocumentManager, sample_ir):
        """Verify serialization for Raw style (which only keeps summary and addons)."""
        # 1. Set strategy to raw
        parser, _ = get_docstring_codec("raw")
        serializer = get_docstring_serializer("raw")
        doc_manager.set_strategy(parser, serializer)

        # 2. Serialize
        serialized_data = doc_manager._serialize_ir(sample_ir)

        # 3. Assert serialized format (Hybrid Mode because of addons)
        assert isinstance(serialized_data, dict)
        assert serialized_data["Raw"] == "This is a summary."
        assert serialized_data["Addon.Test"] == {"key": "value"}
        # Extended and sections are intentionally lost in raw serialization
        assert "Extended" not in serialized_data
        assert "Parameters" not in serialized_data

        # 4. Deserialize
        deserialized_ir = doc_manager._deserialize_ir(serialized_data)

        # 5. Assert roundtrip equality
        assert deserialized_ir.summary == sample_ir.summary
        assert deserialized_ir.addons == sample_ir.addons
        assert not deserialized_ir.extended
        assert not deserialized_ir.sections

    def test_raw_serialization_simple_string(self, doc_manager: DocumentManager):
        """Verify raw serialization degrades to a simple string when no addons are present."""
        parser, _ = get_docstring_codec("raw")
        serializer = get_docstring_serializer("raw")
        doc_manager.set_strategy(parser, serializer)

        ir = DocstringIR(summary="Just a simple string.")
        serialized_data = doc_manager._serialize_ir(ir)

        assert isinstance(serialized_data, str)
        assert serialized_data == "Just a simple string."

        deserialized_ir = doc_manager._deserialize_ir(serialized_data)
        assert deserialized_ir.summary == "Just a simple string."
        assert not deserialized_ir.addons
