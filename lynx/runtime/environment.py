"""Variable scopes.

A scope holds its own names and defers to its parent for the rest, so nested
scopes (functions, blocks, classes) fall out naturally once we add them.
"""

from __future__ import annotations

from typing import Any

from lynx.errors.errors import LynxNameError


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
        # Declare `name` in *this* scope, shadowing any outer one: function
        # parameters, loop variables, the catch variable, function definitions.
        self.values[name] = value

    def assign(self, name: str, value: Any) -> None:
        # Plain assignment: update the nearest scope that already holds `name`,
        # else create it here. Iterative so deep scope chains can't overflow.
        scope: Environment | None = self
        while scope is not None:
            if name in scope.values:
                scope.values[name] = value
                return
            scope = scope.parent
        self.values[name] = value

    def delete(self, name: str, line: int | None = None) -> None:
        # Removes the name from whichever scope holds it, like `get` finds it.
        # Deleting a name that was never assigned is an error, same as reading one.
        if name in self.values:
            del self.values[name]
            return
        if self.parent is not None:
            self.parent.delete(name, line)
            return
        raise LynxNameError(f"'{name}' is not defined", line)

    def child(self) -> Environment:
        return Environment(self)
