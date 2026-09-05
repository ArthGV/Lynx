"""Walk the AST and run it.

`execute` handles statements (side effects); `evaluate` handles expressions
(returns a Value). Binary operators are dispatched through grammar tables and
their operands reconciled by operations.py, so the interpreter never mentions an
operator character and never decides what two types mean together.
"""

from typing import Any

from src.core.grammar import BINARY_METHOD, UNARY_METHOD
from src.core.nodes import (
    ArrayLiteral,
    Assignment,
    BinaryExpression,
    Boolean,
    Call,
    Function,
    Identifier,
    If,
    MapLiteral,
    Number,
    Print,
    Program,
    Return,
    SetItem,
    Text,
    UnaryExpression,
    Void,
)
from src.errors.errors import (
    LynxError,
    LynxInputError,
    LynxNameError,
    LynxNotImplemented,
    LynxTypeError,
)
from src.runtime import operations
from src.runtime import values
from src.runtime.environment import Environment
from src.runtime.functions import FunctionValue, _Return


def execute(node: Any, env: Environment) -> None:
    if isinstance(node, list):
        for statement in node:
            execute(statement, env)
        return

    match node:
        case Program(statements):
            execute(statements, env)

        case Print(value):
            print(evaluate(value, env))

        case Assignment(name, value):
            env.set(name, evaluate(value, env))

        case SetItem(base, steps, value, line):
            assign_item(base, steps, value, line, env)

        case Function(name, params, body):
            env.set(name, FunctionValue(params, body, env))

        case Call(callee, args, line):
            call(callee, args, line, env)

        case Return(value, line):
            raise _Return(evaluate(value, env))

        case If(branches, else_body):
            for branch in branches:
                if evaluate(branch.condition, env).boolean().is_true():
                    execute(branch.body, env)
                    return
            if else_body is not None:
                execute(else_body, env)

        case _:
            raise LynxTypeError(f"cannot execute {type(node).__name__}")



def evaluate(node: Any, env: Environment) -> values.Type:
    match node:
        case Number(value):
            return values.Number(value)

        case Text(value):
            return values.Text(value)

        case Boolean(value):
            return values.Boolean(value)

        case Void():
            return values.Void()

        case ArrayLiteral(items, line):
            return values.Array([evaluate(item, env) for item in items])

        case MapLiteral(pairs, line):
            return values.Map([
                (evaluate_key(k, env, line), evaluate(v, env))
                for k, v in pairs
            ])

        case Identifier(name, line):
            return env.get(name, line)

        case Call(callee, args, line):
            return call(callee, args, line, env)

        case UnaryExpression(operator, operand, line):
            return apply_unary(operator, evaluate(operand, env), line)

        case BinaryExpression(left, operator, right, line):
            return apply_binary(operator, evaluate(left, env), evaluate(right, env), line)

        case _:
            raise LynxTypeError(f"cannot evaluate {type(node).__name__}")


def evaluate_key(node: Any, env: Environment, line: int | None) -> values.Type:
    key = evaluate(node, env)
    if not isinstance(key, values.SimpleType):
        raise LynxTypeError(
            f"map key must be a simple type, got {key.type_name()}", line
        )
    return key


def call(callee: Any, args: list[Any], line: int | None, env: Environment) -> values.Type:
    # `callee` is either a name (a plain function/index call) or an expression
    # (the result of an earlier chained call), so resolve it to a value first.
    if isinstance(callee, str):
        fn = env.get(callee, line)
    else:
        fn = evaluate(callee, env)

    if isinstance(fn, values.Array):
        return index_array(fn, args, line, env)

    if isinstance(fn, values.Map):
        return index_map(fn, args, line, env)

    if not isinstance(fn, FunctionValue):
        raise LynxTypeError(f"'{callee}' is not a function", line)
    if len(args) != len(fn.params):
        raise LynxInputError(
            f"{callee} expected {len(fn.params)} input but got {len(args)}", line
        )
    scope = fn.env.child()
    for param, arg in zip(fn.params, args):
        scope.set(param, evaluate(arg, env))
    try:
        execute(fn.body, scope)
    except _Return as returned:
        return returned.value
    return values.Void()


def index_array(array: values.Array, args: list[Any], line: int | None, env: Environment) -> values.Type:
    # `,` groups several indices into one access step: `a 1, 0` lowers through
    # each nesting level in order. Indices are 0-based. A range step (`a 3__7`)
    # is a slice of that level instead of a single element.
    current = array
    for arg in args:
        if is_range(arg):
            current = slice_array(current, arg, line, env)
        else:
            current = get_element(current, arg, line, env)
    return current


def index_map(map_value: values.Map, args: list[Any], line: int | None, env: Environment) -> values.Type:
    # Each arg is one key lookup; a run of args descends through nested maps.
    current = map_value
    for arg in args:
        if is_range(arg):
            raise LynxError("range slicing is only supported for arrays", line)
        current = get_element(current, arg, line, env)
    return current


