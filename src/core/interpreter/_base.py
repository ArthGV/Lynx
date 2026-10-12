"""Walk the AST and run it.

`execute` handles statements (side effects); `evaluate` handles expressions
(returns a Value). Binary operators are dispatched through grammar tables and
their operands reconciled by operations.py, so the interpreter never mentions an
operator character and never decides what two types mean together.

Statement-side helpers live in `statements.py`, expression-side helpers in
`expressions.py`, and the two operator dispatchers in `operators.py`. Those are
imported at the *bottom* of this file — after every function they call — so
they can import back from this partially-loaded module without a cycle.
"""

from typing import Any, cast

from src.core.nodes import (
    Append,
    ArrayLiteral,
    Assignment,
    BinaryExpression,
    Boolean,
    Call,
    Cell,
    Delete,
    Error,
    Function,
    GraphBuild,
    GraphLiteral,
    GraphQuery,
    Identifier,
    If,
    Loop,
    MapLiteral,
    MultiAssignment,
    Number,
    Print,
    Program,
    RangeExpression,
    Read,
    Return,
    SetItem,
    Skip,
    Stop,
    TableLiteral,
    TableQuery,
    Test,
    Text,
    Try,
    UnaryExpression,
    Void,
    Write,
)
from src.errors.errors import LynxError, LynxTestError, LynxTypeError
from src.runtime import values
from src.runtime.environment import Environment
from src.runtime.functions import FunctionValue, _Return, _Skip, _Stop

__all__ = [
    "_Return",
    "_Skip",
    "_Stop",
    "evaluate",
    "evaluate_key",
    "evaluate_table_key",
    "execute",
    "is_range",
]


def _bind_unpack(names: list[str], value: values.Type, env: Environment, line: int | None) -> None:
    if not isinstance(value, values.Array):
        raise LynxError(f"cannot unpack {value.type_name()}, expected Array", line)
    if len(value.value) != len(names):
        raise LynxError(f"expected {len(names)} values to unpack, got {len(value.value)}", line)
    for name, elem in zip(names, value.value):
        env.set(name, elem.copy())


def _handle_loop_targets(targets: list[Any], index: int, item: values.Type, env: Environment, line: int | None) -> None:
    """Bind loop targets for a single iteration.

    targets structure examples:
    - ["v"] -> bind element to "v" (single target = element)
    - ["i", "v"] -> bind index to "i", element to "v"
    - [["a", "b"]] -> unpack element to "a", "b"
    - ["i", ["a", "b"]] -> bind index to "i", unpack element to "a", "b"
    """
    if not targets:
        return

    # Check if any target is an unpack group (list)
    has_unpack = any(isinstance(t, list) for t in targets)

    if has_unpack:
        # Has unpack groups - first target might be index
        first = targets[0]
        if isinstance(first, list):
            # First target is unpack group (no index): loop (a, b): items
            _bind_unpack(first, item, env, line)
        else:
            # First target is index variable
            env.set(first, values.Number(index))
            remaining = targets[1:]
            if len(remaining) == 1 and isinstance(remaining[0], list):
                # Unpack target: loop i, (a, b): items
                _bind_unpack(remaining[0], item, env, line)
            elif not remaining:
                # Just index: loop i: items
                pass
            else:
                raise LynxError("invalid loop targets", line)
    else:
        # No unpack groups - simple targets
        if len(targets) == 1:
            # Single target: loop v: items -> bind element
            env.set(targets[0], item.copy())
        elif len(targets) == 2:
            # Two targets: loop i, v: items -> bind index and element
            env.set(targets[0], values.Number(index))
            env.set(targets[1], item.copy())
        else:
            raise LynxError("invalid loop targets", line)


