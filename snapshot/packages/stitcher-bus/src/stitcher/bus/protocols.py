from typing import Protocol


class Renderer(Protocol):
    def render(self, message: str, level: str) -> None: ...
