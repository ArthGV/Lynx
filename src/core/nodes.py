"""AST node definitions.

Each node is a plain dataclass; the interpreter matches on their types.
Nodes that can fail at runtime carry a `line` for error messages.
"""

from dataclasses import dataclass
from typing import Any


@dataclass
class Program:
    statements: list[Any]


@dataclass
class Assignment:
    name: str
    value: Any


@dataclass
class ArrayLiteral:
    items: list[Any]
    line: int | None = None


@dataclass
class Function:
    name: str
    params: list[Any]
    body: list[Any]


@dataclass
class Call:
    callee: str
    args: list[Any]
    line: int | None = None


@dataclass
class Return:
    value: Any
    line: int | None = None


@dataclass
class Print:
    value: Any


@dataclass
class Branch:
    condition: Any
    body: list[Any]


@dataclass
class If:
    branches: list[Any]
    else_body: list[Any] | None = None


@dataclass
class Number:
    value: Any


@dataclass
class Text:
    value: Any


@dataclass
class Boolean:
    value: Any


@dataclass
class Void:
    pass


@dataclass
class Identifier:
    name: str
    line: int | None = None


@dataclass
class BinaryExpression:
    left: Any
    operator: str  # a token type, e.g. "PLUS" — never the character
    right: Any
    line: int | None = None


@dataclass
class UnaryExpression:
    operator: str  # a token type, e.g. "LENGHT" — never the spelling
    operand: Any
    line: int | None = None