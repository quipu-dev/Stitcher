import pytest
from textwrap import dedent

from stitcher.lang.python.docstring.renderers import (
    GoogleDocstringRenderer,
    NumpyDocstringRenderer,
)
from stitcher.spec import (
    DocstringIR,
    DocstringSection,
    DocstringItem,
    FunctionDef,
    Argument,
    ArgumentKind,
    SectionKind,
)


@pytest.fixture
def sample_function_def() -> FunctionDef:
    """A sample FunctionDef to act as the rendering context."""
    return FunctionDef(
        name="sample_func",
        args=[
            Argument(
                name="param1",
                kind=ArgumentKind.POSITIONAL_OR_KEYWORD,
                annotation="int",
            ),
            Argument(
                name="param2",
                kind=ArgumentKind.POSITIONAL_OR_KEYWORD,
                annotation="str",
                default="'default'",
            ),
        ],
        return_annotation="bool",
    )


@pytest.fixture
def sample_docstring_ir() -> DocstringIR:
    """A sample DocstringIR with descriptions, to be merged with context."""
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
            ),
            DocstringSection(
                kind=SectionKind.RETURNS,
                content=[
                    DocstringItem(description="True if successful, False otherwise.")
                ],
            ),
        ],
    )


def test_google_renderer_merges_types(sample_function_def, sample_docstring_ir):
    renderer = GoogleDocstringRenderer()
    result = renderer.render(sample_docstring_ir, context=sample_function_def)

    expected = dedent(
        """
        This is a summary.

        This is an extended description.

        Args:
            param1 (int): Description for param1.
            param2 (str): Description for param2.

        Returns:
            bool: True if successful, False otherwise.
        """
    ).strip()
    assert result.strip() == expected


def test_numpy_renderer_merges_types(sample_function_def, sample_docstring_ir):
    renderer = NumpyDocstringRenderer()
    result = renderer.render(sample_docstring_ir, context=sample_function_def)

    assert "This is a summary." in result
    assert "Parameters" in result
    assert "param1 : int" in result
    assert "Description for param1." in result

    # A more flexible check for returns section
    assert "Returns" in result
    assert "-------" in result
    assert "bool" in result
    assert "True if successful, False otherwise." in result
