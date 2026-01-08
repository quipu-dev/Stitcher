import pytest
from stitcher.spec import DocstringIR, DocstringSection, DocstringItem
from stitcher.adapter.python.docstring.renderers import GoogleDocstringRenderer, NumpyDocstringRenderer


@pytest.fixture
def sample_ir():
    ir = DocstringIR(
        summary="Summary line.",
        extended="Extended description."
    )
    # Add Args
    ir.sections.append(DocstringSection(
        kind="parameters",
        title="Args",
        content=[
            DocstringItem(name="x", annotation="int", description="The x value."),
            DocstringItem(name="y", description="The y value.")
        ]
    ))
    # Add Returns
    ir.sections.append(DocstringSection(
        kind="returns",
        title="Returns",
        content=[
            DocstringItem(annotation="bool", description="True if success.")
        ]
    ))
    return ir


class TestGoogleDocstringRenderer:
    def test_render_google(self, sample_ir):
        renderer = GoogleDocstringRenderer()
        output = renderer.render(sample_ir)
        
        expected = """Summary line.

Extended description.

Args:
    x (int): The x value.
    y: The y value.

Returns:
    bool: True if success."""
        
        assert output.strip() == expected.strip()


class TestNumpyDocstringRenderer:
    def test_render_numpy(self, sample_ir):
        # Adjust titles for Numpy conventions
        sample_ir.sections[0].title = "Parameters" 
        sample_ir.sections[1].title = "Returns" 

        renderer = NumpyDocstringRenderer()
        output = renderer.render(sample_ir)
        
        expected = """Summary line.

Extended description.

Parameters
----------
x : int
    The x value.
y
    The y value.

Returns
-------
bool
    True if success."""
        
        assert output.strip() == expected.strip()