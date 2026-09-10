"""What two values do together.

`values.py` says what one value can do; this module resolves a *pair* of values
down to a single type and then lets `values.py` do that. Three layers are tried
in order, for any pair of types, present or future:

1. **same type** — call the type's own method, exactly as before.
2. **registered pair** — a `@mixed` handler written for this combination.
3. **policy fallback** — the operator's own rule for reconciling two types.

Layer 3 is what makes "everything works with everything" a property rather than
a hope: `@abstractmethod`s force every *type* to define every operation, but the
behaviour space is every *pair* of types, and nothing can force that to be
filled in by hand. The fallback means an unwritten pair still resolves, so a new
type can never reintroduce a raw Python error.

Because layers 2 and 3 both settle the pair before dispatching, every method in
`values.py` may assume `other` is its own type.
"""

from collections.abc import Callable
from typing import Any

from src.errors.errors import LynxNotImplemented
from src.runtime import values

# How an operator reconciles two different types when no `@mixed` handler
# claims the pair.
LEFT = "left"      # coerce the right operand into the left's type
RANK = "rank"      # promote both operands to the higher-ranked type
STRICT = "strict"  # different types simply never match
PASSTHROUGH = "passthrough"  # call left.method(right) with no coercion

# Operator -> its rule, named by the Value method so no operator symbol appears
# outside grammar.py. LEFT is the default, so only the exceptions are listed.
#
# Comparisons must use RANK: under LEFT, `'hi' > 3` compares 'hi' with '3' (true)
# while `3 < 'hi'` compares 3 with number 'hi' (false), so 'hi' would be both
# greater than and not greater than 3. Promoting by rank ignores position, which
# keeps `a.compare(b) == -b.compare(a)` true whatever the types.
POLICY = {
    "equals": STRICT,
    "almost": RANK,
    "greater": RANK,
    "less": RANK,
    "greater_or_equal": RANK,
    "lesser_or_equal": RANK,
    "greater_or_almost": RANK,
    "lesser_or_almost": RANK,
    "in_": PASSTHROUGH,
}

# (left type, right type, method) -> handler(left, right)
MIXED: dict[tuple[type, type, str], Callable[..., values.Type]] = {}


def mixed(first: type, second: type, method: str, commutes: bool = False) -> Callable:
    """Register the meaning of one operation on one pair of types.

    The handler's parameters are named by type and read in source order, so it
    never has to ask which side it was called from. `commutes=True` registers
    the mirrored pair with the arguments swapped back into that order, which is
    why `'hi' * 2` and `2 * 'hi'` can share a single handler. An operation whose
    two directions differ — `'hi' + 2` is 'hi2', `2 + 'hi'` is '2hi' — is two
    registrations instead, each read left to right.
    """
    def register(handler: Callable) -> Callable:
        MIXED[(first, second, method)] = handler
        if commutes:
            MIXED[(second, first, method)] = lambda left, right: handler(right, left)
        return handler
    return register


def binary(method: str, left: values.Type, right: values.Type) -> values.Type:
    if type(left) is type(right):
        return getattr(left, method)(right)

    handler = MIXED.get((type(left), type(right), method))
    if handler is not None:
        # Written for this pair, so any hole inside it is its own business:
        # let its error through untouched.
        return handler(left, right)

    policy = POLICY.get(method, LEFT)
    if policy is STRICT:
        return values.Boolean(False)
    if policy is PASSTHROUGH:
        # The type decides what "in" means for this pair itself; no coercing
        # the container into the element's type first.
        return getattr(left, method)(right)

    # Nobody wrote this pair, so reconcile it and borrow the same-type logic.
    # A hole we land in that way belongs to the *pair* the user wrote, not to
    # whichever type we happened to coerce towards, so it is reported as such:
    # `'hi' * true` is a missing Text-and-Boolean rule, not a missing Text one.
    try:
        if policy is RANK and right.rank > left.rank:
            # Promote the left operand instead, so position can't change the answer.
            return getattr(right.coerce(left), method)(right)
        return getattr(left, method)(left.coerce(right))
    except LynxNotImplemented as error:
        raise LynxNotImplemented(
            f"'{method}' is not implemented yet between "
            f"{left.type_name()} and {right.type_name()}"
        ) from error


# --- pair meanings --------------------------------------------------------


@mixed(values.Text, values.Number, "multiply", commutes=True)
def repeat_multiply_text_number(text: values.Text, number: values.Number) -> values.Text:
    # A fractional count adds a proportional slice of the text, so 0.5 always
    # appends half of it. Negative counts repeat the text unsigned and then
    # reverse the whole result.
    magnitude = abs(number.value)
    whole = int(magnitude)
    fraction = magnitude - whole
    result = text.value * whole
    if fraction > 0:
        result += text.value[:int(fraction * len(text.value))]
    if number.value < 0:
        result = result[::-1]
    return values.Text(result)

@mixed(values.Boolean, values.Number, "multiply", commutes=True)
def repeat_multiply_boolean_number(bool: values.Boolean, number: values.Number) -> values.Number:
    return values.Number(bool.number().value * int(number.value))

@mixed(values.Void, values.Number, "multiply", commutes=True)
def repeat_multiply_void_number(void: values.Void, number: values.Number) -> values.Void:
    return values.Number.default()

@mixed(values.Void, values.Text, "multiply", commutes=True)
def repeat_multiply_void_text(void: values.Void, text: values.Text) -> values.Text:
    return values.Text.default()

@mixed(values.Void, values.Boolean, "multiply", commutes=True)
def repeat_multiply_void_boolean(void: values.Void, bool: values.Boolean) -> values.Boolean:
    return values.Boolean.default()