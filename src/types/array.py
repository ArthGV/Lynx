"""The Array type: a mutable list of other values, simple or complex."""

from __future__ import annotations

from typing import Any

from src.types.base_type import ComplexType, Type
from src.types.simple_type import Boolean, Number, Text, Void
from src.utils.text import compare_raw, edit_distance_seq


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

    def length(self) -> Number:
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
            c = a.compare(b) if type(a) is type(b) else compare_raw(a.rank, b.rank)
            if c != 0:
                return c
        return 0

    def almost(self, other: Array) -> Boolean:
        return Boolean(
            edit_distance_seq(
                self.value,
                other.value,
                lambda a, b: type(a) is type(b) and a.equals(b).is_true(),
            )
            <= 1
        )

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
        keys: list[tuple[str, Any] | None] = []
        for item in self.value:
            if isinstance(item, Void):
                keys.append(("Void", "void"))
            elif isinstance(item, (Number, Text, Boolean)):
                keys.append((item.type_name(), item.value))
            else:
                keys.append(None)
        if all(key is not None for key in keys):
            # Simple elements hash canonically — first occurrence wins, same
            # as the pairwise scan below but in O(n) instead of O(n²).
            seen: set[tuple[str, Any]] = set()
            kept: list[Type] = []
            for item, key in zip(self.value, keys):
                assert key is not None
                if key not in seen:
                    seen.add(key)
                    kept.append(item)
            return Array(kept)
        # Nested elements can't be hashed canonically, so fall back to
        # pairwise type-and-equality scanning.
        seen_items: list[Type] = []
        for item in self.value:
            if not any(type(item) is type(prev) and item.equals(prev).is_true() for prev in seen_items):
                seen_items.append(item)
        return Array(seen_items)

    # --- not implemented yet ---
    def add(self, other: Array) -> Type:
        self.todo("add")

    def subtract(self, other: Array) -> Type:
        self.todo("subtract")

    def multiply(self, other: Array) -> Type:
        self.todo("multiply")

    def divide(self, other: Array) -> Type:
        self.todo("divide")

    def power(self, other: Array) -> Type:
        self.todo("power")

    def root(self, other: Array) -> Type:
        self.todo("root")

    def xor(self, other: Array) -> Type:
        self.todo("xor")

    def not_(self) -> Type:
        self.todo("not_")

    def join(self, other: Array) -> Type:
        self.todo("join")
