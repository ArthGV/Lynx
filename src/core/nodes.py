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
class Cell:
    """A parenthesized value written in a column slot: kept as one element.

    `(4, 5)`, `(a)` and `(__7)` in a table column each store the array as a
    single cell, while a bare array value (`a`, `1__5`) becomes the whole
    column. `evaluate` unwraps a Cell to its inner value everywhere else.
    """

    inner: Any  # the parenthesized expression


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
class Delete:
    """`del <name>` or `del <name> <step>...`. Empty `steps` deletes the whole
    variable; otherwise each step descends into a container and the last one
    is what gets removed — an array index or slice, a map key, or a table
    column name or row index."""

    base: str  # variable name holding the value being deleted from
    steps: list[Any]  # index/key expressions, applied in order; [] = the variable
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
class Write:
    value: Any
    path: Any
    line: int | None = None


@dataclass
class Read:
    """`read 'path'`: reads a file and returns its value. The path operand is
    a text expression here — this node replaces the old per-type `read` method,
    so no Value type carries `read` anymore."""

    operand: Any
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
    end: Any | None  # None = omitted: `N__` runs down to 0
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
class GraphSegment:
    """One `;`-separated statement of a graph literal: a source node, its
    optional value, a target comma-run, and an optional label. The label is
    applied to every edge this segment creates; when present the targets may
    each carry their own value."""

    source: str  # the bare node id
    value: Any | None  # a parenthesized node value, or None
    targets: list[tuple[str, Any | None]]  # (node id, value or None) pairs
    label: Any | None  # an expression evaluating to a Text, or None
    line: int | None = None


@dataclass
class GraphLiteral:
    """`g: a('Ida') -> b, c : 'loves'; d -> e` — nodes, edges and labels."""

    segments: list[GraphSegment]
    line: int | None = None


@dataclass
class GraphBuild:
    """`graph` (an empty graph) or `graph <operand>` (a table of node/edge
    records to convert into a graph)."""

    operand: Any | None
    line: int | None = None


@dataclass
class GraphQuery:
    """`from g 'a'` / `to g 'b'`: the node ids a node points at / is pointed
    at by, as an array. `kind` is FROM or TO."""

    kind: str
    graph: Any  # expression evaluating to a Graph
    node: Any  # expression evaluating to a node id
    line: int | None = None


@dataclass
class EdgeStep:
    """The `-> 'to'` of an edge access or mutation step. Appears as a call
    argument (`g 'a' -> 'b'`), a mutation/delete step (`g 'a' -> 'b': 'l'`,
    `del g 'a' -> 'b'`). `target` evaluates to the edge's target node id."""

    target: Any
    line: int | None = None


@dataclass
class EdgeCreate:
    """The right-hand side of an edge-creating mutation: `g 'x': -> 'z'` or
    `g 'x': -> 'z'('loves')`. `target` evaluates to the target node id and
    `value` (optional) to the node value / edge label."""

    target: Any
    value: Any | None
    line: int | None = None


@dataclass
class UnaryExpression:
    operator: str  # a token type, e.g. "LENGTH" — never the spelling
    operand: Any
    line: int | None = None
