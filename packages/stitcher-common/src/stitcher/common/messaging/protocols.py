from typing import Any, Protocol

class Renderer(Protocol):
    """
    Protocol for message renderers. A renderer's only job is to
    present a final, formatted string to the user.
    """

    def render(self, message: str, level: str) -> None:
        """
        Renders the message.

        Args:
            message: The fully resolved string to be displayed.
            level: The log level ("info", "warning", "error", "success").
        """
        ...