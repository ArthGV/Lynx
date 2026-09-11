"""Walk the AST and run it.

`execute` handles statements (side effects); `evaluate` handles expressions
(returns a Value). Binary operators are dispatched through grammar tables and
their operands reconciled by operations.py, so the interpreter never mentions an
operator character and never decides what two types mean together.

Statement-side helpers live in `statements.py`, expression-side helpers in
`expressions.py`, and the two operator dispatchers in `operators.py`. Those are
imported at the *bottom* of this file — after every function they call — so
they can import back from this partially-loaded package without a cycle.
"""

from typing import Any

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
    TableQuery,
    Text,
    UnaryExpression,
    Void,
)
from src.errors.errors import LynxTypeError
from src.runtime import values
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
            _statements.assign_item(base, steps, value, line, env)

        case Append(base, value, front, line):
            _statements.append_to(base, value, front, line, env)

        case Function(name, params, body):
            env.set(name, FunctionValue(params, body, env))

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
            return _statements.append_to(base, value, front, line, env)

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
            return _expressions.call(callee, args, line, env)

        case TableQuery(kind, expression, line):
            return _expressions.evaluate_table_query(kind, expression, line, env)

        case UnaryExpression(operator, operand, line):
            return _operators.apply_unary(operator, evaluate(operand, env), line)

        case BinaryExpression(left, operator, right, line):
            return _operators.apply_binary(operator, evaluate(left, env), evaluate(right, env), line)

        case RangeExpression(start, end, line):
            return _expressions.build_range(start, end, line, env)

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


# Imported last: these modules call back into the functions above, so the
# package must be fully populated before they load.
from src.core.interpreter import expressions as _expressions  # noqa: E402
from src.core.interpreter import operators as _operators  # noqa: E402
from src.core.interpreter import statements as _statements  # noqa: E402