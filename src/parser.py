"""Recursive-descent parser: tokens in, AST out.

Binary-operator precedence is driven entirely by grammar.BINARY_LEVELS and
prefix keyword functions by grammar.UNARY_METHOD, so neither a new operator nor
a new keyword function needs new parsing code.
"""

from src.errors.errors import LynxSyntaxError
from src.grammar import BINARY_LEVELS, UNARY_METHOD, UNARY_OPERAND_LEVEL
from src.nodes import (
    Assignment,
    BinaryExpression,
    Boolean,
    Branch,
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

EOF = "EOF"


class Parser:
    def __init__(self, tokens):
        self.tokens = tokens
        self.current = 0

    def peek(self):
        if self.current >= len(self.tokens):
            return None
        return self.tokens[self.current]

    def type(self):
        token = self.peek()
        return token.type if token else EOF

    def advance(self):
        token = self.tokens[self.current]
        self.current += 1
        return token

    def match(self, expected):
        if self.type() != expected:
            token = self.peek()
            line = token.line if token else None
            raise LynxSyntaxError(f"expected {expected}, got {self.type()}", line)
        return self.advance()

    def skip_newlines(self):
        while self.type() == "NEWLINE":
            self.advance()

    # -- statements -----------------------------------------------------

    def parse(self):
        statements = []
        self.skip_newlines()
        while self.type() != EOF:
            statements.append(self.parse_statement())
            self.skip_newlines()
        return Program(statements)

    def parse_statement(self):
        match self.type():
            case "PRINT":
                return self.parse_print()
            case "RETURN":
                return self.parse_return()
            case "IF":
                return self.parse_if()
            case "IDENTIFIER":
                return self.parse_name_statement()
        token = self.peek()
        raise LynxSyntaxError(
            f"unexpected {self.type()}", token.line if token else None
        )

    def parse_print(self):
        self.match("PRINT")
        return Print(self.parse_expression())

    def parse_return(self):
        token = self.match("RETURN")
        return Return(self.parse_expression(), token.line)

    def parse_name_statement(self):
        # After a leading identifier we could have an assignment (`x: 5`), a
        # function declaration (`f: a, b` + indented body) or a function call
        # (`f a, b`). A colon means declaration-or-assignment, decided by whether
        # the right-hand side is a parameter list followed by an indented block.
        start = self.current
        line = self.peek().line
        name = self.advance().value
        if self.type() != "COLON":
            return self.parse_call(name, line)
        if self._is_function_declaration():
            return self._parse_function(name)
        self.current = start
        return self.parse_assignment()

    def _is_function_declaration(self):
        # At the COLON. True when the right-hand side is IDENTIFIER
        # (, IDENTIFIER)* then an indented block — i.e. a parameter list rather
        # than an assignment expression.
        i = self.current + 1  # skip COLON
        if self._type_at(i) != "IDENTIFIER":
            return False
        i += 1
        while self._type_at(i) == "COMMA":
            i += 1
            if self._type_at(i) != "IDENTIFIER":
                return False
            i += 1
        return (
            self._type_at(i) == "NEWLINE"
            and self._type_at(i + 1) == "INDENT"
        )

    def _type_at(self, i):
        if i < len(self.tokens):
            return self.tokens[i].type
        return EOF

    def _parse_function(self, name):
        self.match("COLON")
        params = [self.match("IDENTIFIER").value]
        while self.type() == "COMMA":
            self.advance()
            params.append(self.match("IDENTIFIER").value)
        return Function(name, params, self.parse_body())

    def parse_assignment(self):
        name = self.match("IDENTIFIER").value
        self.match("COLON")
        return Assignment(name, self.parse_expression())

    def parse_call(self, name, line):
        args = [self.parse_expression()]
        while self.type() == "COMMA":
            self.advance()
            args.append(self.parse_expression())
        return Call(name, args, line)

    def parse_if(self):
        self.match("IF")
        self.match("COLON")
        branches = [Branch(self.parse_expression(), self.parse_body())]
        else_body = None
        while self.type() == "ELSE":
            self.advance()
            self.match("COLON")
            if self.type() == "NEWLINE":  # bare `else:`
                else_body = self.parse_body()
                break
            branches.append(Branch(self.parse_expression(), self.parse_body()))
        return If(branches, else_body)

    def parse_body(self):
        self.match("NEWLINE")
        self.match("INDENT")
        statements = []
        self.skip_newlines()
        while self.type() not in ("DEDENT", EOF):
            statements.append(self.parse_statement())
            self.skip_newlines()
        self.match("DEDENT")
        return statements

    # -- expressions ----------------------------------------------------

    def parse_expression(self):
        return self.parse_binary(0)

    def parse_binary(self, level):
        if level >= len(BINARY_LEVELS):
            return self.parse_primary()
        operators = BINARY_LEVELS[level]
        left = self.parse_binary(level + 1)
        while self.type() in operators:
            token = self.advance()
            right = self.parse_binary(level + 1)
            left = BinaryExpression(left, token.type, right, token.line)
        return left

    def parse_primary(self):
        token = self.peek()
        match self.type():
            case operator if operator in UNARY_METHOD:
                self.advance()
                return UnaryExpression(
                    operator, self.parse_binary(UNARY_OPERAND_LEVEL), token.line
                )
            case "NUMBER":
                return Number(self.advance().value)
            case "MINUS":
                return self.parse_negative()
            case "TEXT":
                return Text(self.advance().value)
            case "BOOLEAN":
                return Boolean(self.advance().value)
            case "VOID":
                self.advance()
                return Void()
            case "IDENTIFIER":
                name = self.advance().value
                if self._starts_expression(self.type()):
                    return self.parse_call(name, token.line)
                return Identifier(name, token.line)
        raise LynxSyntaxError(
            f"unexpected {self.type()}", token.line if token else None
        )

    def parse_negative(self):
        token = self.advance()
        if self.type() != "NUMBER":
            raise LynxSyntaxError(
                f"expected NUMBER after '-', got {self.type()}", token.line
            )
        return Number(-float(self.advance().value))

    def _starts_expression(self, token_type):
        if token_type in ("NUMBER", "TEXT", "BOOLEAN", "VOID", "IDENTIFIER"):
            return True
        return token_type in UNARY_METHOD
