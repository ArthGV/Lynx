"""Variable scopes.

A scope holds its own names and defers to its parent for the rest, so nested
scopes (functions, blocks, classes) fall out naturally once we add them.
"""

from __future__ import annotations

from typing import Any

from src.errors.errors import LynxNameError


class Environment:
    def __init__(self, parent: Environment | None = None) -> None:
        self.values: dict[str, Any] = {}
        self.parent = parent

    def get(self, name: str, line: int | None = None) -> Any:
        if name in self.values:
            return self.values[name]
        if self.parent is not None:
            return self.parent.get(name, line)
        raise LynxNameError(f"'{name}' is not defined", line)

    def set(self, name: str, value: Any) -> None:
        self.values[name] = value

    def child(self) -> Environment:
        return Environment(self)