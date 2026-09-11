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
class MapLiteral:
    pairs: list[Any]  # list of (key_expr, value_expr) tuples
    line: int | None = None


@dataclass
class TableLiteral:
    columns: list[Any]  # list of (name_expr, [value_exprs]) tuples
    line: int | None = None


@dataclass
class SetItem:
    base: str  # variable name holding the container being mutated
    steps: list[Any]  # index/key expressions, applied in order
    value: Any
    line: int | None = None


@dataclass
class Append:
    base: str  # variable name holding the array being mutated
    value: Any  # an Array splices its elements, anything else appends as one
    front: bool = False  # False appends at the end (<:), True at the front (>:)
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
class Loop:
    condition: Any
    body: list[Any]
    targets: list[str] | None = None
    iterable: Any | None = None


@dataclass
class Stop:
    condition: Any | None = None
    line: int | None = None


@dataclass
class Skip:
    condition: Any | None = None
    line: int | None = None


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
class RangeExpression:
    start: Any | None  # None = omitted: `__N` runs up from 0
    end: Any | None    # None = omitted: `N__` runs down to 0
    line: int | None = None


@dataclass
class TableQuery:
    """A table-and-column keyword: `select t 'a'`, `order t 'price'`,
    `group t 'dept'`, `where t 'price' > 20`. `kind` is the keyword's token type
    and `expression` is the raw rest-of-line operand, decomposed by the
    interpreter for each kind."""

    kind: str
    expression: Any
    line: int | None = None


@dataclass
class UnaryExpression:
    operator: str  # a token type, e.g. "LENGHT" — never the spelling
    operand: Any
    line: int | None = None