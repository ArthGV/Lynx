"""AST node definitions.

Each node is a plain dataclass; the interpreter matches on their types.
Nodes that can fail at runtime carry a `line` for error messages.
"""

from dataclasses import dataclass


@dataclass
class Program:
    statements: list


@dataclass
class Assignment:
    name: str
    value: object


@dataclass
class Function:
    name: str
    params: list
    body: list


@dataclass
class Call:
    callee: str
    args: list
    line: int | None = None


@dataclass
class Return:
    value: object
    line: int | None = None


@dataclass
class Print:
    value: object


@dataclass
class Branch:
    condition: object
    body: list


@dataclass
class If:
    branches: list
    else_body: list | None = None


@dataclass
class Number:
    value: object


@dataclass
class Text:
    value: object


@dataclass
class Boolean:
    value: object


@dataclass
class Void:
    pass


@dataclass
class Identifier:
    name: str
    line: int | None = None


@dataclass
class BinaryExpression:
    left: object
    operator: str  # a token type, e.g. "PLUS" — never the character
    right: object
    line: int | None = None


@dataclass
class UnaryExpression:
    operator: str  # a token type, e.g. "LENGHT" — never the spelling
    operand: object
    line: int | None = None
