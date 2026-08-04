"""Runtime values.

lynx's rule is that everything works with everything: every operation is defined
for every type, so there are no "unsupported operand" errors — only operations
nobody has written yet. `Value` lists the full interface as abstract methods, so
each type is forced to provide all of them. Fill a stub in by replacing its body
with real logic.
"""

from abc import ABC, abstractmethod

from src.grammar import SPELLING
from src.errors import LynxNotImplemented


class Value(ABC):
    def type_name(self):
        return type(self).__name__

    def todo(self, operation):
        raise LynxNotImplemented(f"'{operation}' is not implemented yet for {self.type_name()}")

    # Every value must define all of these. Stubs in each type call self.todo(...).

    # conversions
    @abstractmethod
    def default_value(self): ...
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
    def root(self, other): ...

    # comparisons
    @abstractmethod
    def equals(self, other): ...
    @abstractmethod
    def almost(self, other): ...
    @abstractmethod
    def greater(self, other): ...
    @abstractmethod
    def less(self, other): ...
    @abstractmethod
    def greater_or_equal(self, other): ...
    @abstractmethod
    def lesser_or_equal(self, other): ...
    @abstractmethod
    def greater_or_almost(self, other): ...
    @abstractmethod
    def lesser_or_almost(self, other): ...
    @abstractmethod
    def xor(self, other): ...

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
        return Number(self.value / other.value)

    def greater(self, other):
        return Boolean(self.value > other.value)

    def less(self, other):
        return Boolean(self.value < other.value)

    def equals(self, other):
        return Boolean(self.value == other.value)

    def default_value(self): 
        return 0
    
    def number(self):
        return self

    def text(self): 
        return Text(str(self.value))

    def void(self): 
        return Void()

    def almost(self, other): 
        return Boolean(abs(self.value - other.value) < 1)

    def lenght(self): 
        return Number(len(str(self.value).replace('.', '').replace('-', '')))
        #return Number(len(str(self.value)))

    # --- not implemented yet ---
    
    def power(self, other): self.todo("power")
    def root(self, other): self.todo("root")
    def greater_or_equal(self, other): self.todo("greater_or_equal")
    def lesser_or_equal(self, other): self.todo("lesser_or_equal")
    def greater_or_almost(self, other): self.todo("greater_or_almost")
    def lesser_or_almost(self, other): self.todo("lesser_or_almost")
    def xor(self, other): self.todo("xor")
    def first(self): self.todo("first")
    def last(self): self.todo("last")
    def middle(self): self.todo("middle")


class Text(Value):
    def __init__(self, value):
        self.value = value

    def __repr__(self):
        return str(self.value)

    def add(self, other):
        return Text(self.value + other.value)

    def equals(self, other):
        return Boolean(self.value == other.value)

    def default_value(self):
        return ''

    def text(self):
        return self

    def void(self): 
        return Void()
    

    # --- not implemented yet ---
    
    def number(self): self.todo("number")
    def boolean(self): self.todo("boolean")
    def subtract(self, other): self.todo("subtract")
    def multiply(self, other): self.todo("multiply")
    def divide(self, other): self.todo("divide")
    def power(self, other): self.todo("power")
    def root(self, other): self.todo("root")
    def almost(self, other): self.todo("almost")
    def greater(self, other): self.todo("greater")
    def less(self, other): self.todo("less")
    def greater_or_equal(self, other): self.todo("greater_or_equal")
    def lesser_or_equal(self, other): self.todo("lesser_or_equal")
    def greater_or_almost(self, other): self.todo("greater_or_almost")
    def lesser_or_almost(self, other): self.todo("lesser_or_almost")
    def xor(self, other): self.todo("xor")
    def lenght(self): self.todo("lenght")
    def first(self): self.todo("first")
    def last(self): self.todo("last")
    def middle(self): self.todo("middle")


class Boolean(Value):
    def __init__(self, value):
        self.value = bool(value)

    def __repr__(self):
        return SPELLING[self.value]

    def default_value(self):
        return False

    def boolean(self):
        return self

    def text(self):
        return Text(str(self.__repr__()))
    
    def is_true(self):
        return self.value

    def add(self, other):
        return Boolean(self.value or other.value)

    def multiply(self, other):
        return Boolean(self.value and other.value)

    def xor(self, other):
        return Boolean(self.value != other.value)

    def equals(self, other):
        return Boolean(self.value == other.value)

    def almost(self, other):
        return Boolean(True)

    # --- not implemented yet ---
    
    def number(self): self.todo("number")
    
    def void(self): self.todo("void")
    def subtract(self, other): self.todo("subtract")
    def divide(self, other): self.todo("divide")
    def power(self, other): self.todo("power")
    def root(self, other): self.todo("root")
    
    def greater(self, other): self.todo("greater")
    def less(self, other): self.todo("less")
    def greater_or_equal(self, other): self.todo("greater_or_equal")
    def lesser_or_equal(self, other): self.todo("lesser_or_equal")
    def greater_or_almost(self, other): self.todo("greater_or_almost")
    def lesser_or_almost(self, other): self.todo("lesser_or_almost")
    def lenght(self): self.todo("lenght")
    def first(self): self.todo("first")
    def last(self): self.todo("last")
    def middle(self): self.todo("middle")


class Void(Value):
    """The absence of a value, like Python's None. Everything about how it
    behaves is up to the stubs below."""

    def __repr__(self):
        return SPELLING[None]

    # --- not implemented yet ---
    def number(self):
        return Number(0)
    def text(self):
        return Text('')
    def boolean(self): 
        return Boolean(False)
    def void(self):
        return self
    def default_value(self):
        return None
    def add(self, other): self.todo("add")
    def subtract(self, other): self.todo("subtract")
    def multiply(self, other): self.todo("multiply")
    def divide(self, other): self.todo("divide")
    def power(self, other): self.todo("power")
    def root(self, other): self.todo("root")
    def equals(self, other): self.todo("equals")
    def almost(self, other): self.todo("almost")
    def greater(self, other): self.todo("greater")
    def less(self, other): self.todo("less")
    def greater_or_equal(self, other): self.todo("greater_or_equal")
    def lesser_or_equal(self, other): self.todo("lesser_or_equal")
    def greater_or_almost(self, other): self.todo("greater_or_almost")
    def lesser_or_almost(self, other): self.todo("lesser_or_almost")
    def xor(self, other): self.todo("xor")
    def lenght(self): self.todo("lenght")
    def first(self): self.todo("first")
    def last(self): self.todo("last")
    def middle(self): self.todo("middle")
