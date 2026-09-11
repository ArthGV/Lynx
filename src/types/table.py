"""The Table type: a matrix of named columns, each a list of values."""

from __future__ import annotations

from functools import cmp_to_key
from typing import Any

from src.types.array import Array
from src.types.base_type import ComplexType, Type
from src.types.map import Map
from src.types.simple_type import Boolean, Number, Text, Void
from src.utils.keys import cells_equal, map_key
from src.utils.text import compare_raw
from src.errors.errors import LynxError, LynxTypeError


class Table(ComplexType):
    """A matrix of named columns, each a list of values of any type.

    Literal form is `[ 'id': 1, 2, 3; 'price': 10, 20, 30 ]` — `:` separates a
    column name from its values, `;` separates columns. Columns need not be
    equal in length: shorter ones are padded with Void up to the longest, so
    every row spans all columns. Access reuses the call machinery: a text key
    picks a column (`my_table 'id'`), a number picks a row (`my_table 0`).
    """

    rank = 6
    conversion = "table"
    default_value = {}

    def __init__(self, columns=None) -> None:
        self.columns: dict[str, list[Type]] = {}
        if columns:
            for name, values in columns:
                if isinstance(name, Text):
                    key = name.value
                elif isinstance(name, str):
                    key = name
                else:
                    raise LynxTypeError(
                        f"table column name must be text, got {type(name).__name__}"
                    )
                self.columns[key] = list(values)
        self.nrows = max((len(col) for col in self.columns.values()), default=0)
        for col in self.columns.values():
            if len(col) < self.nrows:
                col.extend(Void() for _ in range(self.nrows - len(col)))

    def __repr__(self) -> str:
        if not self.columns:
            return "{}"
        names = list(self.columns)
        widths = [self._column_width(name) for name in names]
        top = "┌" + "┬".join("─" * width for width in widths) + "┐"
        header = "│" + "│".join(self._render(name, width) for name, width in zip(names, widths)) + "│"
        lines = [top, header]
        if self.nrows:
            lines.append("├" + "┼".join("─" * width for width in widths) + "┤")
            for i in range(self.nrows):
                cells = [self.columns[name][i] for name in names]
                lines.append("│" + "│".join(self._render(cell, width) for cell, width in zip(cells, widths)) + "│")
        lines.append("└" + "┴".join("─" * width for width in widths) + "┘")
        return "\n".join(lines)

    @staticmethod
    def _display(value) -> str:
        if isinstance(value, Text):
            return repr(value.value)
        return str(value)

    def _column_width(self, name: str) -> int:
        widths = [len(name)]
        for value in self.columns[name]:
            s = self._display(value)
            # Text is quoted so it needs no breathing room; booleans and void
            # eat an extra space on either side like the headers do.
            widths.append(len(s) + 2 if isinstance(value, (Boolean, Void)) else len(s))
        return max(4, *widths)

    def _render(self, value, width: int) -> str:
        if isinstance(value, Number):
            s = str(value)
            if len(s) >= width:
                return s
            return " " * (width - len(s) - 1) + s + " "
        s = self._display(value)
        if isinstance(value, Text):
            if len(s) >= width:
                return s
            return s + " " * (width - len(s))
        if len(s) >= width:
            return s
        return " " + s + " " * (width - len(s) - 1)

    def type_name(self) -> str:
        return "Table"

    def get_column(self, name: str) -> Type:
        column = self.columns.get(name)
        if column is None:
            return Void()
        return Array(list(column))

    def get_row(self, index: int) -> Map:
        return Map([(Text(name), column[index]) for name, column in self.columns.items()])

    def lenght(self) -> Array:
        return Array([Number(self.nrows), Number(len(self.columns))])

    def first(self) -> Type:
        if self.nrows:
            return self.get_row(0)
        return Void()

    def last(self) -> Type:
        if self.nrows:
            return self.get_row(self.nrows - 1)
        return Void()

    def middle(self) -> Type:
        if not self.nrows:
            return Void()
        return self.get_row(self.nrows // 2)

    def compare(self, other: Table) -> int:
        if self.nrows != other.nrows:
            return compare_raw(self.nrows, other.nrows)
        if len(self.columns) != len(other.columns):
            return compare_raw(len(self.columns), len(other.columns))
        for name, column in self.columns.items():
            other_column = other.columns.get(name)
            if other_column is None:
                return compare_raw(repr(name), repr(next(iter(other.columns))))
            for a, b in zip(column, other_column):
                c = a.compare(b) if type(a) is type(b) else compare_raw(a.rank, b.rank)
                if c != 0:
                    return c
        return 0

    def almost(self, other: Table) -> Boolean:
        return self.equals(other)

    def equals(self, other: Table) -> Boolean:
        if self.nrows != other.nrows:
            return Boolean(False)
        if self.columns.keys() != other.columns.keys():
            return Boolean(False)
        for name, column in self.columns.items():
            other_column = other.columns[name]
            for a, b in zip(column, other_column):
                if type(a) is not type(b) or not a.equals(b).is_true():
                    return Boolean(False)
        return Boolean(True)

    def number(self) -> Number:
        return Number(self.nrows)

    def text(self) -> Text:
        return Text(self.__repr__())

    def boolean(self) -> Boolean:
        return Boolean(self.nrows > 0)

    def void(self) -> Void:
        return Void()

    def iterate(self) -> list[Type]:
        return [self.get_row(i) for i in range(self.nrows)]

    # --- SQL-style operations ---

    def distinct(self) -> Table:
        seen: list[Map] = []
        indices: list[int] = []
        for i in range(self.nrows):
            row = self.get_row(i)
            if not any(row.equals(prev).is_true() for prev in seen):
                seen.append(row)
                indices.append(i)
        return self._from_row_indices(indices)

    def select(self, names: list[str], line: int | None = None) -> Type:
        for name in names:
            if name not in self.columns:
                return Void()
        return Table([(name, list(self.columns[name])) for name in names])

    def order_by(self, name: str, line: int | None = None) -> Table:
        if name not in self.columns:
            raise LynxError(f"table has no column '{name}'", line)
        column = self.columns[name]
        ordered = sorted(
            range(self.nrows),
            key=cmp_to_key(lambda i, j: self._compare_cells(column[i], column[j])),
        )
        return self._from_row_indices(ordered)

    @staticmethod
    def _compare_cells(a: Type, b: Type) -> int:
        if type(a) is type(b):
            return a.compare(b)
        return compare_raw(a.rank, b.rank)

    def group_by(self, name: str, line: int | None = None) -> Map:
        if name not in self.columns:
            raise LynxError(f"table has no column '{name}'", line)
        groups: dict[Any, tuple[Type, list[int]]] = {}
        for i in range(self.nrows):
            value = self.columns[name][i]
            raw = map_key(value)
            if raw not in groups:
                groups[raw] = (value, [])
            groups[raw][1].append(i)
        result = Map()
        for raw, (value, indices) in groups.items():
            result.set_item(value, self._from_row_indices(indices))
        return result

    def rows_where(self, name: str, operator: str, rhs: Type, line: int | None = None) -> Table:
        if name not in self.columns:
            raise LynxError(f"table has no column '{name}'", line)
        from src.core.grammar import BINARY_METHOD
        from src.runtime import operations as ops

        method = BINARY_METHOD.get(operator, operator)
        column = self.columns[name]
        kept: list[int] = []
        for i in range(self.nrows):
            result = ops.binary(method, column[i], rhs)
            if result.boolean().is_true():
                kept.append(i)
        return self._from_row_indices(kept)

    def join(self, other: Table, line: int | None = None) -> Table:
        shared = [name for name in self.columns if name in other.columns]
        if not shared:
            return Table([])
        names = list(self.columns) + [name for name in other.columns if name not in shared]
        columns: dict[str, list[Type]] = {name: [] for name in names}
        for r in range(self.nrows):
            for s in range(other.nrows):
                if all(cells_equal(self.columns[name][r], other.columns[name][s]) for name in shared):
                    for name in self.columns:
                        columns[name].append(self.columns[name][r])
                    for name in other.columns:
                        if name not in shared:
                            columns[name].append(other.columns[name][s])
        return Table(list(columns.items()))

    def _from_row_indices(self, indices: list[int]) -> Table:
        return Table([(name, [column[i] for i in indices]) for name, column in self.columns.items()])

    def count(self) -> Number:
        return Number(self.nrows)

    # --- not implemented yet ---
    def add(self, other: Table) -> Type: self.todo("add")
    def subtract(self, other: Table) -> Type: self.todo("subtract")
    def multiply(self, other: Table) -> Type: self.todo("multiply")
    def divide(self, other: Table) -> Type: self.todo("divide")
    def power(self, other: Table) -> Type: self.todo("power")
    def root(self, other: Table) -> Type: self.todo("root")
    def xor(self, other: Table) -> Type: self.todo("xor")
    def not_(self) -> Type: self.todo("not_")
    def sum(self) -> Type: self.todo("sum")
    def avg(self) -> Type: self.todo("avg")
    def min(self) -> Type: self.todo("min")
    def max(self) -> Type: self.todo("max")