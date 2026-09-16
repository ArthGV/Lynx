"""The base of every lynx value.

`Type` lists the full interface as abstract methods, so each concrete type
(`simple_type.py`, `array.py`, `map.py`, `table.py`) is forced to provide all
of them. `SimpleType` and `ComplexType` are the two families below it; the
four scalars live with SimpleType in `simple_type.py`.

The derived helpers (`equals`, `default`, `sqrt`, ...) build concrete
Boolean/Number/Void instances, which live in `simple_type.py`. They are
imported lazily inside the method bodies — the same pattern `Table.rows_where`
already uses — because the concrete types subclass `Type`, so a module-level
import here would close an import cycle.
"""

from __future__ import annotations

import inspect
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, ClassVar, NoReturn, cast

from src.errors.errors import LynxNotImplemented

if TYPE_CHECKING:
    from src.types.simple_type import Boolean, Number, Text, Void


class Type(ABC):
    """Every value lynx works with. Subclassed by SimpleType (Number, Text,
    Boolean, Void) and ComplexType (Array). `rank` and `conversion` let
    operations.py reconcile pairs of different types."""

    rank: ClassVar[int | None] = None
    conversion: ClassVar[str | None] = None
    default_value: ClassVar[Any]

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        # Abstract scaffolds (SimpleType, ComplexType) need no rank/conversion;
        # only concrete leaf types that can be instantiated must declare them.
        if inspect.isabstract(cls):
            return
        for declaration in ("rank", "conversion"):
            if getattr(cls, declaration, None) is None:
                raise TypeError(f"{cls.__name__} must declare `{declaration}`")
        if not hasattr(cls, "default_value"):
            raise TypeError(f"{cls.__name__} must declare `default_value`")

    def type_name(self) -> str:
        return type(self).__name__

    def type_of(self) -> Text:
        from src.types.simple_type import Text

        return Text(self.type_name())

    def coerce(self, other: Type) -> Type:
        if self.conversion is None:
            raise LynxNotImplemented(f"cannot coerce {other.type_name()} into {self.type_name()}")
        method = getattr(other, self.conversion, None)
        if method is None:
            raise LynxNotImplemented(f"cannot coerce {other.type_name()} into {self.type_name()}")
        return cast(Type, method())

    def todo(self, operation: str) -> NoReturn:
        raise LynxNotImplemented(f"'{operation}' is not implemented yet for {self.type_name()}")

    # --- comparisons, derived ------------------------------------------

    def equals(self, other: Any) -> Boolean:
        from src.types.simple_type import Boolean

        return Boolean(self.compare(other) == 0)

    def greater(self, other: Any) -> Boolean:
        from src.types.simple_type import Boolean

        return Boolean(self.compare(other) > 0)

    def less(self, other: Any) -> Boolean:
        from src.types.simple_type import Boolean

        return Boolean(self.compare(other) < 0)

    def greater_or_equal(self, other: Any) -> Boolean:
        from src.types.simple_type import Boolean

        return Boolean(self.compare(other) >= 0)

    def lesser_or_equal(self, other: Any) -> Boolean:
        from src.types.simple_type import Boolean

        return Boolean(self.compare(other) <= 0)

    def greater_or_almost(self, other: Any) -> Boolean:
        from src.types.simple_type import Boolean

        return Boolean(self.compare(other) > 0 or self.almost(other).is_true())

    def lesser_or_almost(self, other: Any) -> Boolean:
        from src.types.simple_type import Boolean

        return Boolean(self.compare(other) < 0 or self.almost(other).is_true())

    def in_(self, other: Any) -> Boolean:
        """True when this value appears among `other`'s iterated elements —
        an element of an array, a key of a map, and so on."""
        from src.types.simple_type import Boolean

        for item in other.iterate():
            if type(item) is type(self) and self.equals(item).is_true():
                return Boolean(True)
        return Boolean(False)

    # Every value must define all of these.

    @classmethod
    def default(cls) -> Type:
        from src.types.simple_type import Void

        if cls is Void:
            return Void()
        return cls(cls.default_value)  # type: ignore[call-arg]

    # conversions
    @abstractmethod
    def number(self) -> Number: ...
    @abstractmethod
    def text(self) -> Text: ...
    @abstractmethod
    def boolean(self) -> Boolean: ...
    @abstractmethod
    def void(self) -> Void: ...

    # arithmetic
    @abstractmethod
    def add(self, other: Any) -> Type: ...
    @abstractmethod
    def subtract(self, other: Any) -> Type: ...
    @abstractmethod
    def multiply(self, other: Any) -> Type: ...
    @abstractmethod
    def divide(self, other: Any) -> Type: ...
    @abstractmethod
    def power(self, other: Any) -> Type: ...
    @abstractmethod
    def not_(self) -> Type: ...
    @abstractmethod
    def root(self, other: Any) -> Type: ...
    @abstractmethod
    def xor(self, other: Any) -> Type: ...

    # ordering
    @abstractmethod
    def compare(self, other: Any) -> int: ...
    @abstractmethod
    def almost(self, other: Any) -> Boolean: ...

    # sequence access
    @abstractmethod
    def length(self) -> Type: ...
    @abstractmethod
    def first(self) -> Type: ...
    @abstractmethod
    def last(self) -> Type: ...
    @abstractmethod
    def middle(self) -> Type: ...

    # iteration
    @abstractmethod
    def iterate(self) -> list[Type]:
        """The values a for-loop visits for this value: the elements of an
        array, the keys of a map, the characters of text, a numeric count, and
        so on. Never raises — every type is iterable."""

    # --- table SQL-style operations ---
    # Abstract like every other operation: each type implements the ones that
    # mean something for it and leaves a `todo` stub for the rest — `count` is
    # 1 on a scalar, and `sum` on a Text asks to be written rather than
    # silently returning void.

    @abstractmethod
    def sum(self) -> Type: ...
    @abstractmethod
    def avg(self) -> Type: ...
    @abstractmethod
    def min(self) -> Type: ...
    @abstractmethod
    def max(self) -> Type: ...
    @abstractmethod
    def count(self) -> Number: ...
    @abstractmethod
    def distinct(self) -> Type: ...
    @abstractmethod
    def join(self, other: Any) -> Type: ...

    # --- convenience (concrete, not abstract) ---

    def sqrt(self) -> Type:
        from src.types.simple_type import Number

        return self.root(Number(2))

    def last_index(self) -> Type:
        from src.types.array import Array
        from src.types.simple_type import Number

        length = self.length()
        if isinstance(length, Array):
            return Array([Number(cast(Number, item).value - 1) for item in length.value])
        return Number(cast(Number, length).value - 1)

    def not_equal(self, other: Any) -> Boolean:
        return self.equals(other).not_()


class ComplexType(Type):
    """A value made of other values: Array, Map. Nested types work here."""
