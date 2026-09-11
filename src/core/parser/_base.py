"""Shared parser machinery: token navigation, the public `parse()` entry point,
and the little predicates both grammars use.

Binary-operator precedence is driven entirely by grammar.BINARY_LEVELS and
prefix keyword functions by grammar.UNARY_METHOD, so neither a new operator nor
a new keyword function needs new parsing code. The `Parser` callers see is the
composed class in `__init__.py` — token navigation and `parse()` from here,
statement rules from `statements.py`, expression rules from `expressions.py`.
This base exists so those two grammars can subclass it without an import cycle
through the package `__init__`.
"""

from typing import Any

from src.core.grammar import UNARY_METHOD
from src.core.lexer import Token
from src.core.nodes import Program
from src.errors.errors import LynxSyntaxError

EOF = "EOF"

# Keyword tokens whose operand is the whole rest of the line: a table plus its
# columns (`select t 'a', 'b'`) or, for where, that plus a comparison. They all
# keep the raw parse_binary(0) expression and let the interpreter decompose it.
TABLE_QUERY = {"SELECT", "ORDER", "GROUP", "WHERE"}


class Parser:
    def __init__(self, tokens: list[Token]) -> None:
        self.tokens = tokens
        self.current = 0

    def peek(self) -> Token | None:
        if self.current >= len(self.tokens):
            return None
        return self.tokens[self.current]

    def type(self) -> str:
        token = self.peek()
        return token.type if token else EOF

    def advance(self) -> Token:
        token = self.tokens[self.current]
        self.current += 1
        return token

    def match(self, expected: str) -> Token:
        if self.type() != expected:
            token = self.peek()
            line = token.line if token else None
            raise LynxSyntaxError(f"expected {expected}, got {self.type()}", line)
        return self.advance()

    def skip_newlines(self) -> None:
        while self.type() == "NEWLINE":
            self.advance()

    def parse(self) -> Program:
        statements: list[Any] = []
        self.skip_newlines()
        while self.type() != EOF:
            statements.append(self.parse_statement())
            self.skip_newlines()
        return Program(statements)

    def peek_line(self) -> int | None:
        token = self.peek()
        return token.line if token else None

    def _starts_expression(self, token_type: str) -> bool:
        if token_type in ("NUMBER", "TEXT", "BOOLEAN", "VOID", "IDENTIFIER", "LBRACE", "LPAREN", "LBRACK", "RANGE", "ARRAY", "MAP", "TABLE"):
            return True
        if token_type in TABLE_QUERY:
            return True
        return token_type in UNARY_METHOD

    def _can_start_bound(self, token_type: str) -> bool:
        return token_type == "MINUS" or self._starts_expression(token_type)