from typing import Tuple

from stitcher.spec import DocstringParserProtocol, DocstringRendererProtocol
from stitcher.lang.python.docstring.parsers import RawDocstringParser, GriffeDocstringParser
from stitcher.lang.python.docstring.renderers import GoogleDocstringRenderer, NumpyDocstringRenderer
from stitcher.lang.python.docstring.serializers import (
    RawSerializer,
    GoogleSerializer,
    NumpySerializer,
)
from stitcher.spec import DocstringSerializerProtocol


class RawDocstringRenderer(DocstringRendererProtocol):
    def render(self, docstring_ir, context=None) -> str:
        # For raw mode, we just return the summary as the full docstring.
        # Addons and other fields are ignored in raw render.
        return docstring_ir.summary or ""


def get_docstring_codec(
    style: str,
) -> Tuple[DocstringParserProtocol, DocstringRendererProtocol]:
    if style == "google":
        return GriffeDocstringParser("google"), GoogleDocstringRenderer()
    elif style == "numpy":
        return GriffeDocstringParser("numpy"), NumpyDocstringRenderer()

    # Default to raw
    return RawDocstringParser(), RawDocstringRenderer()


def get_docstring_serializer(style: str) -> DocstringSerializerProtocol:
    if style == "google":
        return GoogleSerializer()
    elif style == "numpy":
        return NumpySerializer()

    # Default to raw
    return RawSerializer()
