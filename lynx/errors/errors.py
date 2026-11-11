"""Errors lynx raises for the user, as opposed to Python bugs in the interpreter.

Each carries an optional line number so main.py can print a clean message
instead of a Python traceback.
"""


class LynxError(Exception):
    kind = "Error"

    def __init__(self, message: str, line: int | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.line = line

    def __str__(self) -> str:
        where = f" on line {self.line}" if self.line is not None else ""
        suffix = f": {self.message}" if self.message else ""
        return f"{self.kind}{where}{suffix}"


class LynxSyntaxError(LynxError):
    kind = "SyntaxError"


class LynxNameError(LynxError):
    kind = "NameError"


class LynxTypeError(LynxError):
    kind = "TypeError"


class LynxInputError(LynxError):
    """An operation got input of the wrong count or shape: too few or too many
    function arguments, a slice replaced by a different length, too many loop
    variables."""

    kind = "InputError"


class LynxReturnError(LynxError):
    """`>>>` used outside of a function body."""

    kind = "ReturnError"


class LynxNotImplemented(LynxError):
    """An operation that the language intends to support but nobody has
    written the logic for yet — a hole to fill, not a user mistake."""

    kind = "NotImplemented"


class LynxInterpreterError(LynxError):
    """A Python exception escaped the interpreter: a bug or an edge case not
    yet converted to a specific lynx error. The original is kept as `__cause__`."""

    kind = "InterpreterError"


class LynxTestError(LynxError):
    """A test assertion failure."""

    kind = "TestError"
