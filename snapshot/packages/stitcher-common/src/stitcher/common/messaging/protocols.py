from typing import Any, Protocol

class Renderer(Protocol):
    """
    Protocol defining the interface for all message renderers.
    A renderer is responsible for taking a message intent and its data
    and presenting it to the user.
    """

    def render(self, msg_id: str, level: str, **kwargs: Any) -> None:
        """
        The core rendering method.

        Args:
            msg_id: The semantic ID of the message (e.g., "generate.file.success").
            level: The log level ("info", "warning", "error", "success").
            **kwargs: The context data for the message template.
        """
        ...