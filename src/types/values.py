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

from abc import ABC, abstractmethod

from src.errors.errors import LynxNotImplemented
from src.grammar import SPELLING


def compare_raw(a, b):
    """-1, 0 or 1 — the shape every type's `compare` returns."""
    if a == b:
        return 0
    return 1 if a > b else -1


def edit_distance(a, b):
    """Levenshtein distance between two strings."""
    if a == b:
        return 0
    previous = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        current = [i]
        row_min = i
        for j, cb in enumerate(b, 1):
            cost = 0 if ca == cb else 1
            current.append(min(current[-1] + 1, previous[j] + 1, previous[j - 1] + cost))
            if current[-1] < row_min:
                row_min = current[-1]
        if row_min > 1:
            return row_min
        previous = current
    return previous[-1]


class Value(ABC):
    # Declared by every type. `rank` is its place in the promotion order used
    # for comparisons (higher wins); `conversion` names the method that turns
    # any other value into this type. __init_subclass__ refuses a type missing
    # either one, the same way the ABC refuses a type missing an operation.
    rank = None
    conversion = None

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        for declaration in ("rank", "conversion"):
            if getattr(cls, declaration, None) is None:
                raise TypeError(f"{cls.__name__} must declare `{declaration}`")

    def type_name(self):
        return type(self).__name__

    def type_of(self):
        # `type`. Concrete like type_name(): every value already knows its own
        # type, so there is nothing here for a type to stub out.
        return Text(self.type_name())

    def coerce(self, other):
        # `other` as a value of self's type, built with the conversion method
        # every type already provides.
        return getattr(other, self.conversion)()

    def todo(self, operation):
        raise LynxNotImplemented(f"'{operation}' is not implemented yet for {self.type_name()}")

    # --- comparisons, derived ------------------------------------------
    # All seven follow from `compare` and `almost`, so a type never restates
    # its own ordering and orientation is written once, here: `less` is just
    # `greater` read the other way round.

    def equals(self, other):
        # `=` never crosses types — operations.py answers false before we get
        # here — so reaching this method means the two types already match.
        return Boolean(self.compare(other) == 0)

    def greater(self, other):
        return Boolean(self.compare(other) > 0)

    def less(self, other):
        return Boolean(self.compare(other) < 0)

    def greater_or_equal(self, other):
        return Boolean(self.compare(other) >= 0)

    def lesser_or_equal(self, other):
        return Boolean(self.compare(other) <= 0)

    def greater_or_almost(self, other):
        return Boolean(self.compare(other) > 0 or self.almost(other).is_true())

    def lesser_or_almost(self, other):
        return Boolean(self.compare(other) < 0 or self.almost(other).is_true())

    # Every value must define all of these. Stubs in each type call self.todo(...).

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

    # ordering: the two primitives the seven comparisons above are built from
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

    def __init__(self, value):
        self.value = float(value)
        if self.value % 1 == 0:
            self.value = int(self.value)

    def __repr__(self):
        return str(self.value)

    def boolean(self):
        return Boolean(self.value > 0)

    def add(self, other):
        return Number(self.value + other.value)

    def subtract(self, other):
        return Number(self.value - other.value)

    def multiply(self, other):
        return Number(self.value * other.value)

    def divide(self, other):
        if other.value == 0:
            return Void()
        return Number(self.value / other.value)

    def compare(self, other):
        return compare_raw(self.value, other.value)

    def number(self):
        return self

    def text(self):
        return Text(str(self.value))

    def void(self):
        return Void()

    def not_(self):
        return Number(1 - self.value)

    def almost(self, other):
        return Boolean(abs(self.value - other.value) < 1)

    def lenght(self):
        return Number(len(str(self.value).replace('.', '').replace('-', '')))

    def first(self): 
        return Number(str(self.value).replace('.', '').replace('-', '')[0])
    
    def last(self):
        return Number(str(self.value)[-1])

    def middle(self):
        digits = str(self.value).replace('.', '').replace('-', '')
        return Number(digits[len(digits) // 2])

    def power(self, other):
        return Number(self.value ** other.value)

    def root(self, other):
        if other.value == 0:
            return Void()
        return Number(self.value ** (1 / other.value))

    def xor(self, other):
        s = self.value + other.value
        return Number(s * (1 - s))


class Text(Value):
    rank = 2
    conversion = "text"
    default_value = ''

    def __init__(self, value):
        self.value = value

    def __repr__(self):
        return str(self.value)

    def add(self, other):
        return Text(self.value + other.value)

    def compare(self, other):
        # Lexicographic, so 'apple' < 'banana'.
        return compare_raw(self.value, other.value)

    def number(self):
        # The number the text spells, or — when it spells none — how long it is.
        try:
            return Number(self.value)
        except ValueError:
            return Number(len(self.value))

    def text(self):
        return self

    def void(self):
        return Void()
    
    def lenght(self): 
        return Number(len(self.value))
    
    def first(self):
        if len(self.value) > 0:
            return Text(self.value[0])
        return Text('')
    
    def last(self): 
        if len(self.value) > 0:
            return Text(self.value[-1])
        return Text('')

    def middle(self):
        if len(self.value) == 0:
            return Text('')
        return Text(self.value[len(self.value) // 2])

    def boolean(self):
        return Boolean(self.value != '')

    def not_(self):
        return Text(str(1 - self.number().value))

    def subtract(self, other):
        return Text(self.value.replace(other.value, ''))

    def multiply(self, other):
        return Text(self.value * len(other.value))

    def power(self, other):
        return Text(self.value * len(other.value))

    def divide(self, other):
        if other.value == '':
            return Void()
        if self.value == '':
            return Text('')
        part = len(self.value) // (len(other.value) + 1)
        return Text(self.value[:max(part, 1)])

    def root(self, other):
        return Text(self.value[:len(self.value) // 2])

    def almost(self, other):
        return Boolean(edit_distance(self.value, other.value) <= 1)

    def xor(self, other):
        combined = Text(self.value + other.value)
        return combined.multiply(combined.not_())


class Boolean(Value):
    rank = 1
    conversion = "boolean"
    default_value = False

    def __init__(self, value):
        self.value = bool(value)

    def __repr__(self):
        return SPELLING[self.value]

    def number(self):
        return Number(1 if self.value else 0)

    def boolean(self):
        return self

    def text(self):
        return Text(str(self.__repr__()))

    def is_true(self):
        return self.value

    def not_(self):
        return Boolean(not self.value)

    def add(self, other):
        return Boolean(self.value or other.value)

    def multiply(self, other):
        return Boolean(self.value and other.value)

    def xor(self, other):
        return Boolean(self.value != other.value)

    def compare(self, other):
        return compare_raw(self.value, other.value)

    def almost(self, other):
        return Boolean(True)

    # --- not implemented yet ---

    def void(self): 
        return Void()
    
    def subtract(self, other): 
        return Boolean(self.value or other.value)
    
    def divide(self, other):
        if not other.value:
            return Void()
        return Boolean(self.value and other.value)
    
    def power(self, other): 
        return Boolean(self.value if other.value else True)
    
    def root(self, other): 
        return Boolean(self.value)
    
    def lenght(self): 
        return Number(1)
    
    def first(self): 
        return self
    
    def last(self): 
        return self
    
    def middle(self): 
        return self


class Void(Value):
    """The absence of a value, like Python's None. Everything about how it
    behaves is up to the stubs below."""

    rank = 0
    conversion = "void"
    default_value = None

    def __repr__(self):
        return SPELLING[None]

    def number(self):
        return Number(0)
    def text(self):
        return Text('')
    def boolean(self):
        return Boolean(False)
    def void(self):
        return self

    def compare(self, other):
        # There is only one void, so any two are the same.
        return 0

    def add(self, other): return Void()
    def subtract(self, other): return Void()
    def multiply(self, other): return Void()
    def divide(self, other): return Void()
    def power(self, other): return Void()
    def root(self, other): return Void()
    def almost(self, other): return Boolean(True)
    def xor(self, other): return Boolean(False)
    def not_(self): return Void()
    def first(self): return Void()
    def last(self): return Void()
    def middle(self): return Void()
    def lenght(self): return Number(0)
