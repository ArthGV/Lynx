from typing import Any

from lynx.runtime.environment import Environment


class FunctionValue:
    """A user-defined function: parameter names, body, and the scope it was
    declared in (used as the parent of the call's fresh scope)."""

    def __init__(self, name: str, params: list[str], body: list[Any], env: Environment) -> None:
        self.name = name
        self.params = params
        self.body = body
        self.env = env

    def type_name(self) -> str:
        return "Function"

    def __repr__(self) -> str:
        return f"LynxFunction: {self.name}"


class _Return(Exception):
    """Control-flow signal: a `>>>` statement unwinds the function body."""

    def __init__(self, value: Any) -> None:
        super().__init__()
        self.value = value


class _Stop(Exception):
    """Control-flow signal: a `stop` statement exits the innermost loop."""


class _Skip(Exception):
    """Control-flow signal: a `skip` statement jumps to the next iteration."""
