"""Walk the AST and run it.

`execute` handles statements (side effects); `evaluate` handles expressions
(returns a Value). Binary operators are dispatched through grammar tables, so
the interpreter never mentions an operator character.
"""

from src import values
from src.grammar import BINARY_METHOD
from src.nodes import (
    Assignment, BinaryExpression, Boolean, Identifier, If, Number, Print,
    Program, Text, TypeOf, Void, Lenght, ToText
)
from src.errors import LynxTypeError, LynxNotImplemented


def execute(node, env):
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

        case If(branches, else_body):
            for branch in branches:
                if evaluate(branch.condition, env).boolean().is_true():
                    execute(branch.body, env)
                    return
            if else_body is not None:
                execute(else_body, env)

        case _:
            raise LynxTypeError(f"cannot execute {type(node).__name__}")


def evaluate(node, env):
    match node:
        case Number(value):
            return values.Number(value)

        case Text(value):
            return values.Text(value)

        case Boolean(value):
            return values.Boolean(value)

        case Void():
            return values.Void()

        case ToText(value):
            return evaluate(value, env).text()

        case Identifier(name, line):
            return env.get(name, line)

        case TypeOf(value):
            return values.Text(evaluate(value, env).type_name())

        case Lenght(value):
            return evaluate(value, env).lenght()

        case BinaryExpression(left, operator, right, line):
            return apply_binary(operator, evaluate(left, env), evaluate(right, env), line)

        case _:
            raise LynxTypeError(f"cannot evaluate {type(node).__name__}")


def apply_binary(operator, left, right, line):
    # Every value defines every operation, so this always resolves; a stub that
    # hasn't been filled in raises LynxNotImplemented, which we locate to `line`.
    try:
        return getattr(left, BINARY_METHOD[operator])(right)
    except LynxNotImplemented as error:
        if error.line is None:
            error.line = line
        raise
