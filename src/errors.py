"""Errors lynx raises for the user, as opposed to Python bugs in the interpreter.

Each carries an optional line number so main.py can print a clean message
instead of a Python traceback.
"""


class LynxError(Exception):
    kind = "Error"

    def __init__(self, message, line=None):
        super().__init__(message)
        self.message = message
        self.line = line

    def __str__(self):
        where = f" on line {self.line}" if self.line is not None else ""
        return f"{self.kind}{where}: {self.message}"


class LynxSyntaxError(LynxError):
    kind = "SyntaxError"


class LynxNameError(LynxError):
    kind = "NameError"


class LynxTypeError(LynxError):
    kind = "TypeError"


class LynxNotImplemented(LynxError):
    """An operation that the language intends to support but nobody has
    written the logic for yet — a hole to fill, not a user mistake."""
    kind = "NotImplemented"