def execute(node: Any, env: Environment) -> None:
    if isinstance(node, list):
        for statement in node:
            execute(statement, env)
        return

    match node:
        case Program(statements):
            execute(statements, env)

        case Write(value, path, line):
            _files.write(evaluate(value, env), evaluate(path, env), line)

        case Print(value):
            print(_printable(value, env))

        case Assignment(name, value):
            env.set(name, evaluate(value, env).copy())

        case MultiAssignment(names, value, line):
            val = evaluate(value, env)
            # Simple types (Number, Text, Boolean, Void): assign same value to all
            if isinstance(val, (values.Number, values.Text, values.Boolean, values.Void)):
                for name in names:
                    env.set(name, val.copy())
            else:
                # Complex types (Array, Map, Table, Graph): iterate and unpack
                items = val.iterate()
                if len(items) != len(names):
                    raise LynxError(f"expected {len(names)} values from {val.type_name()}, got {len(items)}", line)
                for name, item in zip(names, items):
                    env.set(name, item.copy())

        case SetItem(base, steps, value, line):
            _statements.assign_item(base, steps, value, line, env)

        case Append(base, value, front, line):
            _statements.append_to(base, value, front, line, env)

        case Delete(base, steps, line):
            _statements.delete_item(base, steps, line, env)

        case Function(name, params, body):
            env.set(name, FunctionValue(name, params, body, env))

        case Call(callee, args, line):
            _expressions.call(callee, args, line, env)

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
                iterable_line = getattr(iterable, "line", None)
                for index, item in enumerate(items):
                    _handle_loop_targets(
                        targets, index, item, env, iterable_line
                    )
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

        case Test(condition, message, line):
            if not evaluate(condition, env).boolean().is_true():
                msg = str(evaluate(message, env)) if message is not None else ""
                raise LynxTestError(msg, line)

        case Error(message, line):
            msg = str(evaluate(message, env)) if message is not None else ""
            raise LynxError(msg, line)

        case Try(try_body, catch_body, catch_var, else_body, line):
            error_occurred = False
            try:
                execute(try_body, env)
            except LynxError as e:
                error_occurred = True
                if catch_body is not None:
                    catch_env = Environment(env)
                    if catch_var is not None:
                        catch_env.set(catch_var, values.Text(e.message))
                    execute(catch_body, catch_env)
                else:
                    raise
            if not error_occurred and else_body is not None:
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
            return values.Array([evaluate(item, env).copy() for item in items])

        case Append(base, value, front, line):
            return _statements.append_to(base, value, front, line, env)

        case MapLiteral(pairs, line):
            return values.Map([(evaluate_key(k, env, line), evaluate(v, env).copy()) for k, v in pairs], line)

        case TableLiteral(columns, line):
            return values.Table(
                [
                    (
                        evaluate_table_key(k, env, line),
                        _expressions.column_cells_list(value_exprs, line, env),
                    )
                    for k, value_exprs in columns
                ],
                line,
            )

        case Cell(inner):
            return evaluate(inner, env)

        case Identifier(name, line):
            value = env.get(name, line)
            if isinstance(value, FunctionValue):
                raise LynxTypeError(f"cannot use function '{name}' as a value", line)
            return cast(values.Type, value)

        case Call(callee, args, line):
            return _expressions.call(callee, args, line, env)

        case TableQuery(kind, expression, line):
            return _expressions.evaluate_table_query(kind, expression, line, env)

        case GraphBuild(operand, line):
            if operand is None:
                return values.Graph()
            source = evaluate(operand, env)
            return values.Graph(source, line)

        case GraphLiteral(segments, line):
            return _expressions.build_graph(segments, line, env)

        case GraphQuery(kind, graph, node, line):
            return _expressions.evaluate_graph_query(kind, graph, node, line, env)

        case UnaryExpression(operator, operand, line):
            return _operators.apply_unary(operator, evaluate(operand, env), line)

        case Read(operand, line):
            path = evaluate(operand, env)
            if not isinstance(path, values.Text):
                raise LynxTypeError(f"read needs a text path, got {path.type_name()}", line)
            try:
                return _files.read(path.value, line)
            except LynxError as error:
                if error.line is None:
                    error.line = line
                raise

        case BinaryExpression(left, operator, right, line):
            return _operators.apply_binary(operator, evaluate(left, env), evaluate(right, env), line)

        case RangeExpression(start, end, line):
            return _expressions.build_range(start, end, line, env)

        case _:
            raise LynxTypeError(f"cannot evaluate {type(node).__name__}")


def _printable(node: Any, env: Environment) -> Any:
    """What `>>` prints: a bare function name prints the function itself;
    everywhere else a function is not a value."""
    if isinstance(node, Identifier):
        named = env.get(node.name, node.line)
        if isinstance(named, FunctionValue):
            return named
    return evaluate(node, env)


def evaluate_key(node: Any, env: Environment, line: int | None) -> values.Type:
    key = evaluate(node, env)
    if not isinstance(key, values.SimpleType):
        raise LynxTypeError(f"map key must be a simple type, got {key.type_name()}", line)
    return key


def evaluate_table_key(node: Any, env: Environment, line: int | None) -> values.Text:
    name = evaluate(node, env)
    if not isinstance(name, values.Text):
        raise LynxTypeError(f"table column name must be text, got {name.type_name()}", line)
    return name


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
        raise LynxTypeError(f"range {which} must be an integer, got {_describe(value)}", line)
    if not isinstance(value.value, int):
        raise LynxTypeError(f"range {which} must be an integer, got {_describe(value)}", line)
    return value.value


# Imported last: these modules call back into the functions above, so this
# module must be fully populated before they load.
from src.core import files as _files  # noqa: E402
from src.core.interpreter import expressions as _expressions  # noqa: E402
from src.core.interpreter import operators as _operators  # noqa: E402
from src.core.interpreter import statements as _statements  # noqa: E402  # fmt: skip
