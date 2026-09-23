"""The Graph type: a mutable collection of nodes and directed edges.

Nodes and edges both carry values: a node's value is a plain `Type` (Void for
a valueless node), an edge's is called its label. Node ids are Text. A graph
is immutable-looking from the outside but mutated in place by `g 'id': value`,
`g 'a' -> 'b': label`, `del g ...` — the same call machinery every other
collection uses.

The literal form is `a('Ida') -> b, c : 'loves'; d -> e` — `;` separates
segments, each with one source, a target comma-run and (once) a shared label.
`text()` renders that form back: one line per (source, label) group, in
first-appearance order, then isolated nodes.

CSV round-trips through four columns — `kind, from, to, value` — where a
`node` row carries just an id and a `edge` row carries both endpoints (see
`core/files.py`). Array node values survive as a parenthesized cell `(1, 2)`.
"""

from __future__ import annotations

from typing import Any

from src.errors.errors import LynxError, LynxTypeError
from src.types.array import Array
from src.types.base_type import ComplexType, Type
from src.types.simple_type import Boolean, Number, Text, Void
from src.types.table import Table
from src.utils.text import compare_raw, edit_distance_sets


class Graph(ComplexType):
    """A mutable collection of nodes and directed edges.

    `nodes` maps an id to the node's value; `edges` maps an (source, target)
    id pair to the label. Both preserve insertion order.
    """

    rank = 7
    conversion = "graph"
    default_value = None

    def __init__(self, records: Type | None = None, line: int | None = None) -> None:
        self.nodes: dict[str, Type] = {}
        self.edges: dict[tuple[str, str], Type] = {}
        if records is None:
            return
        if isinstance(records, Graph):
            # A copy: `h: graph g` aliases nothing.
            self.nodes = dict(records.nodes)
            self.edges = dict(records.edges)
            return
        if isinstance(records, Table):
            self._from_table(records, line)
            return
        raise LynxTypeError(f"cannot build a graph from a {records.type_name()}", line)

    def _from_table(self, table: Table, line: int | None) -> None:
        # A graph csv (or any table with the same shape) carries one row per
        # record: `kind,from,to,value`. `node` rows define a node's value;
        # `edge` rows create both endpoints and the label in one go.
        for column in ("kind", "from", "to", "value"):
            if column not in table.columns:
                raise LynxError(
                    "cannot convert a table into a graph without the columns kind, from, to, value",
                    line,
                )
        for i in range(table.nrows):
            kind = table.columns["kind"][i]
            if not isinstance(kind, Text):
                raise LynxError(f"unknown graph row kind '{kind}'", line)
            if kind.value == "node":
                node_id = _text_cell(table.columns["from"][i], "node", line)
                value = self._value_cell(table.columns["value"][i])
                if node_id in self.nodes:
                    raise LynxTypeError(f"node '{node_id}' is defined twice", line)
                self.nodes[node_id] = value
            elif kind.value == "edge":
                source = _text_cell(table.columns["from"][i], "edge", line)
                target = _text_cell(table.columns["to"][i], "edge", line)
                self.nodes.setdefault(source, Void())
                self.nodes.setdefault(target, Void())
                self.edges[(source, target)] = self._value_cell(table.columns["value"][i])
            else:
                raise LynxError(f"unknown graph row kind '{kind.value}'", line)

    @staticmethod
    def _value_cell(value: Type) -> Type:
        # CSV reading types a `(1, 2, 3)` value cell as Text (it has commas
        # and gets quoted); a parenthesized comma-run is an array round-trip.
        if isinstance(value, Text):
            parsed = _parse_array_cell(value.value)
            if parsed is not None:
                return parsed
        return value

    # --- basic reads --------------------------------------------------------

    def type_name(self) -> str:
        return "Graph"

    def get_item(self, key: Type) -> Type:
        if not isinstance(key, Text):
            raise LynxTypeError(f"a graph node id must be a Text, got {key.type_name()}")
        return self.nodes.get(key.value, Void())

    def set_node(self, node_id: str, value: Type) -> None:
        # Upsert: create the node or overwrite its value.
        self.nodes[node_id] = value

    def get_edge_label(self, source: str, target: str) -> Type:
        return self.edges.get((source, target), Void())

    def set_edge_label(self, source: str, target: str, label: Type, line: int | None = None) -> None:
        # Strict: mirrors the literal, never creating an edge silently.
        if (source, target) not in self.edges:
            raise LynxError(f"edge '{source}' -> '{target}' does not exist", line)
        self.edges[(source, target)] = label

    def create_edge(self, source: str, target: str, label: Type, line: int | None = None) -> None:
        # `g 'from': -> 'to'` — the source must be a known node; the target is
        # created as a by-product (unless it is the source itself).
        if source == target:
            raise LynxError(f"cannot create an edge from '{source}' to itself", line)
        if source not in self.nodes:
            raise LynxError(f"cannot create an edge from missing node '{source}'", line)
        self.nodes.setdefault(target, Void())
        self.edges[(source, target)] = label

    def delete_node(self, node_id: str) -> None:
        self.nodes.pop(node_id, None)
        for (source, target) in list(self.edges):
            if source == node_id or target == node_id:
                del self.edges[(source, target)]

    def delete_edge(self, source: str, target: str) -> None:
        self.edges.pop((source, target), None)

    def out_neighbors(self, node_id: Type) -> Type:
        if not isinstance(node_id, Text):
            raise LynxTypeError(f"a graph node id must be a Text, got {node_id.type_name()}")
        if node_id.value not in self.nodes:
            return Void()
        return Array([Text(target) for (source, target) in self.edges if source == node_id.value])

    def in_neighbors(self, node_id: Type) -> Type:
        if not isinstance(node_id, Text):
            raise LynxTypeError(f"a graph node id must be a Text, got {node_id.type_name()}")
        if node_id.value not in self.nodes:
            return Void()
        return Array([Text(source) for (source, target) in self.edges if target == node_id.value])

    # --- conversions -------------------------------------------------------

    def number(self) -> Number:
        return Number(len(self.nodes))

    def boolean(self) -> Boolean:
        return Boolean(len(self.nodes) > 0)

    def void(self) -> Void:
        return Void()

    def text(self) -> Text:
        return Text(self.__repr__())

    def __repr__(self) -> str:
        if not self.nodes:
            return "graph"
        if not self.edges:
            return "\n".join(self._fragment(node_id) for node_id in self.nodes)
        lines: list[str] = []
        groups: dict[tuple[str, tuple[str, Any]], list[str]] = {}
        labels: dict[tuple[str, tuple[str, Any]], Type] = {}
        order: list[tuple[str, tuple[str, Any]]] = []
        incident: set[str] = set()
        for (source, target), label in self.edges.items():
            incident.add(source)
            incident.add(target)
            key = (source, _label_key(label))
            if key not in groups:
                groups[key] = [target]
                labels[key] = label
                order.append(key)
            else:
                groups[key].append(target)
        for (source, label_group), targets in groups.items():
            line = self._fragment(source) + " -> " + ", ".join(self._fragment(target) for target in targets)
            inline = _inline(labels[(source, label_group)])
            if inline is not None:
                line += " : " + inline
            lines.append(line)
        for node_id in self.nodes:
            if node_id not in incident:
                lines.append(self._fragment(node_id))
        return "\n".join(lines)

    def _fragment(self, node_id: str) -> str:
        value = self.nodes.get(node_id, Void())
        rendered = _inline(value)
        return node_id if rendered is None else f"{node_id}({rendered})"

    # --- sequence access over node ids --------------------------------------

    def length(self) -> Array:
        return Array([Number(len(self.nodes)), Number(len(self.edges))])

    def first(self) -> Type:
        if self.nodes:
            return Text(next(iter(self.nodes)))
        return Void()

    def last(self) -> Type:
        if self.nodes:
            return Text(list(self.nodes)[-1])
        return Void()

    def middle(self) -> Type:
        if not self.nodes:
            return Void()
        return Text(list(self.nodes)[len(self.nodes) // 2])

    def iterate(self) -> list[Type]:
        return [Text(node_id) for node_id in self.nodes]

    # --- ordering ------------------------------------------------------------

    def compare(self, other: Graph) -> int:
        if len(self.nodes) != len(other.nodes):
            return compare_raw(len(self.nodes), len(other.nodes))
        if len(self.edges) != len(other.edges):
            return compare_raw(len(self.edges), len(other.edges))
        return 0

    def equals(self, other: Graph) -> Boolean:
        # Structural: ids, values and labels must match, but creation order
        # and the order records were added do not matter.
        if set(self.nodes) != set(other.nodes):
            return Boolean(False)
        for node_id, value in self.nodes.items():
            other_value = other.nodes[node_id]
            if type(value) is not type(other_value) or not value.equals(other_value).is_true():
                return Boolean(False)
        if set(self.edges) != set(other.edges):
            return Boolean(False)
        for edge, label in self.edges.items():
            other_label = other.edges[edge]
            if type(label) is not type(other_label) or not label.equals(other_label).is_true():
                return Boolean(False)
        return Boolean(True)

    def almost(self, other: Graph) -> Boolean:
        node_edits = edit_distance_sets(set(self.nodes), set(other.nodes))
        edge_edits = edit_distance_sets(self._edge_signatures(), other._edge_signatures())
        return Boolean(node_edits + edge_edits <= 1)

    def _edge_signatures(self) -> set[str]:
        return {
            f"{source}->{target}:{_label_key(label)!r}"
            for (source, target), label in self.edges.items()
        }

    # --- SQL-style operations --------------------------------------------------

    def count(self) -> Number:
        return Number(len(self.nodes))

    def distinct(self) -> Graph:
        return self

    # --- not implemented yet ---

    def add(self, other: Graph) -> Type:
        self.todo("add")

    def subtract(self, other: Graph) -> Type:
        self.todo("subtract")

    def multiply(self, other: Graph) -> Type:
        self.todo("multiply")

    def divide(self, other: Graph) -> Type:
        self.todo("divide")

    def power(self, other: Graph) -> Type:
        self.todo("power")

    def root(self, other: Graph) -> Type:
        self.todo("root")

    def xor(self, other: Graph) -> Type:
        self.todo("xor")

    def not_(self) -> Type:
        self.todo("not_")

    def sum(self) -> Type:
        self.todo("sum")

    def avg(self) -> Type:
        self.todo("avg")

    def min(self) -> Type:
        self.todo("min")

    def max(self) -> Type:
        self.todo("max")

    def join(self, other: Graph) -> Type:
        self.todo("join")


def _text_cell(value: Type, kind: str, line: int | None) -> str:
    if not isinstance(value, Text):
        raise LynxTypeError(f"a graph {kind} id must be a Text, got {value.type_name()}", line)
    return value.value


def _label_key(label: Type) -> tuple[str, Any]:
    if isinstance(label, Void):
        return ("void", None)
    if isinstance(label, Text):
        return ("text", label.value)
    if isinstance(label, Number):
        return ("number", label.value)
    if isinstance(label, Boolean):
        return ("boolean", label.value)
    return (label.type_name(), repr(label))


def _inline(value: Type) -> str | None:
    """The parenthesized inline form of a value in a graph's literal rendering:
    text is quoted, arrays are bare comma-runs, nothing prints for void."""
    if isinstance(value, Void):
        return None
    if isinstance(value, Text):
        return f"'{value.value}'"
    if isinstance(value, Array):
        return ", ".join(_inline(item) or "void" for item in value.value)
    return str(value)


def _parse_array_cell(text: str) -> Type | None:
    """Turn a `(1, 2, 3)` value cell back into an Array, or None if the text
    is not a balanced parenthesized comma-run (e.g. plain text `(oops`)."""
    if not (text.startswith("(") and text.endswith(")") and len(text) > 2):
        return None
    parts = text[1:-1].split(",")
    items: list[Type] = []
    for part in parts:
        items.append(_infer_array_item(part.strip()))
    return Array(items)


def _infer_array_item(text: str) -> Type:
    from src.core.files import _infer_cell

    if text.startswith("'") and text.endswith("'"):
        return Text(text[1:-1])
    return _infer_cell(text, False)