def get_element(container, step: Any, line: int | None, env: Environment) -> values.Type:
    """Fetch one index/key lookup into `container`. Shared by read access and
    mutation so both validate and report the same way."""
    key = evaluate(step, env)
    if isinstance(container, values.Array):
        if not isinstance(key, values.Number):
            raise LynxTypeError(
                f"array index must be a number, got {key.type_name()}", line
            )
        idx = key.value
        if not isinstance(idx, int) or idx < 0 or idx >= len(container.value):
            raise LynxError(
                f"index {idx} out of range for an array of length {len(container.value)}", line
            )
        return container.value[idx]
    if isinstance(container, values.Map):
        if not isinstance(key, values.SimpleType):
            raise LynxTypeError(
                f"map key must be a simple type, got {key.type_name()}", line
            )
        try:
            return container.get_item(key)
        except KeyError:
            raise LynxError(f"key {key!r} not found in map", line)
    raise LynxTypeError("cannot index into a value that is not an array or map", line)


def assign_item(base: str, steps: list[Any], value_node: Any, line: int | None, env: Environment) -> None:
    # `a 1, 0: 5` — walk the deref path to the innermost container, then set.
    container = env.get(base, line)
    for step in steps[:-1]:
        if is_range(step):
            raise LynxError("range slicing is only supported for the last index", line)
        container = get_element(container, step, line, env)
    if is_range(steps[-1]):
        slice_assign(container, steps[-1], value_node, line, env)
        return
    key = evaluate(steps[-1], env)
    new_value = evaluate(value_node, env)
    if isinstance(container, values.Array):
        if not isinstance(key, values.Number):
            raise LynxTypeError(
                f"array index must be a number, got {key.type_name()}", line
            )
        idx = key.value
        if not isinstance(idx, int) or idx < 0 or idx >= len(container.value):
            raise LynxError(
                f"index {idx} out of range for an array of length {len(container.value)}", line
            )
        container.value[idx] = new_value
        return
    if isinstance(container, values.Map):
        if not isinstance(key, values.SimpleType):
            raise LynxTypeError(
                f"map key must be a simple type, got {key.type_name()}", line
            )
        container.set_item(key, new_value)
        return
    raise LynxTypeError("cannot index into a value that is not an array or map", line)


def is_range(node: Any) -> bool:
    """True when a call/index step is a range expression (`3__7`, `__7`)."""
    return isinstance(node, BinaryExpression) and node.operator == "RANGE"


def _describe(value: values.Type) -> str:
    """Echo a value in an error message, quoting text so it reads clearly."""
    if isinstance(value, values.Text):
        return repr(value.value)
    return repr(value)


def range_bounds(left: values.Type, right: values.Type, line: int | None) -> tuple[int, int]:
    """Validate two range endpoints and return them as integer bounds.

    Only non-negative integers are accepted; anything else raises a message
    that echoes the offending value.
    """
    start = _int_bound(left, "start", line)
    end = _int_bound(right, "end", line)
    if start > end:
        raise LynxError(
            f"range start {start} is greater than range end {end}", line
        )
    return start, end


def _int_bound(value: values.Type, which: str, line: int | None) -> int:
    if not isinstance(value, values.Number):
        raise LynxTypeError(
            f"range {which} must be an integer, got {_describe(value)}", line
        )
    if not isinstance(value.value, int):
        raise LynxTypeError(
            f"range {which} must be an integer, got {_describe(value)}", line
        )
    if value.value < 0:
        raise LynxError(
            f"range {which} must be non-negative, got {value.value}", line
        )
    return value.value


def _range_node_bounds(node: Any, env: Environment, line: int | None) -> tuple[int, int]:
    """Resolve the endpoints of a range expression (`<left>__<right>`) to ints."""
    return range_bounds(evaluate(node.left, env), evaluate(node.right, env), line)


def slice_array(array: values.Array, node: Any, line: int | None, env: Environment) -> values.Type:
    start, end = _range_node_bounds(node, env, line)
    if end >= len(array.value):
        raise LynxError(
            f"range end {end} out of bounds for an array of length {len(array.value)}", line
        )
    return values.Array(array.value[start:end + 1])


def slice_assign(container: values.Type, node: Any, value_node: Any, line: int | None, env: Environment) -> None:
    if not isinstance(container, values.Array):
        raise LynxTypeError("cannot slice a value that is not an array", line)
    start, end = _range_node_bounds(node, env, line)
    if end >= len(container.value):
        raise LynxError(
            f"range end {end} out of bounds for an array of length {len(container.value)}", line
        )
    new_value = evaluate(value_node, env)
    if not isinstance(new_value, values.Array):
        new_value = values.Array([new_value])
    expected = end - start + 1
    if len(new_value.value) != expected:
        raise LynxInputError(
            f"range {start}__{end} covers {expected} elements but got {len(new_value.value)}", line
        )
    container.value[start:end + 1] = new_value.value


def apply_binary(operator: str, left: values.Type, right: values.Type, line: int | None) -> values.Type:
    # Every value defines every operation and operations.binary reconciles any
    # pair of types, so this always resolves; a stub that hasn't been filled in
    # raises LynxNotImplemented, which we locate to `line`.
    if operator == "RANGE":
        # A range is strictly numeric: it must not flow through operations.py,
        # whose coercion would swallow the type of a bad endpoint before we
        # could name it in an error.
        start, end = range_bounds(left, right, line)
        return values.Array([values.Number(i) for i in range(start, end + 1)])
    try:
        return operations.binary(BINARY_METHOD[operator], left, right)
    except LynxNotImplemented as error:
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