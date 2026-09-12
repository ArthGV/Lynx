"""The Map type: a mutable collection of key→value pairs."""

from __future__ import annotations

from src.types.base_type import ComplexType, Type
from src.types.simple_type import Boolean, Number, Text, Void
from src.utils.keys import map_key, value_from_key
from src.utils.text import compare_raw


class Map(ComplexType):
    """A mutable collection of key→value pairs whose keys are simple types.

    Literal form is `{ 'a': 1; 'b': 2 }` — `;` separates entries so values can
    be arrays without colliding with the `,` of an array literal. Access reuses
    the call machinery: `my_map 'a'`, chained for nested maps.
    """

    rank = 5
    conversion = "map"
    default_value = {}

    def __init__(self, entries=None) -> None:
        self.value: dict[tuple, Type] = {}
        if entries:
            for key, value in entries:
                self.set_item(key, value)

    def set_item(self, key: Type, value: Type) -> None:
        self.value[map_key(key)] = value

    def get_item(self, key: Type) -> Type:
        return self.value.get(map_key(key), Void())

    def __repr__(self) -> str:
        if not self.value:
            return "{}"
        parts = []
        for raw, value in self.value.items():
            parts.append(f"{raw[1]}: {value}")
        return "{ " + "; ".join(parts) + " }"

    def type_name(self) -> str:
        return "Map"

    def length(self) -> Number:
        return Number(len(self.value))

    def first(self) -> Type:
        if self.value:
            return next(iter(self.value.values()))
        return Void()

    def last(self) -> Type:
        if self.value:
            return list(self.value.values())[-1]
        return Void()

    def middle(self) -> Type:
        if not self.value:
            return Void()
        values = list(self.value.values())
        return values[len(values) // 2]

    def compare(self, other: Map) -> int:
        if len(self.value) != len(other.value):
            return compare_raw(len(self.value), len(other.value))
        for (rk, rv), (ok, ov) in zip(self.value.items(), other.value.items()):
            if rk != ok:
                return compare_raw(repr(rk), repr(ok))
            c = rv.compare(ov) if type(rv) is type(ov) else compare_raw(rv.rank, ov.rank)
            if c != 0:
                return c
        return 0

    def almost(self, other: Map) -> Boolean:
        return self.equals(other)

    def equals(self, other: Map) -> Boolean:
        if len(self.value) != len(other.value):
            return Boolean(False)
        for (rk, rv) in self.value.items():
            if rk not in other.value:
                return Boolean(False)
            ov = other.value[rk]
            if type(rv) is not type(ov) or not rv.equals(ov).is_true():
                return Boolean(False)
        return Boolean(True)

    def number(self) -> Number:
        return Number(len(self.value))

    def text(self) -> Text:
        return Text(self.__repr__())

    def boolean(self) -> Boolean:
        return Boolean(len(self.value) > 0)

    def void(self) -> Void:
        return Void()

    def keys(self) -> list[Type]:
        """The map's keys in insertion order, rebuilt into values."""
        return [value_from_key(raw) for raw in self.value.keys()]

    def iterate(self) -> list[Type]:
        return self.keys()

    def count(self) -> Number:
        return Number(len(self.value))

    def distinct(self) -> Map:
        return self

    # --- not implemented yet ---
    def add(self, other: Map) -> Type: self.todo("add")
    def subtract(self, other: Map) -> Type: self.todo("subtract")
    def multiply(self, other: Map) -> Type: self.todo("multiply")
    def divide(self, other: Map) -> Type: self.todo("divide")
    def power(self, other: Map) -> Type: self.todo("power")
    def root(self, other: Map) -> Type: self.todo("root")
    def xor(self, other: Map) -> Type: self.todo("xor")
    def not_(self) -> Type: self.todo("not_")
    def sum(self) -> Type: self.todo("sum")
    def avg(self) -> Type: self.todo("avg")
    def min(self) -> Type: self.todo("min")
    def max(self) -> Type: self.todo("max")
    def join(self, other: Map) -> Type: self.todo("join")