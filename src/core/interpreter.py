"""Walk the AST and run it.

`execute` handles statements (side effects); `evaluate` handles expressions
(returns a Value). Binary operators are dispatched through grammar tables and
their operands reconciled by operations.py, so the interpreter never mentions an
operator character and never decides what two types mean together.
"""

from typing import Any

from src.core.grammar import BINARY_METHOD, UNARY_METHOD
from src.core.nodes import (
    Assignment,
    BinaryExpression,
    Boolean,
    Call,
    Function,
    Identifier,
    If,
    Number,
    Print,
    Program,
    Return,
    Text,
    UnaryExpression,
    Void,
)
from src.errors.errors import (
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



def evaluate(node: Any, env: Environment) -> values.Value:
    match node:
        case Number(value):
            return values.Number(value)

        case Text(value):
            return values.Text(value)

        case Boolean(value):
            return values.Boolean(value)

        case Void():
            return values.Void()

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


def call(callee: str, args: list[Any], line: int | None, env: Environment) -> values.Value:
    fn = env.get(callee, line)
    if not isinstance(fn, FunctionValue):
        raise LynxNameError(f"'{callee}' is not a function", line)
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


def apply_binary(operator: str, left: values.Value, right: values.Value, line: int | None) -> values.Value:
    # Every value defines every operation and operations.binary reconciles any
    # pair of types, so this always resolves; a stub that hasn't been filled in
    # raises LynxNotImplemented, which we locate to `line`.
    try:
        return operations.binary(BINARY_METHOD[operator], left, right)
    except LynxNotImplemented as error:
        if error.line is None:
            error.line = line
        raise


def apply_unary(operator: str, value: values.Value, line: int | None) -> values.Value:
    # Same contract as apply_binary: every value defines every operation, so a
    # stub that hasn't been filled in raises LynxNotImplemented, which we locate
    # to `line`.
    try:
        return getattr(value, UNARY_METHOD[operator])()
    except LynxNotImplemented as error:
        if error.line is None:
            error.line = line
        raise