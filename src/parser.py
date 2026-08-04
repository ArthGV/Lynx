"""Recursive-descent parser: tokens in, AST out.

Binary-operator precedence is driven entirely by grammar.BINARY_LEVELS and
prefix keyword functions by grammar.UNARY_METHOD, so neither a new operator nor
a new keyword function needs new parsing code.
"""

from src.grammar import BINARY_LEVELS, UNARY_METHOD, UNARY_OPERAND_LEVEL
from src.nodes import (
    Assignment, BinaryExpression, Boolean, Branch, Identifier, If, Number,
    Print, Program, Text, UnaryExpression, Void
)
from src.errors import LynxSyntaxError

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
            case "IF":
                return self.parse_if()
            case "IDENTIFIER":
                return self.parse_assignment()
        token = self.peek()
        raise LynxSyntaxError(
            f"unexpected {self.type()}", token.line if token else None
        )

    def parse_print(self):
        self.match("PRINT")
        return Print(self.parse_expression())

    def parse_assignment(self):
        name = self.match("IDENTIFIER").value
        self.match("COLON")
        return Assignment(name, self.parse_expression())

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
            case "TEXT":
                return Text(self.advance().value)
            case "BOOLEAN":
                return Boolean(self.advance().value)
            case "VOID":
                self.advance()
                return Void()
            case "IDENTIFIER":
                return Identifier(self.advance().value, token.line)
        raise LynxSyntaxError(
            f"unexpected {self.type()}", token.line if token else None
        )
