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
    # each nesting level in order. Indices are 0-based.
    current: values.Array = array
    for arg in args:
        if not isinstance(current, values.Array):
            raise LynxTypeError("cannot index into a value that is not an array", line)
        index_value = evaluate(arg, env)
        if not isinstance(index_value, values.Number):
            raise LynxTypeError(
                f"array index must be a number, got {index_value.type_name()}", line
            )
        idx = index_value.value
        if not isinstance(idx, int) or idx < 0 or idx >= len(current.value):
            raise LynxError(
                f"index {idx} out of range for an array of length {len(current.value)}", line
            )
        current = current.value[idx]
    return current


def index_map(map_value: values.Map, args: list[Any], line: int | None, env: Environment) -> values.Type:
    # Each arg is one key lookup; a run of args descends through nested maps.
    current = map_value
    for arg in args:
        if not isinstance(current, values.Map):
            raise LynxTypeError("cannot index into a value that is not a map", line)
        key = evaluate(arg, env)
        if not isinstance(key, values.SimpleType):
            raise LynxTypeError(
                f"map key must be a simple type, got {key.type_name()}", line
            )
        try:
            current = current.get_item(key)
        except KeyError:
            raise LynxError(f"key not found in map", line)
    return current


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