"""Runtime values — what a single value can do.

lynx's rule is that everything works with everything: every operation is defined
for every type, so there are no "unsupported operand" errors — only operations
nobody has written yet. `Type` is the base: `SimpleType` for scalars (Number,
Text, Boolean, Void) and `ComplexType` for values made of other values (Array).
`Type` lists the full interface as abstract methods, so each type is forced to
provide all of them. Fill a stub in by replacing its body with real logic.

Combining two *different* types is `operations.py`'s job: it resolves the pair
before dispatching here, so every method below may assume `other` is its own
type. Each type owes two declarations for that to work — `rank`, its place in
the promotion order, and `conversion`, the name of the method that builds one.
"""

from __future__ import annotations

import inspect
from abc import ABC, abstractmethod

from src.core.grammar import SPELLING
from src.errors.errors import LynxNotImplemented
from src.utils.text import compare_raw, edit_distance


class Type(ABC):
    """Every value lynx works with. Subclassed by SimpleType (Number, Text,
    Boolean, Void) and ComplexType (Array). `rank` and `conversion` let
    operations.py reconcile pairs of different types."""

    rank: int | None = None
    conversion: str | None = None

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        # Abstract scaffolds (SimpleType, ComplexType) need no rank/conversion;
        # only concrete leaf types that can be instantiated must declare them.
        if inspect.isabstract(cls):
            return
        for declaration in ("rank", "conversion"):
            if getattr(cls, declaration, None) is None:
                raise TypeError(f"{cls.__name__} must declare `{declaration}`")

    def type_name(self) -> str:
        return type(self).__name__

    def type_of(self) -> Text:
        return Text(self.type_name())

    def coerce(self, other: Type) -> Type:
        method = getattr(other, self.conversion, None)
        if method is None:
            raise LynxNotImplemented(
                f"cannot coerce {other.type_name()} into {self.type_name()}"
            )
        return method()

    def todo(self, operation: str) -> None:
        raise LynxNotImplemented(f"'{operation}' is not implemented yet for {self.type_name()}")

    # --- comparisons, derived ------------------------------------------

    def equals(self, other: Type) -> Boolean:
        return Boolean(self.compare(other) == 0)

    def greater(self, other: Type) -> Boolean:
        return Boolean(self.compare(other) > 0)

    def less(self, other: Type) -> Boolean:
        return Boolean(self.compare(other) < 0)

    def greater_or_equal(self, other: Type) -> Boolean:
        return Boolean(self.compare(other) >= 0)

    def lesser_or_equal(self, other: Type) -> Boolean:
        return Boolean(self.compare(other) <= 0)

    def greater_or_almost(self, other: Type) -> Boolean:
        return Boolean(self.compare(other) > 0 or self.almost(other).is_true())

    def lesser_or_almost(self, other: Type) -> Boolean:
        return Boolean(self.compare(other) < 0 or self.almost(other).is_true())

    # Every value must define all of these.

    @abstractmethod
    def default_value(self): ...

    @classmethod
    def default(cls):
        if cls is Void:
            return Void()
        return cls(cls.default_value)

    # conversions
    @abstractmethod
    def number(self): ...
    @abstractmethod
    def text(self): ...
    @abstractmethod
    def boolean(self): ...
    @abstractmethod
    def void(self): ...

    # arithmetic
    @abstractmethod
    def add(self, other): ...
    @abstractmethod
    def subtract(self, other): ...
    @abstractmethod
    def multiply(self, other): ...
    @abstractmethod
    def divide(self, other): ...
    @abstractmethod
    def power(self, other): ...
    @abstractmethod
    def not_(self): ...
    @abstractmethod
    def root(self, other): ...
    @abstractmethod
    def xor(self, other): ...

    # ordering
    @abstractmethod
    def compare(self, other): ...
    @abstractmethod
    def almost(self, other): ...

    # sequence access
    @abstractmethod
    def lenght(self): ...
    @abstractmethod
    def first(self): ...
    @abstractmethod
    def last(self): ...
    @abstractmethod
    def middle(self): ...

    # iteration
    @abstractmethod
    def iterate(self) -> list[Type]:
        """The values a for-loop visits for this value: the elements of an
        array, the keys of a map, the characters of text, a numeric count, and
        so on. Never raises — every type is iterable."""


class SimpleType(Type):
    """A value made of a single scalar: Number, Text, Boolean, Void."""


class ComplexType(Type):
    """A value made of other values: Array, Map. Nested types work here."""


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

    def lenght(self) -> Number:
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

    def lenght(self) -> Number:
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

    def lenght(self) -> Number:
        return Number(1)

    def first(self) -> Boolean:
        return self

    def last(self) -> Boolean:
        return self

    def middle(self) -> Boolean:
        return self

    def iterate(self) -> list[Type]:
        return [self]


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
        
    def lenght(self) -> Number: 
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

    # --- not implemented yet ---
    def add(self, other: Array) -> Type: self.todo("add")
    def subtract(self, other: Array) -> Type: self.todo("subtract")
    def multiply(self, other: Array) -> Type: self.todo("multiply")
    def divide(self, other: Array) -> Type: self.todo("divide")
    def power(self, other: Array) -> Type: self.todo("power")
    def root(self, other: Array) -> Type: self.todo("root")
    def xor(self, other: Array) -> Type: self.todo("xor")
    def not_(self) -> Type: self.todo("not_")


def _map_key(value: Type):
    """A hashable, type-qualified representation of a simple value, so `1`
    and `'1'` are distinct keys. Keys are restricted to simple types."""
    if isinstance(value, (Number, Text, Boolean, Void)):
        return (value.type_name(), value.value)
    return (value.type_name(), repr(value))


def _value_from_key(raw: tuple) -> Type:
    """Reverse of `_map_key`: rebuild the key value stored in a map."""
    kind, value = raw
    if kind == "Number":
        return Number(value)
    if kind == "Text":
        return Text(value)
    if kind == "Boolean":
        return Boolean(value)
    return Void()


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
        self.value[_map_key(key)] = value

    def get_item(self, key: Type):
        return self.value[_map_key(key)]

    def __repr__(self) -> str:
        if not self.value:
            return "{}"
        parts = []
        for raw, value in self.value.items():
            parts.append(f"{raw[1]}: {value}")
        return "{ " + "; ".join(parts) + " }"

    def type_name(self) -> str:
        return "Map"

    def lenght(self) -> Number:
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
        return [_value_from_key(raw) for raw in self.value.keys()]

    def iterate(self) -> list[Type]:
        return self.keys()

    # --- not implemented yet ---
    def add(self, other: Map) -> Type: self.todo("add")
    def subtract(self, other: Map) -> Type: self.todo("subtract")
    def multiply(self, other: Map) -> Type: self.todo("multiply")
    def divide(self, other: Map) -> Type: self.todo("divide")
    def power(self, other: Map) -> Type: self.todo("power")
    def root(self, other: Map) -> Type: self.todo("root")
    def xor(self, other: Map) -> Type: self.todo("xor")
    def not_(self) -> Type: self.todo("not_")