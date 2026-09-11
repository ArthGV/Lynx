"""The Array type: a mutable list of other values, simple or complex."""

from __future__ import annotations

from src.types.base_type import ComplexType, Type
from src.types.simple_type import Boolean, Number, Text, Void
from src.utils.text import compare_raw


class Array(ComplexType):
    """A mutable list of other values, simple or complex.

    Literal form is comma-separated and bracket-free: `my_array: 1, true, 'hi'`.
    Element access reuses the call machinery: `my_array 0`, chained for nesting.
    """

    rank = 4
    conversion = "array"
    default_value = []

    def __init__(self, items: list[Type]) -> None:
        self.value = list(items)

    def __repr__(self) -> str:
        return "[ " + ", ".join(str(item) for item in self.value) + " ]"

    def type_name(self) -> str:
        return "Array"

    def lenght(self) -> Number:
        return Number(len(self.value))

    def first(self) -> Type:
        if len(self.value) > 0:
            return self.value[0]
        return Void()

    def last(self) -> Type:
        if len(self.value) > 0:
            return self.value[-1]
        return Void()

    def middle(self) -> Type:
        if len(self.value) == 0:
            return Void()
        return self.value[len(self.value) // 2]

    def compare(self, other: Array) -> int:
        if len(self.value) != len(other.value):
            return compare_raw(len(self.value), len(other.value))
        for a, b in zip(self.value, other.value):
            if type(a) is type(b):
                c = a.compare(b)
            else:
                c = compare_raw(a.rank, b.rank)
            if c != 0:
                return c
        return 0

    def almost(self, other: Array) -> Boolean:
        return self.equals(other)

    def equals(self, other: Array) -> Boolean:
        if len(self.value) != len(other.value):
            return Boolean(False)
        for a, b in zip(self.value, other.value):
            if type(a) is type(b):
                if not a.equals(b).is_true():
                    return Boolean(False)
            else:
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

    def iterate(self) -> list[Type]:
        return list(self.value)

    # --- SQL-style operations ---

    def sum(self) -> Type:
        numbers = [v for v in self.value if isinstance(v, Number)]
        if not numbers:
            return Void()
        return Number(sum(v.value for v in numbers))

    def avg(self) -> Type:
        numbers = [v for v in self.value if isinstance(v, Number)]
        if not numbers:
            return Void()
        return Number(sum(v.value for v in numbers) / len(numbers))

    def min(self) -> Type:
        numbers = [v for v in self.value if isinstance(v, Number)]
        if not numbers:
            return Void()
        return Number(min(v.value for v in numbers))

    def max(self) -> Type:
        numbers = [v for v in self.value if isinstance(v, Number)]
        if not numbers:
            return Void()
        return Number(max(v.value for v in numbers))

    def count(self) -> Number:
        return Number(len(self.value))

    def distinct(self) -> Array:
        seen: list[Type] = []
        for item in self.value:
            if not any(type(item) is type(seen_item) and item.equals(seen_item).is_true() for seen_item in seen):
                seen.append(item)
        return Array(seen)

    # --- not implemented yet ---
    def add(self, other: Array) -> Type: self.todo("add")
    def subtract(self, other: Array) -> Type: self.todo("subtract")
    def multiply(self, other: Array) -> Type: self.todo("multiply")
    def divide(self, other: Array) -> Type: self.todo("divide")
    def power(self, other: Array) -> Type: self.todo("power")
    def root(self, other: Array) -> Type: self.todo("root")
    def xor(self, other: Array) -> Type: self.todo("xor")
    def not_(self) -> Type: self.todo("not_")
    def join(self, other: Array) -> Type: self.todo("join")