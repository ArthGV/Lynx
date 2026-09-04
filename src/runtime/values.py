"""Runtime values — what a single value can do.

lynx's rule is that everything works with everything: every operation is defined
for every type, so there are no "unsupported operand" errors — only operations
nobody has written yet. `Value` lists the full interface as abstract methods, so
each type is forced to provide all of them. Fill a stub in by replacing its body
with real logic.

Combining two *different* types is `operations.py`'s job: it resolves the pair
before dispatching here, so every method below may assume `other` is its own
type. Each type owes two declarations for that to work — `rank`, its place in
the promotion order, and `conversion`, the name of the method that builds one.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from src.core.grammar import SPELLING
from src.errors.errors import LynxNotImplemented
from src.utils.text import compare_raw, edit_distance


class Value(ABC):
    rank: int | None = None
    conversion: str | None = None

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        for declaration in ("rank", "conversion"):
            if getattr(cls, declaration, None) is None:
                raise TypeError(f"{cls.__name__} must declare `{declaration}`")

    def type_name(self) -> str:
        return type(self).__name__

    def type_of(self) -> Text:
        return Text(self.type_name())

    def coerce(self, other: Value) -> Value:
        return getattr(other, self.conversion)()

    def todo(self, operation: str) -> None:
        raise LynxNotImplemented(f"'{operation}' is not implemented yet for {self.type_name()}")

    # --- comparisons, derived ------------------------------------------

    def equals(self, other: Value) -> Boolean:
        return Boolean(self.compare(other) == 0)

    def greater(self, other: Value) -> Boolean:
        return Boolean(self.compare(other) > 0)

    def less(self, other: Value) -> Boolean:
        return Boolean(self.compare(other) < 0)

    def greater_or_equal(self, other: Value) -> Boolean:
        return Boolean(self.compare(other) >= 0)

    def lesser_or_equal(self, other: Value) -> Boolean:
        return Boolean(self.compare(other) <= 0)

    def greater_or_almost(self, other: Value) -> Boolean:
        return Boolean(self.compare(other) > 0 or self.almost(other).is_true())

    def lesser_or_almost(self, other: Value) -> Boolean:
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


class Number(Value):
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


class Text(Value):
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


class Boolean(Value):
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


class Void(Value):
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

    def compare(self, other: Value) -> int:
        return 0

    def almost(self, other: Value) -> Boolean: 
            return Boolean(True)
    def xor(self, other: Value) -> Boolean: 
            return Boolean(False)
        
    def lenght(self) -> Number: 
            return Number(0)

    def add(self, other: Value) -> Void: return Void()
    def subtract(self, other: Value) -> Void: return Void()
    def multiply(self, other: Value) -> Void: return Void()
    def divide(self, other: Value) -> Void: return Void()
    def power(self, other: Value) -> Void: return Void()
    def root(self, other: Value) -> Void: return Void()
    def not_(self) -> Void: return Void()
    def first(self) -> Void: return Void()
    def last(self) -> Void: return Void()
    def middle(self) -> Void: return Void()

    