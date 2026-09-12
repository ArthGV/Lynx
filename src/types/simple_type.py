"""The scalar types and the SimpleType marker.

`SimpleType` is the family of single-value types; the four scalars — Number,
Text, Boolean, Void — subclass it here, in one file. Values made of other
values (Array, Map, Table) each live in their own module, and everything's
interface lives in `base_type.py`.
"""

from __future__ import annotations

from src.core.grammar import SPELLING
from src.types.base_type import Type
from src.utils.text import compare_raw, edit_distance


class SimpleType(Type):
    """A value made of a single scalar: Number, Text, Boolean, Void."""


class Number(SimpleType):
    rank = 3
    conversion = "number"
    default_value = 0

    def __init__(self, value: int | float | str) -> None:
        self.value = float(value)
        if self.value % 1 == 0:
            self.value = int(self.value)

    def __repr__(self) -> str:
        return str(self.value)

    def boolean(self) -> Boolean:
        return Boolean(self.value > 0)

    def add(self, other: Number) -> Number:
        return Number(self.value + other.value)

    def subtract(self, other: Number) -> Number:
        return Number(self.value - other.value)

    def multiply(self, other: Number) -> Number:
        return Number(self.value * other.value)

    def divide(self, other: Number) -> Number | Void:
        if other.value == 0:
            return Void()
        return Number(self.value / other.value)

    def compare(self, other: Number) -> int:
        return compare_raw(self.value, other.value)

    def number(self) -> Number:
        return self

    def text(self) -> Text:
        return Text(str(self.value))

    def void(self) -> Void:
        return Void()

    def not_(self) -> Number:
        return Number(1 - self.value)

    def almost(self, other: Number) -> Boolean:
        return Boolean(abs(self.value - other.value) < 1)

    def length(self) -> Number:
        return Number(len(str(self.value).replace('.', '').replace('-', '')))

    def first(self) -> Number:
        return Number(str(self.value).replace('.', '').replace('-', '')[0])

    def last(self) -> Number:
        return Number(str(self.value)[-1])

    def middle(self) -> Number:
        digits = str(self.value).replace('.', '').replace('-', '')
        return Number(digits[len(digits) // 2])

    def power(self, other: Number) -> Number:
        return Number(self.value ** other.value)

    def root(self, other: Number) -> Number | Void:
        if other.value == 0:
            return Void()
        return Number(self.value ** (1 / other.value))

    def xor(self, other: Number) -> Number:
        s = self.value + other.value
        return Number(s * (1 - s))

    def sum(self) -> Number:
        return self

    def avg(self) -> Number:
        return self

    def min(self) -> Number:
        return self

    def max(self) -> Number:
        return self

    def count(self) -> Number:
        return Number(1)

    def distinct(self) -> Number:
        return self

    def join(self, other: Number) -> Type:
        self.todo("join")

    def iterate(self) -> list[Type]:
        # Closest integer, then counts 0..n (n >= 0) or 0..n (n < 0, descending).
        n = round(self.value)
        if n >= 0:
            return [Number(i) for i in range(0, n + 1)]
        return [Number(i) for i in range(0, n - 1, -1)]


class Text(SimpleType):
    rank = 2
    conversion = "text"
    default_value = ''

    def __init__(self, value: str) -> None:
        self.value = value

    def __repr__(self) -> str:
        return str(self.value)

    def add(self, other: Text) -> Text:
        return Text(self.value + other.value)

    def compare(self, other: Text) -> int:
        return compare_raw(self.value, other.value)

    def number(self) -> Number:
        try:
            return Number(self.value)
        except ValueError:
            return Number(len(self.value))

    def text(self) -> Text:
        return self

    def void(self) -> Void:
        return Void()

    def length(self) -> Number:
        return Number(len(self.value))

    def first(self) -> Text:
        if len(self.value) > 0:
            return Text(self.value[0])
        return Text('')

    def last(self) -> Text:
        if len(self.value) > 0:
            return Text(self.value[-1])
        return Text('')

    def middle(self) -> Text:
        if len(self.value) == 0:
            return Text('')
        return Text(self.value[len(self.value) // 2])

    def boolean(self) -> Boolean:
        return Boolean(self.value != '')

    def not_(self) -> Text:
        return Text(str(1 - self.number().value))

    def subtract(self, other: Text) -> Text:
        return Text(self.value.replace(other.value, ''))

    def multiply(self, other: Text) -> Text:
        return Text(self.value * len(other.value))

    def power(self, other: Text) -> Text:
        return Text(self.value * len(other.value))

    def divide(self, other: Text) -> Text | Void:
        if other.value == '':
            return Void()
        if self.value == '':
            return Text('')
        part = len(self.value) // (len(other.value) + 1)
        return Text(self.value[:max(part, 1)])

    def root(self, other: Text) -> Text:
        return Text(self.value[:len(self.value) // 2])

    def almost(self, other: Text) -> Boolean:
        return Boolean(edit_distance(self.value, other.value) <= 1)

    def xor(self, other: Text) -> Text:
        combined = Text(self.value + other.value)
        return combined.multiply(combined.not_())

    def iterate(self) -> list[Type]:
        return [Text(char) for char in self.value]

    # --- SQL-style operations ---

    def count(self) -> Number:
        return Number(len(self.value))

    def distinct(self) -> Text:
        return self

    def sum(self) -> Type: self.todo("sum")
    def avg(self) -> Type: self.todo("avg")
    def min(self) -> Type: self.todo("min")
    def max(self) -> Type: self.todo("max")
    def join(self, other: Text) -> Type: self.todo("join")


class Boolean(SimpleType):
    rank = 1
    conversion = "boolean"
    default_value = False

    def __init__(self, value: bool) -> None:
        self.value = bool(value)

    def __repr__(self) -> str:
        return SPELLING[self.value]

    def number(self) -> Number:
        return Number(1 if self.value else 0)

    def boolean(self) -> Boolean:
        return self

    def text(self) -> Text:
        return Text(str(self.__repr__()))

    def is_true(self) -> bool:
        return self.value

    def not_(self) -> Boolean:
        return Boolean(not self.value)

    def add(self, other: Boolean) -> Boolean:
        return Boolean(self.value or other.value)

    def multiply(self, other: Boolean) -> Boolean:
        return Boolean(self.value and other.value)

    def xor(self, other: Boolean) -> Boolean:
        return Boolean(self.value != other.value)

    def compare(self, other: Boolean) -> int:
        return compare_raw(self.value, other.value)

    def almost(self, other: Boolean) -> Boolean:
        return Boolean(True)

    def void(self) -> Void:
        return Void()

    def subtract(self, other: Boolean) -> Boolean:
        return Boolean(self.value or other.value)

    def divide(self, other: Boolean) -> Boolean | Void:
        if not other.value:
            return Void()
        return Boolean(self.value and other.value)

    def power(self, other: Boolean) -> Boolean:
        return Boolean(self.value if other.value else True)

    def root(self, other: Boolean) -> Boolean:
        return Boolean(self.value)

    def length(self) -> Number:
        return Number(1)

    def first(self) -> Boolean:
        return self

    def last(self) -> Boolean:
        return self

    def middle(self) -> Boolean:
        return self

    def iterate(self) -> list[Type]:
        return [self]

    # --- SQL-style operations ---

    def count(self) -> Number:
        return Number(1)

    def distinct(self) -> Boolean:
        return self

    def sum(self) -> Type: self.todo("sum")
    def avg(self) -> Type: self.todo("avg")
    def min(self) -> Type: self.todo("min")
    def max(self) -> Type: self.todo("max")
    def join(self, other: Boolean) -> Type: self.todo("join")


class Void(SimpleType):
    """The absence of a value, like Python's None."""

    rank = 0
    conversion = "void"
    default_value = None

    def __repr__(self) -> str:
        return SPELLING[None]

    def number(self) -> Number:
        return Number(0)

    def text(self) -> Text:
        return Text('')

    def boolean(self) -> Boolean:
        return Boolean(False)

    def void(self) -> Void:
        return self

    def compare(self, other: Type) -> int:
        return 0

    def almost(self, other: Type) -> Boolean:
        return Boolean(True)

    def xor(self, other: Type) -> Boolean:
        return Boolean(False)

    def length(self) -> Number:
        return Number(0)

    def add(self, other: Type) -> Void: return Void()
    def subtract(self, other: Type) -> Void: return Void()
    def multiply(self, other: Type) -> Void: return Void()
    def divide(self, other: Type) -> Void: return Void()
    def power(self, other: Type) -> Void: return Void()
    def root(self, other: Type) -> Void: return Void()
    def not_(self) -> Void: return Void()
    def first(self) -> Void: return Void()
    def last(self) -> Void: return Void()
    def middle(self) -> Void: return Void()
    def iterate(self) -> list[Type]: return []
    def count(self) -> Number: return Number(0)
    def distinct(self) -> Void: return Void()
    def sum(self) -> Type: return Void()
    def avg(self) -> Type: return Void()
    def min(self) -> Type: return Void()
    def max(self) -> Type: return Void()

    def join(self, other: Type) -> Type: self.todo("join")