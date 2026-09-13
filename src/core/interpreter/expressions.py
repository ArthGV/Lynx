"""Expression-side evaluation helpers: call resolution, indexing and slicing of
every container type, range building, and table-query evaluation. The two
dispatchers (`execute`/`evaluate`) live in `_base.py` and route here.

This module imports its shared helpers (`evaluate`, `execute`, `is_range`,
...) back from the partially-loaded `_base` — which in turn imports this
module only at the bottom of its file, after those functions exist.
"""

from typing import Any

from src.core.grammar import WHERE_OPERATORS
from src.core.interpreter._base import (
    _describe,
    _int_bound,
    evaluate,
    execute,
    is_range,
)
from src.core.nodes import ArrayLiteral, BinaryExpression, Call, Cell, RangeExpression
from src.errors.errors import LynxError, LynxInputError, LynxSyntaxError, LynxTypeError
from src.runtime import values
from src.runtime.environment import Environment
from src.runtime.functions import FunctionValue, _Return

# Which binary operators `where t 'col' <op> value` accepts. Shared with the
# parser, which splits the operand on any of these tokens.
_WHERE_OPERATORS = WHERE_OPERATORS


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
    # Several all-text args project a subset of columns: `t 'id', 'price'` is a
    # new table with those columns, same as `select t 'id', 'price'`. Any other
    # access falls through to the single-step descent (`t 'id' 0`).
    if len(args) > 1:
        columns: list[str] = []
        for arg in args:
            if is_range(arg):
                break
            key = evaluate(arg, env)
            if not isinstance(key, values.Text):
                break
            columns.append(key.value)
        else:
            return table.select(columns, line)
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


def evaluate_table_query(kind: str, expression: Any, line: int | None, env: Environment) -> values.Type:
    """Resolve one `select` / `order` / `group` / `where` expression.

    The parser stores the raw rest-of-line operand (`parse_binary(0)` — the
    Call for a table plus columns, or a BinaryExpression for `where`), and this
    decomposes it per kind so the two sides of a comparison are never coerced
    into each other before the row-by-row filter runs.
    """
    if kind == "WHERE":
        return evaluate_where(expression, line, env)
    if not isinstance(expression, Call) or not expression.args:
        raise LynxSyntaxError(
            f"{kind.lower()} needs a table and a column, like: {kind.lower()} t 'price'", line
        )
    table = table_base(expression, kind, line, env)
    if kind == "SELECT":
        return table.select([column_name(arg, line, env) for arg in expression.args], line)
    if len(expression.args) != 1:
        raise LynxSyntaxError(f"{kind.lower()} needs exactly one column", line)
    column = column_name(expression.args[0], line, env)
    if kind == "ORDER":
        return table.order_by(column, line)
    return table.group_by(column, line)


def evaluate_where(expression: Any, line: int | None, env: Environment) -> values.Type:
    if not isinstance(expression, BinaryExpression) or expression.operator not in _WHERE_OPERATORS:
        raise LynxSyntaxError("where needs a comparison, like: where t 'price' > 20", line)
    left = expression.left
    if not isinstance(left, Call) or len(left.args) != 1:
        raise LynxSyntaxError("where needs a comparison, like: where t 'price' > 20", line)
    table = table_base(left, "WHERE", line, env)
    column = column_name(left.args[0], line, env)
    rhs = evaluate(expression.right, env)
    return table.rows_where(column, expression.operator, rhs, line)


def table_base(call_node: Call, kind: str, line: int | None, env: Environment) -> values.Table:
    # `callee` is either a name or an expression (from a chained call); same
    # resolution as call().
    name = call_node.callee
    value = env.get(name, line) if isinstance(name, str) else evaluate(name, env)
    if not isinstance(value, values.Table):
        raise LynxTypeError(f"{kind.lower()} needs a table, got {value.type_name()}", line)
    return value


def column_name(node: Any, line: int | None, env: Environment) -> str:
    name = evaluate(node, env)
    if not isinstance(name, values.Text):
        raise LynxTypeError(f"table column name must be text, got {name.type_name()}", line)
    return name.value


def cell_value(node: Any, line: int | None, env: Environment) -> list[values.Type]:
    # One table column cell. A `Cell` (a parenthesized value like `(4, 5)`,
    # `(a)` or `(__7)`) is kept as a single element; any other value that
    # evaluates to an array is spread into the column.
    if isinstance(node, Cell):
        return [evaluate(node.inner, env)]
    value = evaluate(node, env)
    if isinstance(value, values.Array):
        return list(value.value)
    return [value]


def column_cells_list(value_nodes: list[Any], line: int | None, env: Environment) -> list[values.Type]:
    # The column values parsed from a table literal (`'id': 1, 2, a; ...`):
    # one cell per value, arrays spreading as above.
    cells: list[values.Type] = []
    for node in value_nodes:
        cells.extend(cell_value(node, line, env))
    return cells


def table_cells(value_node: Any, line: int | None, env: Environment) -> list[values.Type]:
    # The right-hand side of a table column assignment. A comma-run is already
    # an ArrayLiteral of per-cell values, so use them as-is; a single value
    # (bare array, range, scalar, parenthesized Cell) goes through cell_value.
    if isinstance(value_node, ArrayLiteral):
        return column_cells_list(value_node.items, line, env)
    return cell_value(value_node, line, env)