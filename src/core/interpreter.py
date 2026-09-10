"""Walk the AST and run it.

`execute` handles statements (side effects); `evaluate` handles expressions
(returns a Value). Binary operators are dispatched through grammar tables and
their operands reconciled by operations.py, so the interpreter never mentions an
operator character and never decides what two types mean together.
"""

from typing import Any

from src.core.grammar import BINARY_METHOD, UNARY_METHOD
from src.core.nodes import (
    Append,
    ArrayLiteral,
    Assignment,
    BinaryExpression,
    Boolean,
    Call,
    Function,
    Identifier,
    If,
    Loop,
    MapLiteral,
    Number,
    Print,
    Program,
    RangeExpression,
    Return,
    SetItem,
    Skip,
    Stop,
    TableLiteral,
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
from src.runtime import operations, values
from src.runtime.environment import Environment
from src.runtime.functions import FunctionValue, _Return, _Skip, _Stop


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

        case Append(base, value, front, line):
            append_to(base, value, front, line, env)

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

        case Loop(condition, body, targets, iterable):
            if targets is None:
                while evaluate(condition, env).boolean().is_true():
                    try:
                        execute(body, env)
                    except _Stop:
                        break
                    except _Skip:
                        continue
            else:
                items = evaluate(iterable, env).iterate()
                for index, item in enumerate(items):
                    if len(targets) == 1:
                        env.set(targets[0], item)
                    else:
                        env.set(targets[0], values.Number(index))
                        env.set(targets[1], item)
                    try:
                        execute(body, env)
                    except _Stop:
                        break
                    except _Skip:
                        continue

        case Stop(condition, line):
            if condition is None or evaluate(condition, env).boolean().is_true():
                raise _Stop()

        case Skip(condition, line):
            if condition is None or evaluate(condition, env).boolean().is_true():
                raise _Skip()

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

        case Append(base, value, front, line):
            return append_to(base, value, front, line, env)

        case MapLiteral(pairs, line):
            return values.Map([
                (evaluate_key(k, env, line), evaluate(v, env))
                for k, v in pairs
            ])

        case TableLiteral(columns, line):
            return values.Table([
                (evaluate_table_key(k, env, line), [evaluate(v, env) for v in values_list])
                for k, values_list in columns
            ])

        case Identifier(name, line):
            return env.get(name, line)

        case Call(callee, args, line):
            return call(callee, args, line, env)

        case UnaryExpression(operator, operand, line):
            return apply_unary(operator, evaluate(operand, env), line)

        case BinaryExpression(left, operator, right, line):
            return apply_binary(operator, evaluate(left, env), evaluate(right, env), line)

        case RangeExpression(start, end, line):
            return build_range(start, end, line, env)

        case _:
            raise LynxTypeError(f"cannot evaluate {type(node).__name__}")


def evaluate_key(node: Any, env: Environment, line: int | None) -> values.Type:
    key = evaluate(node, env)
    if not isinstance(key, values.SimpleType):
        raise LynxTypeError(
            f"map key must be a simple type, got {key.type_name()}", line
        )
    return key


def evaluate_table_key(node: Any, env: Environment, line: int | None) -> values.Text:
    name = evaluate(node, env)
    if not isinstance(name, values.Text):
        raise LynxTypeError(
            f"table column name must be text, got {name.type_name()}", line
        )
    return name


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

    if isinstance(fn, values.Table):
        return index_table(fn, args, line, env)

    if isinstance(fn, values.Text):
        return index_text(fn, args, line, env)

    if not isinstance(fn, FunctionValue):
        if isinstance(callee, str):
            raise LynxTypeError(
                f"'{callee}' is not a function, it is a {fn.type_name()}", line
            )
        raise LynxTypeError(f"cannot call a {fn.type_name()}", line)
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


def index_table(table: values.Table, args: list[Any], line: int | None, env: Environment) -> values.Type:
    # Each arg is one access step: a text key picks a column, a number picks a
    # row. A run of args descends through the returned value (`t 'id' 0`).
    current = table
    for arg in args:
        if is_range(arg):
            raise LynxError("range slicing is only supported for arrays", line)
        current = get_element(current, arg, line, env)
    return current


def index_text(text_value: values.Text, args: list[Any], line: int | None, env: Environment) -> values.Type:
    # Same stepping as index_array: a range step is a characters slice, a plain
    # step is one character lookup.
    current = text_value
    for arg in args:
        if is_range(arg):
            current = slice_text(current, arg, line, env)
        else:
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
        return container.get_item(key)
    if isinstance(container, values.Table):
        if isinstance(key, values.Text):
            return container.get_column(key.value)
        if isinstance(key, values.Number):
            idx = key.value
            if not isinstance(idx, int) or idx < 0 or idx >= container.nrows:
                raise LynxError(
                    f"index {idx} out of range for a table with {container.nrows} rows", line
                )
            return container.get_row(idx)
        raise LynxTypeError(
            f"table access needs a column name or a row index, got {key.type_name()}", line
        )
    if isinstance(container, values.Text):
        if not isinstance(key, values.Number):
            raise LynxTypeError(
                f"text index must be a number, got {key.type_name()}", line
            )
        idx = key.value
        if not isinstance(idx, int) or idx < 0 or idx >= len(container.value):
            raise LynxError(
                f"index {idx} out of range for text of length {len(container.value)}", line
            )
        return values.Text(container.value[idx])
    raise LynxTypeError("cannot index into a value that is not an array or map", line)


def append_to(base: str, value_node: Any, front: bool, line: int | None, env: Environment) -> values.Type:
    # `my_arr <: x` appends at the end; `my_arr >: x` at the front. An Array x
    # splices its elements, anything else appends as a single element. Returns
    # the (same, now mutated) array so it can be printed or assigned.
    container = env.get(base, line)
    if not isinstance(container, values.Array):
        raise LynxTypeError(
            f"cannot {'prepend' if front else 'append'} onto a {container.type_name()}", line
        )
    added = evaluate(value_node, env)
    items = added.value if isinstance(added, values.Array) else [added]
    if front:
        container.value[0:0] = items
    else:
        container.value.extend(items)
    return container


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
    if isinstance(container, values.Text):
        if not isinstance(key, values.Number):
            raise LynxTypeError(
                f"text index must be a number, got {key.type_name()}", line
            )
        idx = key.value
        if not isinstance(idx, int) or idx < 0 or idx >= len(container.value):
            raise LynxError(
                f"index {idx} out of range for text of length {len(container.value)}", line
            )
        if not isinstance(new_value, values.Text):
            raise LynxTypeError(
                f"text index assignment needs a text, got {new_value.type_name()}", line
            )
        if len(new_value.value) != 1:
            raise LynxError(
                f"text index assignment needs exactly one character, got {len(new_value.value)}", line
            )
        chars = list(container.value)
        chars[idx] = new_value.value
        container.value = "".join(chars)
        return
    raise LynxTypeError("cannot index into a value that is not an array or map", line)


def is_range(node: Any) -> bool:
    """True when a call/index step is a range expression (`3__7`, `__7`, `5__`)."""
    return isinstance(node, RangeExpression)


def _describe(value: values.Type) -> str:
    """Echo a value in an error message, quoting text so it reads clearly."""
    if isinstance(value, values.Text):
        return repr(value.value)
    return repr(value)


def _int_bound(value: values.Type, which: str, line: int | None) -> int:
    if not isinstance(value, values.Number):
        raise LynxTypeError(
            f"range {which} must be an integer, got {_describe(value)}", line
        )
    if not isinstance(value.value, int):
        raise LynxTypeError(
            f"range {which} must be an integer, got {_describe(value)}", line
        )
    return value.value


def build_range(start_node: Any, end_node: Any, line: int | None, env: Environment) -> values.Type:
    """Evaluate a range expression (`<start>__<end>`) into an array.

    An omitted side is an implicit 0: `__5` runs up from 0, `5__` runs down to
    0. The implicit 0 must be reachable, so the given side of a shorthand must
    be non-negative — an explicit `0__-3` is fine.
    """
    start = 0 if start_node is None else _int_bound(evaluate(start_node, env), "start", line)
    end = 0 if end_node is None else _int_bound(evaluate(end_node, env), "end", line)
    if start_node is None and end < 0:
        raise LynxError(f"range from 0 needs a non-negative end, got {end}", line)
    if end_node is None and start < 0:
        raise LynxError(f"range to 0 needs a non-negative start, got {start}", line)
    step = 1 if end >= start else -1
    stop = end + 1 if end >= start else end - 1
    return values.Array([values.Number(i) for i in range(start, stop, step)])


def _slice_bounds(node: Any, env: Environment, line: int | None) -> tuple[int, int]:
    """Resolve a slice range's endpoints; array indices must be non-negative."""
    start = 0 if node.start is None else _int_bound(evaluate(node.start, env), "start", line)
    end = 0 if node.end is None else _int_bound(evaluate(node.end, env), "end", line)
    if start < 0:
        raise LynxError(f"array slice start must be non-negative, got {start}", line)
    if end < 0:
        raise LynxError(f"array slice end must be non-negative, got {end}", line)
    return start, end


def _sliced_indices(start: int, end: int) -> list[int]:
    """The array indices a slice covers, ascending or descending with its bounds."""
    step = 1 if end >= start else -1
    stop = end + 1 if end >= start else end - 1
    return list(range(start, stop, step))


def slice_array(array: values.Array, node: Any, line: int | None, env: Environment) -> values.Type:
    start, end = _slice_bounds(node, env, line)
    worst = max(start, end)
    if worst >= len(array.value):
        which = "start" if start > end else "end"
        raise LynxError(
            f"range {which} {worst} out of bounds for an array of length {len(array.value)}", line
        )
    return values.Array([array.value[i] for i in _sliced_indices(start, end)])


def slice_text(text_value: values.Text, node: Any, line: int | None, env: Environment) -> values.Type:
    start, end = _slice_bounds(node, env, line)
    worst = max(start, end)
    if worst >= len(text_value.value):
        which = "start" if start > end else "end"
        raise LynxError(
            f"range {which} {worst} out of bounds for text of length {len(text_value.value)}", line
        )
    return values.Text("".join(text_value.value[i] for i in _sliced_indices(start, end)))


def slice_assign(container: values.Type, node: Any, value_node: Any, line: int | None, env: Environment) -> None:
    if isinstance(container, values.Text):
        _slice_assign_text(container, node, value_node, line, env)
        return
    if not isinstance(container, values.Array):
        raise LynxTypeError("cannot slice a value that is not an array", line)
    start, end = _slice_bounds(node, env, line)
    indices = _sliced_indices(start, end)
    worst = max(start, end)
    if worst >= len(container.value):
        which = "start" if start > end else "end"
        raise LynxError(
            f"range {which} {worst} out of bounds for an array of length {len(container.value)}", line
        )
    new_value = evaluate(value_node, env)
    if not isinstance(new_value, values.Array):
        new_value = values.Array([new_value])
    if len(new_value.value) != len(indices):
        raise LynxInputError(
            f"range {start}__{end} covers {len(indices)} elements but got {len(new_value.value)}", line
        )
    for index, item in zip(indices, new_value.value):
        container.value[index] = item


def _slice_assign_text(container: values.Text, node: Any, value_node: Any, line: int | None, env: Environment) -> None:
    # Mirrors the array slice-assignment contract: the replacement text must
    # cover exactly the sliced characters, so the string keeps its length.
    start, end = _slice_bounds(node, env, line)
    indices = _sliced_indices(start, end)
    worst = max(start, end)
    if worst >= len(container.value):
        which = "start" if start > end else "end"
        raise LynxError(
            f"range {which} {worst} out of bounds for text of length {len(container.value)}", line
        )
    new_value = evaluate(value_node, env)
    if not isinstance(new_value, values.Text):
        raise LynxTypeError(
            f"text slice assignment needs a text, got {new_value.type_name()}", line
        )
    if len(new_value.value) != len(indices):
        raise LynxInputError(
            f"range {start}__{end} covers {len(indices)} characters but got {len(new_value.value)}", line
        )
    chars = list(container.value)
    for index, char in zip(indices, new_value.value):
        chars[index] = char
    container.value = "".join(chars)


def apply_binary(operator: str, left: values.Type, right: values.Type, line: int | None) -> values.Type:
    # Every value defines every operation and operations.binary reconciles any
    # pair of types, so this always resolves; a stub that hasn't been filled in
    # raises LynxNotImplemented, which we locate to `line`.
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