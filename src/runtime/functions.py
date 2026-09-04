from typing import Any

from src.runtime.environment import Environment


class FunctionValue:
    """A user-defined function: parameter names, body, and the scope it was
    declared in (used as the parent of the call's fresh scope)."""

    def __init__(self, params: list[str], body: list[Any], env: Environment) -> None:
        self.params = params
        self.body = body
        self.env = env


class _Return(Exception):
    """Control-flow signal: a `>>>` statement unwinds the function body."""
    def __init__(self, value: Any) -> None:
        super().__init__()
        self.value = value