"""Binary and unary operator dispatch.

Every value defines every operation and operations.binary reconciles any pair
of types, so these two never decide what two types mean together — they only
route the operator (named by its grammar table) to the value layer and pin any
error to its line.
"""

from src.core.grammar import BINARY_METHOD, UNARY_METHOD
from src.errors.errors import LynxError, LynxNotImplemented
from src.runtime import operations, values


def apply_binary(operator: str, left: values.Type, right: values.Type, line: int | None) -> values.Type:
    # Every value defines every operation and operations.binary reconciles any
    # pair of types, so this always resolves; a stub that hasn't been filled in
    # raises LynxNotImplemented, which we locate to `line`.
    try:
        return operations.binary(BINARY_METHOD[operator], left, right)
    except LynxError as error:
        if error.line is None:
            error.line = line
        raise


def apply_unary(operator: str, value: values.Type, line: int | None) -> values.Type:
    # Same contract as apply_binary: every value defines every operation, so a
    # stub that hasn't been filled in raises LynxNotImplemented, which we locate
    # to `line`.
    try:
        return getattr(value, UNARY_METHOD[operator])()
    except LynxNotImplemented as error:
        if error.line is None:
            error.line = line
        raise