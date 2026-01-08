from typing import Tuple

from stitcher.spec import DocstringParserProtocol, DocstringRendererProtocol
from .parsers import RawDocstringParser, GriffeDocstringParser
from .renderers import GoogleDocstringRenderer, NumpyDocstringRenderer
from .serializers import (
    RawSerializer,
    GoogleSerializer,
    NumpySerializer,
)
from stitcher.spec import DocstringSerializerProtocol


class RawDocstringRenderer(DocstringRendererProtocol):
    """
    A simple renderer that just dumps the summary.
    Used for 'raw' mode consistency.
    """

    def render(self, docstring_ir, context=None) -> str:
        # For raw mode, we just return the summary as the full docstring.
        # Addons and other fields are ignored in raw render.
        return docstring_ir.summary or ""


def get_docstring_codec(
    style: str,
) -> Tuple[DocstringParserProtocol, DocstringRendererProtocol]:
    """
    Factory to get the parser and renderer for a specific docstring style.

    Args:
        style: "google", "numpy", or "raw".

    Returns:
        (Parser, Renderer) tuple.
    """
    if style == "google":
        return GriffeDocstringParser("google"), GoogleDocstringRenderer()
    elif style == "numpy":
        return GriffeDocstringParser("numpy"), NumpyDocstringRenderer()

    # Default to raw
    return RawDocstringParser(), RawDocstringRenderer()


def get_docstring_serializer(style: str) -> DocstringSerializerProtocol:
    """
    Factory to get the serializer for a specific docstring style.
    """
    if style == "google":
        return GoogleSerializer()
    elif style == "numpy":
        return NumpySerializer()

    # Default to raw
    return RawSerializer()
