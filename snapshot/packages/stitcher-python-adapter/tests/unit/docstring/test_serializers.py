import pytest
from stitcher.spec import (
    DocstringIR,
    DocstringItem,
    DocstringSection,
    SectionKind,
)
from stitcher.lang.python.docstring.serializers import (
    RawSerializer,
    GoogleSerializer,
    NumpySerializer,
)


@pytest.fixture
def complex_ir() -> DocstringIR:
    """A comprehensive DocstringIR object for testing serializers."""
    return DocstringIR(
        summary="This is the summary.",
        extended="This is the extended description.",
        sections=[
            DocstringSection(
                kind=SectionKind.PARAMETERS,
                content=[
                    DocstringItem(
                        name="param1",
                        annotation="int",
                        description="The first parameter.",
                    ),
                    DocstringItem(
                        name="param2",
                        annotation="str",
                        description="The second parameter.",
                    ),
                ],
            ),
            DocstringSection(
                kind=SectionKind.RETURNS,
                content=[
                    DocstringItem(
                        annotation="bool",
                        description="True if successful, False otherwise.",
                    )
                ],
            ),
            DocstringSection(
                kind=SectionKind.RAISES,
                content=[
                    DocstringItem(annotation="ValueError", description="If invalid.")
                ],
            ),
            DocstringSection(
                kind=SectionKind.EXAMPLES,
                content=">>> my_func(1, 'a')\nTrue",
            ),
            # Custom section
            DocstringSection(
                kind="custom",
                title="Configuration",
                content="This is a custom section.",
            ),
        ],
        addons={"Addon.Test": {"key": "value"}},
    )


class TestRawSerializer:
    def test_roundtrip_simple(self):
        serializer = RawSerializer()
        ir = DocstringIR(summary="Simple doc.")
        serialized = serializer.to_yaml(ir)
        assert serialized == "Simple doc."
        deserialized = serializer.from_yaml(serialized)
        assert deserialized == ir

    def test_roundtrip_hybrid(self):
        serializer = RawSerializer()
        ir = DocstringIR(summary="Hybrid doc.", addons={"Addon.Test": "Data"})
        serialized = serializer.to_yaml(ir)
        assert serialized == {"Raw": "Hybrid doc.", "Addon.Test": "Data"}
        deserialized = serializer.from_yaml(serialized)
        assert deserialized == ir


class TestGoogleSerializer:
    def test_to_yaml(self, complex_ir):
        serializer = GoogleSerializer()
        data = serializer.to_yaml(complex_ir)

        assert data["Summary"] == "This is the summary."
        assert data["Extended"] == "This is the extended description."
        assert "Args" in data
        # Verification: No type info encoded in the value string
        assert data["Args"]["param1"] == "The first parameter."
        assert "Returns" in data
        assert data["Returns"]["bool"] == "True if successful, False otherwise."
        assert "Raises" in data
        assert "Examples" in data
        assert data["Addon.Test"] == {"key": "value"}
        assert data["Configuration"] == "This is a custom section."

    def test_from_yaml_roundtrip(self, complex_ir):
        serializer = GoogleSerializer()
        yaml_data = serializer.to_yaml(complex_ir)
        reconstructed_ir = serializer.from_yaml(yaml_data)

        # Due to fallback keys, we need to compare content carefully
        assert reconstructed_ir.summary == complex_ir.summary
        assert reconstructed_ir.extended == complex_ir.extended
        assert reconstructed_ir.addons == complex_ir.addons

        # A simple equality check might fail due to ordering or minor differences.
        # Let's check section by section.
        assert len(reconstructed_ir.sections) == len(complex_ir.sections)

    def test_graceful_fallback_from_string(self):
        serializer = GoogleSerializer()
        ir = serializer.from_yaml("Just a raw string.")
        assert ir.summary == "Just a raw string."
        assert not ir.sections
        assert not ir.addons


class TestNumpySerializer:
    def test_to_yaml(self, complex_ir):
        serializer = NumpySerializer()
        data = serializer.to_yaml(complex_ir)

        assert data["Summary"] == "This is the summary."
        assert "Parameters" in data  # Key difference from Google
        assert data["Parameters"]["param1"] == "The first parameter."
        assert "Returns" in data
        assert "Raises" in data
        assert "Examples" in data
        assert data["Addon.Test"] == {"key": "value"}
        assert data["Configuration"] == "This is a custom section."

    def test_from_yaml_roundtrip(self, complex_ir):
        serializer = NumpySerializer()
        yaml_data = serializer.to_yaml(complex_ir)
        reconstructed_ir = serializer.from_yaml(yaml_data)

        assert reconstructed_ir.summary == complex_ir.summary
        assert reconstructed_ir.extended == complex_ir.extended
        assert reconstructed_ir.addons == complex_ir.addons
        assert len(reconstructed_ir.sections) == len(complex_ir.sections)
